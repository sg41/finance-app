# finance-app-master/schemas.py
from pydantic import BaseModel, field_validator, Field
from typing import Optional

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