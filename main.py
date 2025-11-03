# main.py
import os
import secrets
import httpx
import logging # 1. Импортируем модуль логгирования
from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import models
from database import engine, get_db
from encryption_service import encrypt_data, decrypt_data

# 2. Настраиваем базовую конфигурацию логгирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

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
    # ... другие банки
}

def log_request(request: httpx.Request):
    """Функция для красивого вывода информации о запросе."""
    logging.info(f"--> {request.method} {request.url}")
    logging.info(f"    Headers: {request.headers}")
    if request.content:
        logging.info(f"    Body: {request.content.decode()}")

def log_response(response: httpx.Response):
    """Функция для красивого вывода информации об ответе."""
    logging.info(f"<-- {response.status_code} {response.reason_phrase} URL: {response.url}")
    try:
        logging.info(f"    Response JSON: {response.json()}")
    except Exception:
        logging.info(f"    Response Text: {response.text}")

# --- Вспомогательные функции ---

async def get_bank_token(bank_name: str) -> str:
    """Получает технический токен для нашего приложения."""
    cache_entry = BANK_TOKEN_CACHE.get(bank_name)
    if cache_entry and cache_entry["expires_at"] > datetime.utcnow():
        return cache_entry["token"]

    config = BANK_CONFIGS[bank_name]
    token_url = f"{config['base_url']}/auth/bank-token"
    params = {"client_id": config['client_id'], "client_secret": config['client_secret']}

    async with httpx.AsyncClient() as client:
        # --- ОТЛАДКА ---
        request = client.build_request("POST", token_url, params=params)
        log_request(request)
        # --- КОНЕЦ ОТЛАДКИ ---
        
        response = await client.send(request)
        
        # --- ОТЛАДКА ---
        log_response(response)
        # --- КОНЕЦ ОТЛАДКИ ---

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to get bank token: {response.text}")
    
    token_data = response.json()
    BANK_TOKEN_CACHE[bank_name] = {
        "token": token_data['access_token'],
        "expires_at": datetime.utcnow() + timedelta(seconds=token_data['expires_in'] - 60)
    }
    return token_data['access_token']

async def fetch_accounts(user_access_token: str, bank_name: str) -> dict:
    """Используя токен пользователя, запрашивает список его счетов."""
    config = BANK_CONFIGS[bank_name]
    accounts_url = f"{config['base_url']}/accounts"
    headers = {"Authorization": f"Bearer {user_access_token}", "X-Requesting-Bank": config['client_id']}
    
    async with httpx.AsyncClient() as client:
        # --- ОТЛАДКА ---
        request = client.build_request("GET", accounts_url, headers=headers)
        log_request(request)
        # --- КОНЕЦ ОТЛАДКИ ---
        
        response = await client.send(request)
        
        # --- ОТЛАДКА ---
        log_response(response)
        # --- КОНЕЦ ОТЛАДКИ ---

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to fetch accounts: {response.text}")
    
    return response.json()

# --- API Эндпоинты ---

@app.post("/connect/{bank_name}")
async def connect_bank_and_fetch_data(bank_name: str, db: Session = Depends(get_db)):
    if bank_name not in BANK_CONFIGS:
        raise HTTPException(status_code=404, detail="Bank not found")
    
    config = BANK_CONFIGS[bank_name]
    bank_access_token = await get_bank_token(bank_name)
    
    # --- Шаг 1: Создаем согласие ---
    consent_url = f"{config['base_url']}/account-consents/request"
    headers = {"Authorization": f"Bearer {bank_access_token}", "Content-Type": "application/json", "X-Requesting-Bank": config['client_id']}
    consent_body = {"client_id": f"{config['client_id']}-1", "permissions": ["ReadAccountsDetail", "ReadBalances", "ReadTransactionsDetail"], "reason": "Агрегация счетов для FinApp", "requesting_bank": "FinApp"}
    
    async with httpx.AsyncClient() as client:
        # --- ОТЛАДКА ---
        request = client.build_request("POST", consent_url, headers=headers, json=consent_body)
        log_request(request)
        # --- КОНЕЦ ОТЛАДКИ ---
        
        response = await client.post(consent_url, headers=headers, json=consent_body)
        
        # --- ОТЛАДКА ---
        log_response(response)
        # --- КОНЕЦ ОТЛАДКИ ---

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to create consent: {response.text}")

    consent_data = response.json()
    consent_id = consent_data['consent_id']

    if not consent_data.get("auto_approved"):
        raise HTTPException(status_code=501, detail="Manual approval flow is not implemented yet.")

    # --- Шаг 3: Обмен согласия на токен пользователя ---
    token_url = f"{config['base_url']}/auth/token"
    token_data = {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": consent_id}
    auth = (config['client_id'], config['client_secret'])

    # ИЗМЕНЕНИЕ: Мы передаем `auth` прямо в конструктор клиента.
    # Теперь этот клиент будет автоматически применять аутентификацию ко всем запросам.
    async with httpx.AsyncClient(auth=auth) as client:
        # --- ОТЛАДКА ---
        # Теперь `build_request` не нуждается в `auth`, так как он уже настроен в клиенте.
        request = client.build_request("POST", token_url, data=token_data)
        log_request(request)
        # --- КОНЕЦ ОТЛАДКИ ---
        
        # Аналогично, `post` тоже больше не нуждается в `auth`.
        response = await client.post(token_url, data=token_data)
        
        # --- ОТЛАДКА ---
        log_response(response)
        # --- КОНЕЦ ОТЛАДКИ ---

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to exchange consent for token: {response.text}")
    
    token_json = response.json()
    user_access_token = token_json['access_token']

    # --- Шаг 4: Сохраняем подключение и токены в БД ---
    user_id = 1
    new_connection = models.ConnectedBank(user_id=user_id, bank_name=bank_name, consent_id=consent_id, status="active")
    db.add(new_connection)
    db.commit()
    db.refresh(new_connection)
    new_token = models.AuthToken(
        connection_id=new_connection.id,
        encrypted_access_token=encrypt_data(token_json['access_token']),
        encrypted_refresh_token=encrypt_data(token_json['refresh_token']),
        expires_at=datetime.utcnow() + timedelta(seconds=token_json['expires_in'])
    )
    db.add(new_token)
    db.commit()

    # --- Шаг 5: Сразу запрашиваем данные по счетам! ---
    accounts_data = await fetch_accounts(user_access_token, bank_name)
    
    return {"status": "success", "message": f"Bank {bank_name} connected and accounts fetched successfully!", "accounts_data": accounts_data}