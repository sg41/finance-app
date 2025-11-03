# main.py
import os
import secrets
import httpx
import logging
from datetime import datetime, timedelta
from typing import Dict

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import models
from database import engine, get_db
from encryption_service import encrypt_data

logger = logging.getLogger("uvicorn")
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("CLIENT_ID и CLIENT_SECRET должны быть установлены в .env файле")

models.Base.metadata.create_all(bind=engine)
app = FastAPI()

BANK_TOKEN_CACHE: Dict[str, Dict] = {}

BANK_CONFIGS = {
    "vbank": {
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "base_url": "https://vbank.open.bankingapi.ru", "auto_approve": True
    },
}

# ... (функции log_request, log_response, get_bank_token, fetch_accounts остаются без изменений) ...
def log_request(request: httpx.Request):
    logger.info(f"--> {request.method} {request.url}")
    logger.info(f"    Headers: {request.headers}")
    if request.content:
        logger.info(f"    Body: {request.content.decode()}")

def log_response(response: httpx.Response):
    logger.info(f"<-- {response.status_code} {response.reason_phrase} URL: {response.url}")
    try: logger.info(f"    Response JSON: {response.json()}")
    except Exception: logger.info(f"    Response Text: {response.text}")

async def get_bank_token(bank_name: str) -> str:
    cache_entry = BANK_TOKEN_CACHE.get(bank_name)
    if cache_entry and cache_entry["expires_at"] > datetime.utcnow():
        return cache_entry["token"]
    config = BANK_CONFIGS[bank_name]
    token_url = f"{config['base_url']}/auth/bank-token"
    params = {"client_id": config['client_id'], "client_secret": config['client_secret']}
    async with httpx.AsyncClient() as client:
        request = client.build_request("POST", token_url, params=params)
        log_request(request)
        response = await client.send(request)
        log_response(response)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to get bank token: {response.text}")
    token_data = response.json()
    BANK_TOKEN_CACHE[bank_name] = {
        "token": token_data['access_token'],
        "expires_at": datetime.utcnow() + timedelta(seconds=token_data['expires_in'] - 60)
    }
    return token_data['access_token']

async def fetch_accounts(bank_access_token: str, consent_id: str, bank_client_id: str, bank_name: str) -> dict:
    """Запрашивает список счетов, используя технический токен, ID согласия и ID клиента."""
    config = BANK_CONFIGS[bank_name]
    accounts_url = f"{config['base_url']}/accounts"
    
    headers = {
        "Authorization": f"Bearer {bank_access_token}",
        "X-Requesting-Bank": config['client_id'],
        "X-Consent-Id": consent_id
    }
    
    # --- ИЗМЕНЕНИЕ 2: Добавляем ID клиента как query-параметр ---
    params = {
        "client_id": bank_client_id
    }
    
    async with httpx.AsyncClient() as client:
        # --- ИЗМЕНЕНИЕ 3: Передаем `params` в запрос ---
        request = client.build_request("GET", accounts_url, headers=headers, params=params)
        log_request(request)
        response = await client.send(request)
        log_response(response)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to fetch accounts: {response.text}")
    
    return response.json()


# main.py

# ... (весь код выше остается без изменений) ...

@app.post("/connect/{bank_name}/{client_suffix}")
async def connect_bank_and_fetch_data(bank_name: str, client_suffix: int, db: Session = Depends(get_db)):
    if bank_name not in BANK_CONFIGS:
        raise HTTPException(status_code=404, detail="Bank not found")

    config = BANK_CONFIGS[bank_name]
    user_id = 1
    full_bank_client_id = f"{config['client_id']}-{client_suffix}"

    # Шаг 1: Получаем токен и создаем согласие
    bank_access_token = await get_bank_token(bank_name)
    consent_url = f"{config['base_url']}/account-consents/request"
    headers = {"Authorization": f"Bearer {bank_access_token}", "Content-Type": "application/json", "X-Requesting-Bank": config['client_id']}
    consent_body = {"client_id": full_bank_client_id, "permissions": ["ReadAccountsDetail", "ReadBalances", "ReadTransactionsDetail"], "reason": f"Агрегация счетов для клиента {full_bank_client_id}", "requesting_bank": "FinApp"}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(consent_url, headers=headers, json=consent_body)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to create consent: {response.text}")
    consent_data = response.json()
    consent_id = consent_data['consent_id']
    if not consent_data.get("auto_approved"):
        raise HTTPException(status_code=501, detail="Manual approval flow is not implemented yet.")

    # --- ИЗМЕНЕНИЕ: Логика "Найти или Создать" ---
    
    # Шаг 2: Ищем подключение по УНИКАЛЬНОМУ consent_id
    connection = db.query(models.ConnectedBank).filter(
        models.ConnectedBank.consent_id == consent_id
    ).first()

    if connection:
        logger.info(f"Найдено существующее подключение с consent_id: {consent_id}. Будет обновлено.")
        status_message = "already_exists_updated"
    else:
        logger.info(f"Создается новое подключение с consent_id: {consent_id}.")
        # Если не найдено, создаем новый объект БЕЗ имени
        connection = models.ConnectedBank(
            user_id=user_id,
            bank_name=bank_name,
            bank_client_id=full_bank_client_id,
            consent_id=consent_id,
            status="active",
        )
        db.add(connection)
        db.commit() # Сохраняем "пустую" запись, чтобы она появилась в БД
        db.refresh(connection) # Обновляем объект, чтобы получить его ID из БД
        status_message = "success_created"

    # Шаг 3: Запрашиваем данные по счетам
    accounts_data = await fetch_accounts(bank_access_token, consent_id, full_bank_client_id, bank_name)

    # Шаг 4: Извлекаем имя и ОБНОВЛЯЕМ запись
    try:
        account_holder_name = accounts_data.get("data", {}).get("account", [{}])[0].get("account", [{}])[0].get("name")
        if account_holder_name and connection.full_name != account_holder_name:
            logger.info(f"Обновляем имя для consent_id {consent_id} на '{account_holder_name}'")
            connection.full_name = account_holder_name
            db.commit() # Сохраняем только изменение имени
    except (IndexError, KeyError, AttributeError) as e:
        logger.warning(f"Не удалось извлечь имя пользователя из данных по счетам: {e}")

    return {
        "status": status_message,
        "message": f"Bank client {full_bank_client_id} processed successfully!",
        "accounts_data": accounts_data
    }