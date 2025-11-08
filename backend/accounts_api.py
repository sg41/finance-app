# finance-app-master/accounts_api.py
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timezone
import models
from database import get_db
from deps import user_is_admin_or_self, get_current_user
from utils import get_bank_token
from decimal import Decimal
from schemas import AccountListResponse, TransactionListResponse, TurnoverResponse, TransactionDetail

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
    query = db.query(models.Account).join(models.ConnectedBank).filter(models.ConnectedBank.user_id == user_id)

    if bank_name:
        query = query.filter(models.ConnectedBank.bank_name == bank_name)
    
    if api_account_id:
        query = query.filter(models.Account.api_account_id == api_account_id)

    accounts_from_db = query.all()

    # --- vvv КЛЮЧЕВОЕ ИЗМЕНЕНИЕ vvv ---
    # Вручную создаем список словарей, чтобы Pydantic был доволен.
    
    accounts_data = []
    for acc in accounts_from_db:
        # Копируем атрибуты из объекта Account
        acc_dict = {
            "id": acc.id,
            "connection_id": acc.connection_id,
            "api_account_id": acc.api_account_id,
            "status": acc.status,
            "currency": acc.currency,
            "account_type": acc.account_type,
            "account_subtype": acc.account_subtype,
            "nickname": acc.nickname,
            "opening_date": acc.opening_date,
            "owner_data": acc.owner_data,
            "balance_data": acc.balance_data,
            # Явно добавляем данные из связанного объекта connection
            "bank_client_id": acc.connection.bank_client_id,
            "bank_name": acc.connection.bank_name,
        }
        accounts_data.append(acc_dict)

    # Передаем в Pydantic-модель уже подготовленный список словарей
    return AccountListResponse(count=len(accounts_data), accounts=accounts_data)
    # --- ^^^ КОНЕЦ ИЗМЕНЕНИЯ ^^^ ---

