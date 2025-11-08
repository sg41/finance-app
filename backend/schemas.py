# finance-app-master/schemas.py
from pydantic import BaseModel, field_validator, Field
from typing import Optional, List, Any
from datetime import datetime
from decimal import Decimal

class UserCreate(BaseModel):
    email: str
    password: str

    @field_validator('password')
    def password_not_too_long(cls, v):
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Password must be at most 72 bytes long')
        return v


class UserLogin(BaseModel):
    username: str = Field(alias="email")
    password: str

    class Config:
        populate_by_name = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenWithUser(Token):
    user_id: int

class UserResponse(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    count: int
    users: list[UserResponse]


class UserUpdateAdmin(BaseModel):
    email: Optional[str] = None
    is_admin: Optional[bool] = None

# --- НОВЫЕ СХЕМЫ ДЛЯ БАНКОВ ---
class BankResponse(BaseModel):
    id: int
    name: str
    base_url: str
    auto_approve: bool
    icon_url: Optional[str] = None # <-- Оставляем это поле как было
    
    class Config:
        from_attributes = True

class BankListResponse(BaseModel):
    count: int
    banks: list[BankResponse]

class AccountSchema(BaseModel):
    id: int
    connection_id: int
    api_account_id: str
    status: Optional[str] = None
    currency: Optional[str] = None
    account_type: Optional[str] = None
    account_subtype: Optional[str] = None
    nickname: Optional[str] = None
    opening_date: Optional[str] = None
    owner_data: Optional[Any] = None
    balance_data: Optional[Any] = None
    
    # Поля, которые мы добавим вручную в эндпоинте
    bank_client_id: str
    bank_name: str

    class Config:
        from_attributes = True

class AccountListResponse(BaseModel):
    count: int
    accounts: List[AccountSchema]

# --- vvv НОВЫЕ СХЕМЫ ДЛЯ ТРАНЗАКЦИЙ vvv ---
class TransactionAmountDetail(BaseModel):
    amount: str
    currency: str

class BankTransactionCodeDetail(BaseModel):
    code: str

class TransactionDetail(BaseModel):
    accountId: str
    transactionId: str
    transactionOinf: Optional[str] = None
    amount: TransactionAmountDetail
    creditDebitIndicator: str
    status: str
    bookingDateTime: datetime
    valueDateTime: datetime
    transactionInformation: Optional[str] = None
    bankTransactionCode: Optional[BankTransactionCodeDetail] = None
    code: Optional[str] = None

class TransactionListData(BaseModel):
    transaction: List[TransactionDetail]

class TransactionListResponse(BaseModel):
    data: TransactionListData
# --- ^^^ КОНЕЦ НОВЫХ СХЕМ ^^^ ---

class TurnoverResponse(BaseModel):
    account_id: str
    total_credit: Decimal = Field(..., description="Общая сумма поступлений (приход)")
    total_debit: Decimal = Field(..., description="Общая сумма списаний (расход)")
    currency: str
    period_from: Optional[datetime] = None
    period_to: Optional[datetime] = None