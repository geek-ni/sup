logo = """
  _______ ___ ___ _______                          
 |   _   |   Y   |   _   |                        
 |.  1___|   1   |.  |   |                        
 |.  |___ \_   _/|.  |   |                        
 |:  1   | |:  | |:  |   |                        
 |::.. . | |::.| |::.|:. |                        
 `-------' `---' `--- ---'

[API v2] Usov Ivan, 2024.
"""

import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import asyncio
from database import SessionLocal, engine
from models import Base, Pass
from schemas import PassCreate, PassUpdate, PassInDB
from arduino_controller import ArduinoController
from starlette.responses import FileResponse
from config import settings
from datetime import datetime
from logger import logger
from colorama import init, Fore
from contextlib import asynccontextmanager

Base.metadata.create_all(bind=engine)

arduino_controller = ArduinoController()
new_card_queue = asyncio.Queue(maxsize=1)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


"""
#Устаревшая констркция. Если asynccontextmanager не будет воркать, включи это

@app.on_event("startup")
async def startup_event():
    await arduino_controller.connect()
    asyncio.create_task(nfc_processing_task())

@app.on_event("shutdown")
async def shutdown_event():
    await arduino_controller.disconnect()
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    await arduino_controller.connect()
    asyncio.create_task(nfc_processing_task())
    yield
    await arduino_controller.disconnect()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
async def index():
    return FileResponse('index.html')


@app.get("/logs/current")
async def get_current_log():
    return {"log_content": logger.get_current_log_content()}


@app.get("/logs/files")
async def get_log_files():
    return {"log_files": logger.get_all_log_files()}


@app.get("/logs/download/{filename}")
async def download_log(filename: str):
    file_path = os.path.join(logger.log_dir, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename)
    raise HTTPException(status_code=404, detail="Файл лога не найден")


@app.post("/passes/", response_model=PassInDB)
async def create_pass(pass_data: PassCreate, db: Session = Depends(get_db)):
    db_pass = Pass(**pass_data.dict())
    db.add(db_pass)
    logger.log(f"Создан новый пропуск: {db_pass.card_number}")
    try:
        db.commit()
        db.refresh(db_pass)
    except Exception as e:
        db.rollback()
        logger.log(f"Ошибка при создании пропуска: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Ошибка при создании пропуска: {str(e)}")
    return db_pass


@app.get("/passes/", response_model=list[PassInDB])
async def get_passes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    passes = db.query(Pass).offset(skip).limit(limit).all()
    return passes


async def check_pass_and_open_door(card_number: str, db: Session):
    db_pass = db.query(Pass).filter(Pass.card_number == card_number).first()
    if db_pass and db_pass.expires_at > datetime.utcnow():
        db_pass.last_used = datetime.utcnow()
        db.commit()
        await arduino_controller.open_door()
        await asyncio.sleep(settings.DOOR_OPEN_DURATION)
        logger.log(f"Доступ разрешен для карты: {card_number}")
        return True
    logger.log(f"Доступ запрещен для карты: {card_number}")
    return False


@app.get("/check/{card_number}")
async def check_pass(card_number: str, db: Session = Depends(get_db)):
    result = await check_pass_and_open_door(card_number, db)
    return {"access_granted": result}


@app.delete("/passes/{card_number}")
async def delete_pass(card_number: str, db: Session = Depends(get_db)):
    db_pass = db.query(Pass).filter(Pass.card_number == card_number).first()
    if db_pass:
        db.delete(db_pass)
        db.commit()
        logger.log(f"Удален пропуск: {card_number}")
        return {"message": "Пропуск успешно удален"}
    logger.log(f"Попытка удаления несуществующего пропуска: {card_number}")
    raise HTTPException(status_code=404, detail="Пропуск не найден")


@app.put("/passes/{card_number}", response_model=PassInDB)
async def update_pass(card_number: str, pass_data: PassUpdate, db: Session = Depends(get_db)):
    db_pass = db.query(Pass).filter(Pass.card_number == card_number).first()
    if db_pass:
        for key, value in pass_data.dict(exclude_unset=True).items():
            setattr(db_pass, key, value)
        db.commit()
        db.refresh(db_pass)
        logger.log(f"Обновлен пропуск: {card_number}")
        return db_pass
    logger.log(f"Попытка обновления несуществующего пропуска: {card_number}")
    raise HTTPException(status_code=404, detail="Пропуск не найден")


@app.get("/open-door/")
async def open_door_command():
    try:
        response = await arduino_controller.open_door()
        await asyncio.sleep(settings.DOOR_OPEN_DURATION)
        logger.log(f"Дверь открыта. Ответ Arduino: {response}")
        return {"message": "Дверь открыта и закрыта"}
    except Exception as e:
        logger.log(f"Ошибка при открытии двери: {str(e)}")
        return {"error": f"Не удалось выполнить команду: {str(e)}"}


@app.get("/wait-for-card")
async def wait_for_card():
    try:
        card_number = await asyncio.wait_for(new_card_queue.get(), timeout=30.0)
        return {"card_number": card_number}
    except asyncio.TimeoutError:
        return {"error": "Время ожидания новой карты истекло"}
    except Exception as e:
        return {"error": f"Произошла ошибка при ожидании карты: {str(e)}"}


async def process_nfc_data(card_number: str):
    db = next(get_db())
    try:
        await check_pass_and_open_door(card_number, db)
    finally:
        db.close()


async def nfc_processing_task():
    while True:
        try:
            data = await arduino_controller._read_serial()
            if data.startswith("NFC:"):
                card_number = data[4:].strip()
                if card_number =='reinitialized':
                    logger.log(f"Модуль NFC переинициализирован", "ARDUINO")
                else:
                    logger.log(f"Считали карту: {card_number}", "ARDUINO")
                    await process_nfc_data(card_number)
                    try:
                        new_card_queue.put_nowait(card_number)

                    except asyncio.QueueFull:
                        # Если очередь полна, удаляем старое значение и добавляем новое
                        _ = new_card_queue.get_nowait()
                        new_card_queue.put_nowait(card_number)
        except Exception as e:
            logger.log(f"Ошибка в nfc_processing_task: {e}", "ARDUINO")
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    init(autoreset=True)
    print(Fore.LIGHTGREEN_EX + logo)
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)