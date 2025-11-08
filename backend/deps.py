# deps.py
from fastapi import Depends, HTTPException, status, Path # <-- Добавьте Path
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
from models import User
from security import SECRET_KEY, ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User: 
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

# --- НОВАЯ ЗАВИСИМОСТЬ ---
def user_is_admin_or_self(
    user_id: int = Path(..., description="ID пользователя, к ресурсам которого осуществляется доступ"),
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Проверяет, является ли текущий пользователь администратором
    ИЛИ запрашивает свои собственные ресурсы.
    """
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted"
        )
    return current_user

# --- НОВАЯ ЗАВИСИМОСТЬ ДЛЯ АДМИНОВ ---
def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Проверяет, является ли текущий пользователь администратором.
    Если нет - выбрасывает исключение 403 Forbidden.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user