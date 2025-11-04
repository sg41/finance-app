# finance-app-master/banks_api.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models
from database import get_db
from schemas import BankListResponse

router = APIRouter(prefix="/banks", tags=["banks"])

@router.get("/", response_model=BankListResponse, summary="Получить список доступных банков")
def get_available_banks(db: Session = Depends(get_db)):
    """
    Возвращает список всех поддерживаемых банков, с которыми
    можно установить соединение.
    """
    banks = db.query(models.Bank).all()
    return {"count": len(banks), "banks": banks}