@router.get(
    "/{api_account_id}/transactions",
    response_model=TransactionListResponse,
    summary="Получить транзакции по счету из банка"
)
async def get_transactions(
    user_id: int,
    api_account_id: str,
    from_booking_date_time: Optional[datetime] = Query(None, description="Начало периода в формате ISO 8601"),
    to_booking_date_time: Optional[datetime] = Query(None, description="Конец периода в формате ISO 8601"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    #           vvv ИЗМЕНЕНИЕ ЗДЕСЬ vvv
    limit: int = Query(50, ge=1, le=100, description="Количество элементов на странице"),
    #           ^^^ ИЗМЕНЕНИЕ ЗДЕСЬ ^^^
    db: Session = Depends(get_db),
    current_user: models.User = Depends(user_is_admin_or_self)
):
    """
    Запрашивает и возвращает список транзакций для конкретного счета
    непосредственно из API банка.
    """
    db_account = db.query(models.Account).join(models.ConnectedBank).filter(
        models.Account.api_account_id == api_account_id,
        models.ConnectedBank.user_id == user_id
    ).first()

    if not db_account:
        raise HTTPException(status_code=404, detail="Account not found or access denied for this user.")

    connection = db_account.connection
    if not connection or connection.status != "active" or not connection.consent_id:
        raise HTTPException(status_code=403, detail="Active connection with consent is required to fetch transactions.")

    bank_config = db.query(models.Bank).filter(models.Bank.name == connection.bank_name).first()
    if not bank_config:
         raise HTTPException(status_code=500, detail="Bank configuration not found.")

    bank_access_token = await get_bank_token(connection.bank_name, db)

    headers = {
        "Authorization": f"Bearer {bank_access_token}",
        "X-Requesting-Bank": bank_config.client_id,
        "X-Consent-Id": connection.consent_id,
        "Accept": "application/json"
    }
    
    transactions_url = f"{bank_config.base_url}/accounts/{api_account_id}/transactions"
    
    params = {"page": page, "limit": limit}
    if from_booking_date_time:
        params["from_booking_date_time"] = from_booking_date_time.isoformat()
    if to_booking_date_time:
        params["to_booking_date_time"] = to_booking_date_time.isoformat()
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(transactions_url, headers=headers, params=params)
            response.raise_for_status()
            response_data = response.json()

            if (from_booking_date_time or to_booking_date_time) and "data" in response_data:
                original_transactions = response_data["data"].get("transaction", [])
                filtered_transactions = []
                
                from_utc = from_booking_date_time.replace(tzinfo=timezone.utc) if from_booking_date_time and from_booking_date_time.tzinfo is None else from_booking_date_time
                to_utc = to_booking_date_time.replace(tzinfo=timezone.utc) if to_booking_date_time and to_booking_date_time.tzinfo is None else to_booking_date_time

                for trans_data in original_transactions:
                    try:
                        transaction = TransactionDetail(**trans_data)
                        is_in_date_range = True
                        if from_utc and transaction.bookingDateTime < from_utc:
                            is_in_date_range = False
                        if to_utc and transaction.bookingDateTime > to_utc:
                            is_in_date_range = False
                        
                        if is_in_date_range:
                            filtered_transactions.append(trans_data)
                    except Exception:
                        continue 

                response_data["data"]["transaction"] = filtered_transactions
                
            return response_data

        except httpx.HTTPStatusError as e:
            error_detail = f"Error from bank API: {e.response.status_code} - {e.response.text}"
            raise HTTPException(status_code=e.response.status_code, detail=error_detail)
        except (httpx.RequestError, Exception) as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch transactions from {connection.bank_name}: {e}")

@router.get(
    "/{api_account_id}/turnover",
    response_model=TurnoverResponse,
    summary="Получить обороты (приход/расход) по счету за период"
)
async def get_account_turnover(
    user_id: int,
    api_account_id: str,
    from_booking_date_time: Optional[datetime] = Query(None, description="Начало периода в формате ISO 8601"),
    to_booking_date_time: Optional[datetime] = Query(None, description="Конец периода в формате ISO 8601"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(user_is_admin_or_self)
):
    """
    Рассчитывает и возвращает общую сумму поступлений и списаний по
    конкретному счету за указанный период, запрашивая все страницы
    транзакций из API банка.
    """
    db_account = db.query(models.Account).join(models.ConnectedBank).filter(
        models.Account.api_account_id == api_account_id,
        models.ConnectedBank.user_id == user_id
    ).first()
    if not db_account:
        raise HTTPException(status_code=404, detail="Account not found or access denied.")

    connection = db_account.connection
    if not connection or connection.status != "active" or not connection.consent_id:
        raise HTTPException(status_code=403, detail="Active connection with consent is required.")

    bank_config = db.query(models.Bank).filter(models.Bank.name == connection.bank_name).first()
    if not bank_config:
         raise HTTPException(status_code=500, detail="Bank configuration not found.")

    bank_access_token = await get_bank_token(connection.bank_name, db)

    headers = {
        "Authorization": f"Bearer {bank_access_token}",
        "X-Requesting-Bank": bank_config.client_id,
        "X-Consent-Id": connection.consent_id,
        "Accept": "application/json"
    }
    transactions_url = f"{bank_config.base_url}/accounts/{api_account_id}/transactions"
    
    #           vvv ИЗМЕНЕНИЕ ЗДЕСЬ vvv
    base_params = {"limit": 100} # Запрашиваем максимум для уменьшения числа запросов
    #           ^^^ ИЗМЕНЕНИЕ ЗДЕСЬ ^^^
    if from_booking_date_time:
        base_params["from_booking_date_time"] = from_booking_date_time.isoformat()
    if to_booking_date_time:
        base_params["to_booking_date_time"] = to_booking_date_time.isoformat()

    total_credit = Decimal("0.0")
    total_debit = Decimal("0.0")
    currency = None
    page = 1
    
    from_utc = from_booking_date_time.replace(tzinfo=timezone.utc) if from_booking_date_time and from_booking_date_time.tzinfo is None else from_booking_date_time
    to_utc = to_booking_date_time.replace(tzinfo=timezone.utc) if to_booking_date_time and to_booking_date_time.tzinfo is None else to_booking_date_time

    async with httpx.AsyncClient() as client:
        while True:
            current_params = base_params.copy()
            current_params["page"] = page
            
            try:
                response = await client.get(transactions_url, headers=headers, params=current_params)
                response.raise_for_status()
                response_data = response.json()
                transactions = response_data.get("data", {}).get("transaction", [])
                
                if not transactions:
                    break
                
                for trans_data in transactions:
                    try:
                        transaction = TransactionDetail(**trans_data)
                        
                        is_in_date_range = True
                        if from_utc and transaction.bookingDateTime < from_utc:
                            is_in_date_range = False
                        if to_utc and transaction.bookingDateTime > to_utc:
                            is_in_date_range = False
                        
                        if not is_in_date_range:
                            continue

                        if currency is None:
                            currency = transaction.amount.currency
                        
                        amount_decimal = Decimal(transaction.amount.amount)
                        if transaction.creditDebitIndicator.lower() == 'credit':
                            total_credit += amount_decimal
                        elif transaction.creditDebitIndicator.lower() == 'debit':
                            total_debit += amount_decimal
                            
                    except Exception:
                        continue

                page += 1

            except httpx.HTTPStatusError as e:
                error_detail = f"Error from bank API: {e.response.status_code} - {e.response.text}"
                raise HTTPException(status_code=e.response.status_code, detail=error_detail)
            except (httpx.RequestError, Exception) as e:
                raise HTTPException(status_code=502, detail=f"Failed to fetch transactions from {connection.bank_name}: {e}")

    return TurnoverResponse(
        account_id=api_account_id,
        total_credit=total_credit,
        total_debit=total_debit,
        currency=currency or db_account.currency or "N/A",
        period_from=from_booking_date_time,
        period_to=to_booking_date_time
    )