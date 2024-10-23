from sqlalchemy import Column, Integer, String, DateTime
from database import Base
from datetime import datetime

class Pass(Base):
    __tablename__ = "passes"
    id = Column(Integer, primary_key=True, index=True)
    card_number = Column(String, unique=True, index=True)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    last_used = Column(DateTime, nullable=True)