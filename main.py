# main.py
import os
import secrets
import httpx
import logging
from datetime import datetime, timedelta
from typing import Dict

from pydantic import BaseModel
from fastapi import FastAPI, APIRouter, Depends, HTTPException
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

app = FastAPI(
    title="FinApp API",
    version="1.0.0",
    description="API для подключения банковских счетов и управления финансовыми данными."
)

router = APIRouter(
    prefix="/users/{user_id}/connections",
    tags=["connections"]
)

BANK_TOKEN_CACHE: Dict[str, Dict] = {}
BANK_CONFIGS = {
    "vbank": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "base_url": "https://vbank.open.bankingapi.ru", "auto_approve": True},
    "abank": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "base_url": "https://abank.open.bankingapi.ru", "auto_approve": True},
    "sbank": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "base_url": "https://sbank.open.bankingapi.ru", "auto_approve": False}
}

class ConnectionRequest(BaseModel):
    bank_name: str
    bank_client_id: str

# --- Вспомогательные функции (без изменений) ---
def log_request(request: httpx.Request): logger.info(f"--> {request.method} {request.url}\n    Headers: {request.headers}\n    Body: {request.content.decode() if request.content else ''}")
def log_response(response: httpx.Response): logger.info(f"<-- {response.status_code} URL: {response.url}\n    Response JSON: {response.text}")
async def get_bank_token(bank_name: str) -> str:
    config = BANK_CONFIGS[bank_name]
    cache_entry = BANK_TOKEN_CACHE.get(bank_name)
    if cache_entry and cache_entry["expires_at"] > datetime.utcnow(): return cache_entry["token"]
    token_url = f"{config['base_url']}/auth/bank-token"
    params = {"client_id": config['client_id'], "client_secret": config['client_secret']}
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, params=params)
    if response.status_code != 200: raise HTTPException(status_code=500, detail=f"Failed to get bank token: {response.text}")
    token_data = response.json()
    BANK_TOKEN_CACHE[bank_name] = {"token": token_data['access_token'], "expires_at": datetime.utcnow() + timedelta(seconds=token_data['expires_in'] - 60)}
    return token_data['access_token']
async def fetch_accounts(bank_access_token: str, consent_id: str, bank_client_id: str, bank_name: str) -> dict:
    config = BANK_CONFIGS[bank_name]
    accounts_url = f"{config['base_url']}/accounts"
    headers = {"Authorization": f"Bearer {bank_access_token}", "X-Requesting-Bank": config['client_id'], "X-Consent-Id": consent_id}
    params = {"client_id": bank_client_id}
    async with httpx.AsyncClient() as client:
        response = await client.get(accounts_url, headers=headers, params=params)
    if response.status_code != 200: raise HTTPException(status_code=500, detail=f"Failed to fetch accounts: {response.text}")
    return response.json()


# --- API Эндпоинты ---

