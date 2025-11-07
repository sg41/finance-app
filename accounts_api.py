# finance-app-master/accounts_api.py
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models
from database import get_db
from deps import user_is_admin_or_self
from utils import get_bank_token

router = APIRouter(
    prefix="/users/{user_id}/accounts",
    tags=["accounts"]
)

@router.get("/", summary="Получить все счета пользователя по всем подключенным банкам")
async def get_user_accounts(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(user_is_admin_or_self)
):
    """
    Собирает информацию о счетах и балансах для всех активных
    подключений пользователя.
    """
    connections = db.query(models.ConnectedBank).filter(
        models.ConnectedBank.user_id == user_id,
        models.ConnectedBank.status == "active"
    ).all()

    if not connections:
        return {"data": {"bank": []}}

    all_banks_data = []
    
    async with httpx.AsyncClient() as client:
        for conn in connections:
            bank_config = db.query(models.Bank).filter(models.Bank.name == conn.bank_name).first()
            if not bank_config or not conn.consent_id:
                continue

            bank_access_token = await get_bank_token(conn.bank_name, db)
            
            headers = {
                "Authorization": f"Bearer {bank_access_token}",
                "X-Requesting-Bank": bank_config.client_id,
                "X-Consent-Id": conn.consent_id,
                "Accept": "application/json" # Добавлен для соответствия curl
            }

            # --- v-- ИЗМЕНЕНИЕ ЗДЕСЬ --v ---
            # Добавляем 'client_id' из подключения как query-параметр
            params = {"client_id": conn.bank_client_id}
            
            accounts_url = f"{bank_config.base_url}/accounts"
            try:
                # Передаем 'params' в запрос
                accounts_response = await client.get(accounts_url, headers=headers, params=params)
                accounts_response.raise_for_status()
                accounts_json = accounts_response.json()
                accounts_list = accounts_json.get("data", {}).get("account", [])
            # --- ^-- КОНЕЦ ИЗМЕНЕНИЯ --^ ---
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                print(f"Error fetching accounts for {conn.bank_name}: {e}")
                continue

            accounts_with_balances = []
            for account in accounts_list:
                account_id = account.get("accountId")
                if not account_id:
                    continue

                balances_url = f"{bank_config.base_url}/accounts/{account_id}/balances"
                try:
                    # Также передаем 'params' в запрос баланса, если это необходимо
                    balances_response = await client.get(balances_url, headers=headers, params=params)
                    balances_response.raise_for_status()
                    balances_json = balances_response.json()
                    balances_list = balances_json.get("data", {}).get("balance", [])
                    account["balance"] = balances_list
                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    print(f"Error fetching balances for account {account_id}: {e}")
                    account["balance"] = []
                
                accounts_with_balances.append(account)
            
            all_banks_data.append({
                "name": conn.bank_name,
                "account": accounts_with_balances
            })

    return {"data": {"bank": all_banks_data}}