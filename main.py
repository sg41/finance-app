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
    "vbank": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "base_url": "https://vbank.open.bankingapi.ru", "auto_approve": True},
    "abank": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "base_url": "https://abank.open.bankingapi.ru", "auto_approve": True},
    "sbank": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "base_url": "https://sbank.open.bankingapi.ru", "auto_approve": False}
}

# ... (функции log_request, log_response, get_bank_token, fetch_accounts остаются без изменений) ...
def log_request(request: httpx.Request): logger.info(f"--> {request.method} {request.url}\n    Headers: {request.headers}\n    Body: {request.content.decode() if request.content else ''}")
def log_response(response: httpx.Response): logger.info(f"<-- {response.status_code} URL: {response.url}\n    Response JSON: {response.text}")
async def get_bank_token(bank_name: str) -> str:
    # ... без изменений ...
    cache_entry = BANK_TOKEN_CACHE.get(bank_name)
    if cache_entry and cache_entry["expires_at"] > datetime.utcnow(): return cache_entry["token"]
    config = BANK_CONFIGS[bank_name]
    token_url = f"{config['base_url']}/auth/bank-token"
    params = {"client_id": config['client_id'], "client_secret": config['client_secret']}
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, params=params)
    if response.status_code != 200: raise HTTPException(status_code=500, detail=f"Failed to get bank token: {response.text}")
    token_data = response.json()
    BANK_TOKEN_CACHE[bank_name] = {"token": token_data['access_token'], "expires_at": datetime.utcnow() + timedelta(seconds=token_data['expires_in'] - 60)}
    return token_data['access_token']
async def fetch_accounts(bank_access_token: str, consent_id: str, bank_client_id: str, bank_name: str) -> dict:
    # ... без изменений ...
    config = BANK_CONFIGS[bank_name]
    accounts_url = f"{config['base_url']}/accounts"
    headers = {"Authorization": f"Bearer {bank_access_token}", "X-Requesting-Bank": config['client_id'], "X-Consent-Id": consent_id}
    params = {"client_id": bank_client_id}
    async with httpx.AsyncClient() as client:
        response = await client.get(accounts_url, headers=headers, params=params)
    if response.status_code != 200: raise HTTPException(status_code=500, detail=f"Failed to fetch accounts: {response.text}")
    return response.json()


@app.post("/connect/{bank_name}/{client_suffix}", summary="Шаг 1: Инициировать подключение")
async def initiate_connection(bank_name: str, client_suffix: int, db: Session = Depends(get_db)):
    # ... (код функции почти тот же, что и в прошлый раз, но теперь он только создает запись) ...
    config = BANK_CONFIGS[bank_name]
    user_id = 1
    full_bank_client_id = f"{config['client_id']}-{client_suffix}"
    bank_access_token = await get_bank_token(bank_name)
    consent_url = f"{config['base_url']}/account-consents/request"
    headers = {"Authorization": f"Bearer {bank_access_token}", "Content-Type": "application/json", "X-Requesting-Bank": config['client_id']}
    consent_body = {"client_id": full_bank_client_id, "permissions": ["ReadAccountsDetail", "ReadBalances", "ReadTransactionsDetail"], "reason": f"Агрегация счетов для клиента {full_bank_client_id}", "requesting_bank": "FinApp"}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(consent_url, headers=headers, json=consent_body)
    log_response(response)
        
    if response.status_code != 200: raise HTTPException(status_code=500, detail=f"Failed to create consent: {response.text}")

    consent_data = response.json()

    if consent_data.get("auto_approved"):
        # ... (логика для vbank/abank) ...
        consent_id = consent_data['consent_id']
        connection = models.ConnectedBank(user_id=user_id, bank_name=bank_name, bank_client_id=full_bank_client_id, consent_id=consent_id, status="active")
        db.add(connection)
        db.commit()
        db.refresh(connection)
        accounts_data = await fetch_accounts(bank_access_token, consent_id, full_bank_client_id, bank_name)
        # ... (код обновления имени) ...
        try:
            name = accounts_data.get("data", {}).get("account", [{}])[0].get("account", [{}])[0].get("name")
            if name: connection.full_name = name; db.commit()
        except Exception: pass
        return {"status": "success_auto_approved", "connection_id": connection.id, "accounts_data": accounts_data}
    else:
        # --- Новая логика для SBank ---
        request_id = consent_data['request_id']
        connection = models.ConnectedBank(user_id=user_id, bank_name=bank_name, bank_client_id=full_bank_client_id, request_id=request_id, status="pending")
        db.add(connection)
        db.commit()
        db.refresh(connection)
        return {"status": "pending_manual_approval", "connection_id": connection.id, "message": "Connection initiated. Please approve on the bank's side and then check the status."}

@app.post("/check_consent/{connection_id}", summary="Шаг 2: Проверить статус согласия (для SBank)")
async def check_consent_status(connection_id: int, db: Session = Depends(get_db)):
    connection = db.query(models.ConnectedBank).filter(models.ConnectedBank.id == connection_id).first()
    if not connection: raise HTTPException(status_code=404, detail="Connection not found")
    if connection.status != "pending": return {"status": connection.status, "message": "Consent is not in a pending state."}
    
    config = BANK_CONFIGS[connection.bank_name]
    bank_access_token = await get_bank_token(connection.bank_name)
    
    check_url = f"{config['base_url']}/account-consents/{connection.request_id}"
    headers = {"Authorization": f"Bearer {bank_access_token}", "X-Requesting-Bank": config['client_id']}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(check_url, headers=headers)
    log_response(response)

    if response.status_code != 200: raise HTTPException(status_code=500, detail=f"Failed to check consent status: {response.text}")
    
    consent_data = response.json().get("data", {})
    
    # ИЗМЕНЕНИЕ: Приводим статус к нижнему регистру перед сравнением
    if consent_data.get("status", "").lower() == "authorized":
        consent_id = consent_data['consentId']
        connection.consent_id = consent_id
        connection.status = "active"
        db.commit()
        db.refresh(connection)
        
        accounts_data = await fetch_accounts(bank_access_token, consent_id, connection.bank_client_id, connection.bank_name)
        try:
            name = accounts_data.get("data", {}).get("account", [{}])[0].get("account", [{}])[0].get("name")
            if name: connection.full_name = name; db.commit()
        except Exception: pass
        
        return {"status": "success_approved", "message": "Consent approved and data fetched!", "accounts_data": accounts_data}
    else:
        return {"status": "still_pending", "message": "User has not approved the consent yet."}