@router.get("/", summary="Получить список всех подключений пользователя")
async def list_connections(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    connections = db.query(models.ConnectedBank).filter(models.ConnectedBank.user_id == user_id).all()
    return connections

@router.get("/check/{bank_name}/{bank_client_id}", summary="Проверить наличие подключения в БД")
async def check_connection_exists(user_id: int, bank_name: str, bank_client_id: str, db: Session = Depends(get_db)):
    if bank_name not in BANK_CONFIGS: raise HTTPException(status_code=404, detail=f"Bank '{bank_name}' not supported.")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    connection = db.query(models.ConnectedBank).filter(models.ConnectedBank.user_id == user_id, models.ConnectedBank.bank_name == bank_name, models.ConnectedBank.bank_client_id == bank_client_id).first()
    if connection: return {"status": "exists", "connection_id": connection.id, "connection_status": connection.status}
    else: raise HTTPException(status_code=404, detail="Connection not found.")

@router.post("/", summary="Инициировать подключение")
async def initiate_connection(user_id: int, connection_data: ConnectionRequest, db: Session = Depends(get_db)):
    bank_name = connection_data.bank_name
    bank_client_id = connection_data.bank_client_id
    if bank_name not in BANK_CONFIGS: raise HTTPException(status_code=404, detail=f"Bank '{bank_name}' not supported.")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    config = BANK_CONFIGS[bank_name]
    existing_connection = db.query(models.ConnectedBank).filter(models.ConnectedBank.user_id == user_id, models.ConnectedBank.bank_name == bank_name, models.ConnectedBank.bank_client_id == bank_client_id).first()
    if existing_connection: return {"status": "already_initiated", "message": "Connection has been already initiated.", "connection_id": existing_connection.id}
    bank_access_token = await get_bank_token(bank_name)
    consent_url = f"{config['base_url']}/account-consents/request"
    headers = {"Authorization": f"Bearer {bank_access_token}", "Content-Type": "application/json", "X-Requesting-Bank": config['client_id']}
    consent_body = {"client_id": bank_client_id, "permissions": ["ReadAccountsDetail", "ReadBalances", "ReadTransactionsDetail"], "reason": f"Агрегация счетов для {bank_client_id}", "requesting_bank": "FinApp"}
    async with httpx.AsyncClient() as client: response = await client.post(consent_url, headers=headers, json=consent_body)
    log_response(response)
    if response.status_code != 200: raise HTTPException(status_code=500, detail=f"Failed to create consent request: {response.text}")
    consent_data = response.json()
    if consent_data.get("auto_approved"):
        consent_id = consent_data['consent_id']
        connection = models.ConnectedBank(user_id=user_id, bank_name=bank_name, bank_client_id=bank_client_id, consent_id=consent_id, status="active")
        db.add(connection); db.commit()
        return {"status": "success_auto_approved", "message": "Connection created and auto-approved.", "connection_id": connection.id}
    else:
        request_id = consent_data['request_id']
        connection = models.ConnectedBank(user_id=user_id, bank_name=bank_name, bank_client_id=bank_client_id, request_id=request_id, status="awaitingauthorization")
        db.add(connection); db.commit()
        return {"status": "awaiting_authorization", "message": "Connection initiated. Please approve and check status.", "connection_id": connection.id}

# --- ИЗМЕНЕНИЕ: Путь изменен на `/{connection_id}` ---
@router.post("/{connection_id}", summary="Проверить статус согласия")
async def check_consent_status(user_id: int, connection_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    connection = db.query(models.ConnectedBank).filter(models.ConnectedBank.id == connection_id, models.ConnectedBank.user_id == user_id).first()
    if not connection: raise HTTPException(status_code=404, detail="Connection not found for this user.")
    if connection.status not in ["awaitingauthorization", "active"]: return {"status": connection.status, "message": f"Consent is in a final state: {connection.status}"}
    config = BANK_CONFIGS[connection.bank_name]
    bank_access_token = await get_bank_token(connection.bank_name)
    if connection.status == "awaitingauthorization":
        check_url = f"{config['base_url']}/account-consents/{connection.request_id}"
        headers = {"Authorization": f"Bearer {bank_access_token}", "X-Requesting-Bank": config['client_id']}
    else:
        check_url = f"{config['base_url']}/account-consents/{connection.consent_id}"
        headers = {"Authorization": f"Bearer {bank_access_token}", "x-fapi-interaction-id": config['client_id']}
    async with httpx.AsyncClient() as client: response = await client.get(check_url, headers=headers)
    log_response(response)
    if response.status_code != 200: raise HTTPException(status_code=500, detail=f"Failed to check consent status: {response.text}")
    consent_data = response.json().get("data", {})
    api_status = consent_data.get("status", "unknown").lower()
    if api_status == "authorized":
        if connection.status == "awaitingauthorization": connection.consent_id = consent_data['consentId']
        connection.status = "active"; db.commit()
        accounts_data = await fetch_accounts(bank_access_token, connection.consent_id, connection.bank_client_id, connection.bank_name)
        try:
            name = accounts_data.get("data", {}).get("account", [{}])[0].get("account", [{}])[0].get("name")
            if name and connection.full_name != name: connection.full_name = name; db.commit()
        except Exception: pass
        return {"status": "success_approved", "message": "Consent is active and data fetched!", "accounts_data": accounts_data}
    elif api_status == "rejected":
        connection.status = "rejected"; db.commit()
        return {"status": "rejected", "message": "User has rejected the consent request."}
    else:
        if connection.status != api_status: connection.status = api_status; db.commit()
        return {"status": api_status, "message": f"Consent status is '{api_status}'. Please try again later."}

@router.delete("/{connection_id}", summary="Удалить подключение")
async def delete_connection(user_id: int, connection_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    connection = db.query(models.ConnectedBank).filter(models.ConnectedBank.id == connection_id, models.ConnectedBank.user_id == user_id).first()
    if not connection: raise HTTPException(status_code=404, detail="Connection not found for this user.")
    id_to_revoke = connection.consent_id or connection.request_id
    if id_to_revoke:
        config = BANK_CONFIGS[connection.bank_name]
        revoke_url = f"{config['base_url']}/account-consents/{id_to_revoke}"
        headers = {"x-fapi-interaction-id": config['client_id']}
        async with httpx.AsyncClient() as client: response = await client.delete(revoke_url, headers=headers)
        log_response(response)
        if response.status_code not in [204, 404]: logger.error(f"Банк вернул непредвиденную ошибку при отзыве ресурса {id_to_revoke}: {response.text}")
    db.delete(connection)
    db.commit()
    return {"status": "deleted", "message": "Connection record successfully deleted from the database."}

app.include_router(router)