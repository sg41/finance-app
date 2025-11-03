# models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    # ... другие поля пользователя

class ConnectedBank(Base):
    __tablename__ = "connected_banks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    bank_name = Column(String, index=True)
    consent_id = Column(String, unique=True)
    status = Column(String, default="active")
    
    user = relationship("User")
    tokens = relationship("AuthToken", back_populates="connection", uselist=False)

class AuthToken(Base):
    __tablename__ = "auth_tokens"
    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("connected_banks.id"))
    encrypted_access_token = Column(LargeBinary)
    encrypted_refresh_token = Column(LargeBinary)
    expires_at = Column(DateTime)

    connection = relationship("ConnectedBank", back_populates="tokens")