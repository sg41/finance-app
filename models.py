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
    consent_id = Column(String, unique=True)
    status = Column(String, default="active")
    full_name = Column(String, nullable=True) # <-- ДОБАВЛЯЕМ СЮДА
    
    user = relationship("User")