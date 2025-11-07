# finance-app-master/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB # <-- ИМПОРТИРУЙТЕ JSONB
from database import Base

class Bank(Base):
    __tablename__ = "banks"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    client_id = Column(String, nullable=False)
    client_secret = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    auto_approve = Column(Boolean, default=False)
    icon_filename = Column(String, nullable=True)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_admin = Column(Boolean, default=False, server_default='f')
    
class ConnectedBank(Base):
    __tablename__ = "connected_banks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    bank_name = Column(String, index=True)
    bank_client_id = Column(String, index=True)
    request_id = Column(String, unique=True, nullable=True, index=True)
    consent_id = Column(String, unique=True, nullable=True)
    status = Column(String, default="awaitingauthorization")
    full_name = Column(String, nullable=True)
    
    user = relationship("User")
    # Добавим обратную связь, чтобы легко получать счета подключения
    accounts = relationship("Account", back_populates="connection", cascade="all, delete-orphan")

# v-- НОВАЯ МОДЕЛЬ ДЛЯ ХРАНЕНИЯ СЧЕТОВ --v
class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("connected_banks.id"), nullable=False)
    
    # Поля из API банка
    api_account_id = Column(String, index=True, nullable=False) # accountId
    status = Column(String)
    currency = Column(String(3))
    account_type = Column(String) # accountType
    account_subtype = Column(String) # accountSubType
    nickname = Column(String)
    opening_date = Column(String, nullable=True) # openingDate
    
    # Храним сложные структуры как JSON
    owner_data = Column(JSONB, nullable=True) # Содержимое "account": [...]
    balance_data = Column(JSONB, nullable=True) # Содержимое "balance": [...]

    connection = relationship("ConnectedBank", back_populates="accounts")
# --- КОНЕЦ НОВОЙ МОДЕЛИ ---