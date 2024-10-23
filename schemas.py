from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PassBase(BaseModel):
    card_number: str
    name: str
    expires_at: datetime

class PassCreate(PassBase):
    pass

class PassUpdate(BaseModel):
    name: Optional[str] = None
    expires_at: Optional[datetime] = None

class PassInDB(PassBase):
    id: int
    created_at: datetime
    last_used: Optional[datetime]

    class Config:
        orm_mode = True