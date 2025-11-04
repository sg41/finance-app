# finance-app-master/utils.py
import httpx
import logging
from sqlalchemy.orm import Session
from typing import Optional

from models import ConnectedBank, Bank
from database import get_db

logger = logging.getLogger("uvicorn")
def log_request(request: httpx.Request): logger.info(f"--> {request.method} {request.url}\n    Headers: {request.headers}\n    Body: {request.content.decode() if request.content else ''}")
def log_response(response: httpx.Response): logger.info(f"<-- {response.status_code} URL: {response.url}\n    Response JSON: {response.text}")

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