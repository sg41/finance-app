# finance-app-master/accounts_api.py
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

import models
from database import get_db
from deps import user_is_admin_or_self, get_current_user
from utils import get_bank_token
from schemas import AccountListResponse # <-- Импортируем новую схему

router = APIRouter(
    prefix="/users/{user_id}/accounts",
    tags=["accounts"]
)

@router.post("/{connection_id}/refresh", summary="Обновить и сохранить счета из банка в БД")
async def refresh_and_save_accounts(
    user_id: int,
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Принудительно запрашивает данные о счетах и балансах у банка
    для конкретного подключения и сохраняет/обновляет их в базе данных.
    """
    # 1. Проверяем, что подключение существует и принадлежит пользователю
    conn = db.query(models.ConnectedBank).filter(
        models.ConnectedBank.id == connection_id,
        models.ConnectedBank.user_id == user_id
    ).first()

    if not conn or conn.status != "active" or not conn.consent_id:
        raise HTTPException(status_code=404, detail="Active connection not found or consent is missing.")

    bank_config = db.query(models.Bank).filter(models.Bank.name == conn.bank_name).first()
    if not bank_config:
         raise HTTPException(status_code=500, detail="Bank configuration not found.")

    # 2. Получаем данные от API банка
    bank_access_token = await get_bank_token(conn.bank_name, db)
    headers = {
        "Authorization": f"Bearer {bank_access_token}",
        "X-Requesting-Bank": bank_config.client_id,
        "X-Consent-Id": conn.consent_id,
        "Accept": "application/json"
    }
    params = {"client_id": conn.bank_client_id}
    
    accounts_list = []
    async with httpx.AsyncClient() as client:
        try:
            accounts_url = f"{bank_config.base_url}/accounts"
            accounts_response = await client.get(accounts_url, headers=headers, params=params)
            accounts_response.raise_for_status()
            accounts_list = accounts_response.json().get("data", {}).get("account", [])
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch accounts from {conn.bank_name}: {e}")

        # 3. Для каждого счета получаем баланс и сохраняем/обновляем в БД
        updated_count = 0
        created_count = 0
        for acc_data in accounts_list:
            api_acc_id = acc_data.get("accountId")
            if not api_acc_id:
                continue

            # Получаем баланс
            balances_list = []
            try:
                balances_url = f"{bank_config.base_url}/accounts/{api_acc_id}/balances"
                balances_response = await client.get(balances_url, headers=headers, params=params)
                balances_response.raise_for_status()
                balances_list = balances_response.json().get("data", {}).get("balance", [])
            except (httpx.RequestError, httpx.HTTPStatusError):
                pass # Игнорируем ошибку получения баланса, но продолжаем сохранять счет

            # Ищем счет в нашей БД
            db_account = db.query(models.Account).filter_by(api_account_id=api_acc_id, connection_id=conn.id).first()

            if db_account: # Обновляем существующий
                db_account.status = acc_data.get("status")
                db_account.currency = acc_data.get("currency")
                db_account.nickname = acc_data.get("nickname")
                db_account.owner_data = acc_data.get("account")
                db_account.balance_data = balances_list
                updated_count += 1
            else: # Создаем новый
                new_db_account = models.Account(
                    connection_id=conn.id,
                    api_account_id=api_acc_id,
                    status=acc_data.get("status"),
                    currency=acc_data.get("currency"),
                    account_type=acc_data.get("accountType"),
                    account_subtype=acc_data.get("accountSubType"),
                    nickname=acc_data.get("nickname"),
                    opening_date=acc_data.get("openingDate"),
                    owner_data=acc_data.get("account"),
                    balance_data=balances_list
                )
                db.add(new_db_account)
                created_count += 1
    
    db.commit()

    return {
        "status": "success",
        "message": f"Accounts for connection {connection_id} refreshed.",
        "created": created_count,
        "updated": updated_count
    }


@router.get("/", response_model=AccountListResponse, summary="Получить сохраненные счета из БД с фильтрацией")
def get_saved_accounts(
    user_id: int,
    bank_name: Optional[str] = Query(None, description="Фильтр по имени банка (vbank, abank, etc.)"),
    api_account_id: Optional[str] = Query(None, description="Фильтр по ID счета из API банка"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(user_is_admin_or_self)
):
    """
    Возвращает список счетов пользователя, сохраненных в базе данных.
    Доступна фильтрация по названию банка и ID счета.
    """
    # Начинаем запрос с join'ом, чтобы иметь доступ к данным подключения
    query = db.query(models.Account).join(models.ConnectedBank).filter(models.ConnectedBank.user_id == user_id)

    if bank_name:
        query = query.filter(models.ConnectedBank.bank_name == bank_name)
    
    if api_account_id:
        query = query.filter(models.Account.api_account_id == api_account_id)

    accounts = query.all()
    return AccountListResponse(count=len(accounts), accounts=accounts)