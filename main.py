# finance-app-master/main.py
import os
import secrets
import httpx
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from pydantic import BaseModel
from fastapi import FastAPI, APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import models
from database import engine, get_db
from utils import revoke_bank_consent, log_response, logger
from auth import router as auth_router
from user_api import router as user_router
from banks_api import router as banks_router
from deps import user_is_admin_or_self

load_dotenv()

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

class ConnectionRequest(BaseModel):
    bank_name: str
    bank_client_id: str

async def get_bank_token(bank_name: str, db: Session) -> str:
    config = db.query(models.Bank).filter(models.Bank.name == bank_name).first()
    if not config:
        raise HTTPException(status_code=500, detail=f"Internal server error: Bank config for '{bank_name}' not found.")
    
    cache_entry = BANK_TOKEN_CACHE.get(bank_name)
    if cache_entry and cache_entry["expires_at"] > datetime.utcnow(): return cache_entry["token"]
    
    token_url = f"{config.base_url}/auth/bank-token"
    params = {"client_id": config.client_id, "client_secret": config.client_secret}
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, params=params)
    if response.status_code != 200: raise HTTPException(status_code=500, detail=f"Failed to get bank token: {response.text}")
    token_data = response.json()
    BANK_TOKEN_CACHE[bank_name] = {"token": token_data['access_token'], "expires_at": datetime.utcnow() + timedelta(seconds=token_data['expires_in'] - 60)}
    return token_data['access_token']

async def fetch_accounts(bank_access_token: str, consent_id: str, bank_client_id: str, bank_config: models.Bank) -> dict:
    accounts_url = f"{bank_config.base_url}/accounts"
    headers = {"Authorization": f"Bearer {bank_access_token}", "X-Requesting-Bank": bank_config.client_id, "X-Consent-Id": consent_id}
    params = {"client_id": bank_client_id}
    async with httpx.AsyncClient() as client:
        response = await client.get(accounts_url, headers=headers, params=params)
    if response.status_code != 200: raise HTTPException(status_code=500, detail=f"Failed to fetch accounts: {response.text}")
    return response.json()

@router.get("/", summary="Получить список всех подключений пользователя")
async def list_connections(
    user_id: int,
    db: Session = Depends(get_db),
    bank_name: Optional[str] = None,
    bank_client_id: Optional[str] = None,
    current_user: models.User = Depends(user_is_admin_or_self)
):
    query = db.query(models.ConnectedBank).filter(models.ConnectedBank.user_id == user_id)
    if bank_name:
        query = query.filter(models.ConnectedBank.bank_name == bank_name)
    if bank_client_id:
        query = query.filter(models.ConnectedBank.bank_client_id == bank_client_id)
    connections = query.all()
    return {"count": len(connections), "connections": connections}

@router.post("/", summary="Инициировать подключение")
async def initiate_connection(
    user_id: int,
    connection_data: ConnectionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(user_is_admin_or_self)
):
    bank_name = connection_data.bank_name
    bank_client_id = connection_data.bank_client_id
    config = db.query(models.Bank).filter(models.Bank.name == bank_name).first()
    if not config:
        raise HTTPException(status_code=404, detail=f"Bank '{bank_name}' not supported.")

    existing_connection = db.query(models.ConnectedBank).filter(models.ConnectedBank.user_id == current_user.id, models.ConnectedBank.bank_name == bank_name, models.ConnectedBank.bank_client_id == bank_client_id).first()
    
    if existing_connection: return {"status": "already_initiated", "message": "Connection has been already initiated.", "connection_id": existing_connection.id}
    
    bank_access_token = await get_bank_token(bank_name, db)
    consent_url = f"{config.base_url}/account-consents/request"
    headers = {"Authorization": f"Bearer {bank_access_token}", "Content-Type": "application/json", "X-Requesting-Bank": config.client_id}
    consent_body = {"client_id": bank_client_id, "permissions": ["ReadAccountsDetail", "ReadBalances", "ReadTransactionsDetail"], "reason": f"Агрегация счетов для {bank_client_id}", "requesting_bank": "FinApp"}
    async with httpx.AsyncClient() as client: response = await client.post(consent_url, headers=headers, json=consent_body)
    log_response(response)
    if response.status_code != 200: raise HTTPException(status_code=500, detail=f"Failed to create consent request: {response.text}")
    consent_data = response.json()
    if consent_data.get("auto_approved"):
        consent_id = consent_data['consent_id']
        connection = models.ConnectedBank(user_id=current_user.id, bank_name=bank_name, bank_client_id=bank_client_id, consent_id=consent_id, status="active")
        db.add(connection); db.commit()
        return {"status": "success_auto_approved", "message": "Connection created and auto-approved.", "connection_id": connection.id}
    else:
        request_id = consent_data['request_id']
        connection = models.ConnectedBank(user_id=current_user.id, bank_name=bank_name, bank_client_id=bank_client_id, request_id=request_id, status="awaitingauthorization")
        db.add(connection); db.commit()
        return {"status": "awaiting_authorization", "message": "Connection initiated. Please approve and check status.", "connection_id": connection.id}

@router.post("/{connection_id}", summary="Проверить статус согласия")
async def check_consent_status(
    user_id: int,
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(user_is_admin_or_self)
):
    connection = db.query(models.ConnectedBank).filter(models.ConnectedBank.id == connection_id, models.ConnectedBank.user_id == current_user.id).first()
    if not connection: raise HTTPException(status_code=404, detail="Connection not found for this user.")
    if connection.status not in ["awaitingauthorization", "active"]: return {"status": connection.status, "message": f"Consent is in a final state: {connection.status}"}
    
    config = db.query(models.Bank).filter(models.Bank.name == connection.bank_name).first()
    if not config:
        raise HTTPException(status_code=500, detail=f"Internal error: Bank config for '{connection.bank_name}' disappeared.")

    bank_access_token = await get_bank_token(connection.bank_name, db)
    if connection.status == "awaitingauthorization":
        check_url = f"{config.base_url}/account-consents/{connection.request_id}"
        headers = {"Authorization": f"Bearer {bank_access_token}", "X-Requesting-Bank": config.client_id}
    else:
        check_url = f"{config.base_url}/account-consents/{connection.consent_id}"
        headers = {"Authorization": f"Bearer {bank_access_token}", "x-fapi-interaction-id": config.client_id}
    async with httpx.AsyncClient() as client: response = await client.get(check_url, headers=headers)
    log_response(response)
    if response.status_code != 200: raise HTTPException(status_code=500, detail=f"Failed to check consent status: {response.text}")
    consent_data = response.json().get("data", {})
    api_status = consent_data.get("status", "unknown").lower()
    if api_status == "authorized":
        if connection.status == "awaitingauthorization": connection.consent_id = consent_data['consentId']
        connection.status = "active"; db.commit()
        accounts_data = await fetch_accounts(bank_access_token, connection.consent_id, connection.bank_client_id, config)
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
async def delete_connection(
    user_id: int,
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(user_is_admin_or_self)
):
    connection = db.query(models.ConnectedBank).filter(
        models.ConnectedBank.id == connection_id,
        models.ConnectedBank.user_id == current_user.id
    ).first()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found for this user.")
    
    await revoke_bank_consent(connection, db)
    db.delete(connection)
    db.commit()
    return {"status": "deleted", "message": "Connection record successfully deleted from the database."}

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(router)
app.include_router(banks_router)