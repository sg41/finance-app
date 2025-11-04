# finance-app-master/banks_api.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
import models
from database import get_db
from schemas import BankListResponse, BankResponse
import shutil
import os
from typing import List
from starlette.requests import Request
from deps import get_current_user, get_current_admin_user

router = APIRouter(prefix="/banks", tags=["banks"])

ICON_DIR = "static/icons"
os.makedirs(ICON_DIR, exist_ok=True)

@router.post(
    "/{bank_id}/icon",
    summary="Загрузить иконку для банка (Только для администраторов)",
    tags=["banks"]
)
def upload_bank_icon(
    bank_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin_user)
):
    """
    Загружает файл иконки для указанного банка.
    Доступно только для администраторов.
    """
    bank = db.query(models.Bank).filter(models.Bank.id == bank_id).first()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
        
    # --- v-- ДОБАВЛЕНА ПРОВЕРКА --v ---
    # Проверяем, что файл был отправлен и имеет content_type
    if not file or not file.content_type:
         raise HTTPException(
            status_code=400, 
            detail="File is missing or is not a valid multipart upload."
        )
    # --- ^-- КОНЕЦ ПРОВЕРКИ --^ ---

    # Теперь эта проверка безопасна
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type, please upload an image.")

    file_extension = os.path.splitext(file.filename)[1]
    filename = f"{bank.name}{file_extension}"
    file_path = os.path.join(ICON_DIR, filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    bank.icon_filename = filename
    db.commit()

    return {"filename": filename, "path": f"/{file_path}"}


@router.get(
    "/",
    response_model=BankListResponse,
    summary="Получить список доступных банков (Для авторизованных пользователей)"
)
def get_available_banks(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Возвращает список всех поддерживаемых банков.
    Доступно для любого авторизованного пользователя.
    """
    banks_from_db = db.query(models.Bank).all()
    
    banks_with_urls = []
    for bank in banks_from_db:
        bank_data = bank.__dict__
        if bank.icon_filename:
            icon_url = f"{request.base_url}static/icons/{bank.icon_filename}"
            bank_data['icon_url'] = icon_url
        else:
            bank_data['icon_url'] = None
        banks_with_urls.append(bank_data)

    return {"count": len(banks_with_urls), "banks": banks_with_urls}