# finance-app-master/backend/transactions_api.py

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timezone, time
from decimal import Decimal

import models
from database import get_db
from deps import user_is_admin_or_self
from utils import get_bank_token
from schemas import TransactionListResponse, TurnoverResponse, TransactionDetail

router = APIRouter(
    prefix="/users/{user_id}/banks/{bank_id}/accounts",
    tags=["transactions"]
)


# --- НОВАЯ ЕДИНАЯ ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ВСЕХ ТРАНЗАКЦИЙ ---
async def _get_all_transactions_for_period(
    bank_access_token: str,
    bank_config: models.Bank,
    connection: models.ConnectedBank,
    api_account_id: str,
    from_dt: Optional[datetime],
    to_dt: Optional[datetime],
) -> List[TransactionDetail]:
    """
    Надежно и ОПТИМИЗИРОВАННО получает все транзакции за период.
    """
    transactions_url = f"{bank_config.base_url}/accounts/{api_account_id}/transactions"
    headers = {
        "Authorization": f"Bearer {bank_access_token}",
        "X-Requesting-Bank": bank_config.client_id,
        "X-Consent-Id": connection.consent_id,
        "Accept": "application/json"
    }
    
    # --- ГЛАВНОЕ ИЗМЕНЕНИЕ: Возвращаем передачу дат в API банка ---
    base_params = {"limit": 100}
    if from_dt:
        base_params["from_booking_date_time"] = from_dt.isoformat()
    if to_dt:
        # Для to_dt передаем саму дату, а для нашей внутренней фильтрации
        # будем использовать конец дня.
        base_params["to_booking_date_time"] = to_dt.isoformat()
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    from_utc = from_dt.replace(tzinfo=timezone.utc) if from_dt and from_dt.tzinfo is None else from_dt
    to_utc_inclusive = None
    if to_dt:
        end_of_day = datetime.combine(to_dt.date(), time.max)
        to_utc_inclusive = end_of_day.replace(tzinfo=timezone.utc) if end_of_day.tzinfo is None else end_of_day.astimezone(timezone.utc)

    all_transactions: List[TransactionDetail] = []
    processed_transaction_ids = set()
    page = 1

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            current_params = base_params.copy()
            current_params["page"] = page
            
            try:
                response = await client.get(transactions_url, headers=headers, params=current_params)
                response.raise_for_status()
                response_data = response.json()
                transactions_on_page = response_data.get("data", {}).get("transaction", [])
                
                if not transactions_on_page:
                    break
                
                num_processed_before = len(processed_transaction_ids)

                for trans_data in transactions_on_page:
                    try:
                        transaction_id = trans_data.get("transactionId")
                        if not transaction_id or transaction_id in processed_transaction_ids:
                            continue
                        
                        transaction = TransactionDetail(**trans_data)

                        # Внутренняя фильтрация остаётся как дополнительная проверка
                        is_in_date_range = True
                        if from_utc and transaction.bookingDateTime < from_utc:
                            is_in_date_range = False
                        if to_utc_inclusive and transaction.bookingDateTime > to_utc_inclusive:
                            is_in_date_range = False
                        
                        if is_in_date_range:
                            processed_transaction_ids.add(transaction_id)
                            all_transactions.append(transaction)
                            
                    except Exception:
                        continue
                
                if len(processed_transaction_ids) == num_processed_before:
                    break

                page += 1
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                raise Exception(f"Failed to fetch transactions from {connection.bank_name}: {e}")

    return all_transactions


# --- ОБНОВЛЕННАЯ ФУНКЦИЯ get_transactions ---
@router.get(
    "/{api_account_id}/transactions",
    response_model=TransactionListResponse,
    summary="Получить транзакции по ID счета и ID банка"
)
async def get_transactions(
    user_id: int,
    bank_id: int,
    api_account_id: str,
    from_booking_date_time: Optional[datetime] = Query(None, description="Начало периода в формате ISO 8601"),
    to_booking_date_time: Optional[datetime] = Query(None, description="Конец периода в формате ISO 8601"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(user_is_admin_or_self)
):
    bank = db.query(models.Bank).filter(models.Bank.id == bank_id).first()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank with the specified ID not found.")
    
    connection = db.query(models.ConnectedBank).join(models.Account).filter(
        models.Account.api_account_id == api_account_id,
        models.ConnectedBank.user_id == user_id,
        models.ConnectedBank.bank_name == bank.name
    ).first()

    if not connection or connection.status != "active" or not connection.consent_id:
        raise HTTPException(status_code=403, detail="Active connection with consent is required.")

    bank_access_token = await get_bank_token(connection.bank_name, db)

    try:
        all_transactions = await _get_all_transactions_for_period(
            bank_access_token=bank_access_token,
            bank_config=bank,
            connection=connection,
            api_account_id=api_account_id,
            from_dt=from_booking_date_time,
            to_dt=to_booking_date_time,
        )
        transactions_as_dicts = [t.model_dump() for t in all_transactions]
        return {"data": {"transaction": transactions_as_dicts}}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# --- ОБНОВЛЕННАЯ ФУНКЦИЯ get_account_turnover ---
@router.get(
    "/{api_account_id}/turnover",
    response_model=TurnoverResponse,
    summary="Получить обороты по ID счета и ID банка за период"
)
async def get_account_turnover(
    user_id: int,
    bank_id: int,
    api_account_id: str,
    from_booking_date_time: Optional[datetime] = Query(None, description="Начало периода в формате ISO 8601"),
    to_booking_date_time: Optional[datetime] = Query(None, description="Конец периода в формате ISO 8601"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(user_is_admin_or_self)
):
    bank = db.query(models.Bank).filter(models.Bank.id == bank_id).first()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank with the specified ID not found.")
    
    db_account = db.query(models.Account).join(models.ConnectedBank).filter(
        models.Account.api_account_id == api_account_id,
        models.ConnectedBank.user_id == user_id,
        models.ConnectedBank.bank_name == bank.name
    ).first()
    
    if not db_account:
        raise HTTPException(status_code=404, detail="Account not found for the specified bank or access denied.")

    bank_access_token = await get_bank_token(db_account.connection.bank_name, db)

    try:
        all_transactions = await _get_all_transactions_for_period(
            bank_access_token=bank_access_token,
            bank_config=bank,
            connection=db_account.connection,
            api_account_id=api_account_id,
            from_dt=from_booking_date_time,
            to_dt=to_booking_date_time,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
        
    total_credit = Decimal("0.0")
    total_debit = Decimal("0.0")
    currency = None

    for transaction in all_transactions:
        if currency is None and transaction.amount.currency:
            currency = transaction.amount.currency
        
        amount_decimal = Decimal(transaction.amount.amount)
        if transaction.creditDebitIndicator.lower() == 'credit':
            total_credit += amount_decimal
        elif transaction.creditDebitIndicator.lower() == 'debit':
            total_debit += amount_decimal

    return TurnoverResponse(
        account_id=api_account_id,
        total_credit=total_credit,
        total_debit=total_debit,
        currency=currency or db_account.currency or "N/A",
        period_from=from_booking_date_time,
        period_to=to_booking_date_time
    )