# models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

# models.py
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=True) # <-- ДОБАВЛЕНО ЭТО ПОЛЕ
    
class ConnectedBank(Base):
    __tablename__ = "connected_banks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    bank_name = Column(String, index=True)
    bank_client_id = Column(String, index=True) # <-- ДОБАВЛЕНО ЭТО ПОЛЕ
    consent_id = Column(String, unique=True)
    status = Column(String, default="active")
    
    user = relationship("User")
