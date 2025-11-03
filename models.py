# models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)

class ConnectedBank(Base):
    __tablename__ = "connected_banks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    bank_name = Column(String, index=True)
    bank_client_id = Column(String, index=True)
    
    # ИЗМЕНЕНИЕ 1: Добавляем поле для ID запроса
    request_id = Column(String, unique=True, nullable=True, index=True)
    
    # ИЗМЕНЕНИЕ 2: consent_id теперь может быть пустым (для статуса "pending")
    consent_id = Column(String, unique=True, nullable=True)
    
    status = Column(String, default="pending") # <-- Меняем статус по умолчанию
    full_name = Column(String, nullable=True)
    
    user = relationship("User")