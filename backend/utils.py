# finance-app-master/utils.py
import httpx
import logging
from sqlalchemy.orm import Session
from typing import Optional, Dict
from datetime import datetime, timedelta

from fastapi import HTTPException
import models
from models import ConnectedBank, Bank


logger = logging.getLogger("uvicorn")
def log_request(request: httpx.Request): logger.info(f"--> {request.method} {request.url}\n    Headers: {request.headers}\n    Body: {request.content.decode() if request.content else ''}")
def log_response(response: httpx.Response): logger.info(f"<-- {response.status_code} URL: {response.url}\n    Response JSON: {response.text}")


# --- ПЕРЕНЕСЕНО ИЗ main.py ---
BANK_TOKEN_CACHE: Dict[str, Dict] = {}

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
# --- КОНЕЦ ПЕРЕНЕСЕННОГО КОДА ---


async def revoke_bank_consent(connection: ConnectedBank, db: Session) -> None:
    """
    Отзывает согласие (consent или request) в банке по данным подключения.
    """
    id_to_revoke = connection.consent_id or connection.request_id
    if not id_to_revoke:
        return

    bank_name = connection.bank_name
    config = db.query(Bank).filter(Bank.name == bank_name).first()
    if not config:
        logger.warning(f"Bank config for '{bank_name}' not found in DB for conn {connection.id}. Skipping revocation.")
        return

    revoke_url = f"{config.base_url.strip()}/account-consents/{id_to_revoke}"
    headers = {"x-fapi-interaction-id": config.client_id}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(revoke_url, headers=headers)
        logger.info(f"Revoked consent {id_to_revoke} at {revoke_url}: status {response.status_code}")
        if response.status_code not in (204, 404):
            logger.error(f"Unexpected status on revoke: {response.status_code}, body: {response.text}")
    except Exception as e:
        logger.error(f"Failed to revoke consent {id_to_revoke} for bank {bank_name}: {e}")