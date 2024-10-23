import asyncio
from typing import Optional

import serial

from config import settings
from logger import logger


class ArduinoController:
    def __init__(self):
        self.port = settings.ARDUINO_PORT
        self.baudrate = settings.ARDUINO_BAUDRATE
        self.arduino: Optional[serial.Serial] = None
        self.read_task: Optional[asyncio.Task] = None

    async def connect(self):
        try:
            self.arduino = serial.Serial(self.port, self.baudrate, timeout=0)
            await asyncio.sleep(2)
            logger.log("Ожидание готовности Arduino...", "ARDUINO")
            await self._wait_for_ready()
            self.read_task = asyncio.create_task(self._read_serial())
        except Exception as e:
            logger.log(f"Ошибка при подключении к Arduino: {e}", "ARDUINO")
            raise

    async def _wait_for_ready(self):
        while True:
            if self.arduino.in_waiting:
                response = self.arduino.readline().decode().strip()
                if response == "Arduino ready":
                    logger.log("Arduino готова к работе.", "ARDUINO")
                    break
            await asyncio.sleep(0.1)

    async def disconnect(self):
        if self.read_task:
            self.read_task.cancel()
        if self.arduino:
            self.arduino.close()
            logger.log("Соединение с Arduino закрыто.", "ARDUINO")

    async def send_command(self, command: str) -> str:
        if not self.arduino:
            logger.log("Попытка отправить команду без подключения к Arduino", "ARDUINO")
            raise ConnectionError(
                "[!] Нет соединения с Arduino. Вызовите метод connect() сначала."
            )

        full_command = f"{command}\n"
        self.arduino.write(full_command.encode())
        logger.log(f"Отправлена команда: {command}", "ARDUINO")
        return await self._read_response()

    async def _read_response(self) -> str:
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < 7:
            if self.arduino.in_waiting:
                response = self.arduino.readline().decode().strip()
                if response:
                    logger.log(f"Получен ответ от Arduino: {response}", "ARDUINO")
                    return response
            await asyncio.sleep(0.1)
        logger.log("Таймаут при ожидании ответа от Arduino", "ARDUINO")
        return "Нет ответа от Arduino"

    async def _read_serial(self):
        if self.arduino.in_waiting:
            return self.arduino.readline().decode().strip()
        return ""

    async def open_door(self):
        response = await self.send_command("OpenDoor")
        logger.log(f"Попытка открыть дверь. Ответ Arduino: {response}", "ARDUINO")
        return response

    async def close_door(self):
        return await self.send_command("Blink")
