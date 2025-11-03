import os
import requests
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

BANK_URL = os.getenv("BANK_URL")
CLIENT_ID = os.getenv("CLIENT_ID", "test_client_id")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "test_client_secret")

# === 1. Получение токена ===
def get_access_token():
    url = f"{BANK_URL}/auth/bank-token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    resp = requests.post(url, data=data)
    resp.raise_for_status()
    return resp.json()["access_token"]

# === 2. Получение счетов ===
def get_accounts(token):
    url = f"{BANK_URL}/accounts"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()["accounts"]

# === 3. Получение договоров (agreements) ===
def get_agreements(token):
    url = f"{BANK_URL}/agreements"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()["agreements"]

# === 4. Получение транзакций по счёту ===
def get_transactions(token, account_id):
    url = f"{BANK_URL}/accounts/{account_id}/transactions"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()["transactions"]

# === 5. Анализ регулярных платежей из транзакций ===
def detect_recurring_payments(transactions, days_back=90):
    # Группируем по описанию/получателю и сумме
    groups = defaultdict(list)
    cutoff = datetime.now() - timedelta(days=days_back)

    for t in transactions:
        # Пропускаем доходы
        if t.get("amount", 0) >= 0:
            continue
        date = datetime.fromisoformat(t["bookingDate"])
        if date < cutoff:
            continue
        key = (t.get("creditorName", "Unknown"), abs(t["amount"]))
        groups[key].append(date)

    recurring = []
    for (creditor, amount), dates in groups.items():
        if len(dates) >= 2:
            # Простой расчёт периодичности: средний интервал
            sorted_dates = sorted(dates)
            intervals = [(sorted_dates[i] - sorted_dates[i-1]).days for i in range(1, len(sorted_dates))]
            avg_interval = sum(intervals) / len(intervals) if intervals else 30

            # Предположим, что следующий платёж примерно через тот же интервал
            next_date = sorted_dates[-1] + timedelta(days=round(avg_interval))
            recurring.append({
                "creditor": creditor,
                "amount": amount,
                "next_date": next_date.strftime("%Y-%m-%d"),
                "type": "recurring_payment",
                "source": "transaction_analysis"
            })
    return recurring

# === 6. Извлечение предстоящих платежей из договоров ===
def extract_payments_from_agreements(agreements):
    payments = []
    for ag in agreements:
        product_type = ag.get("productType", "").lower()
        if product_type in ["loan", "credit", "credit_card"]:
            # Условно считаем, что платёж ежемесячный
            # В реальности можно брать из schedule или paymentPlan
            start_date = ag.get("startDate", "2025-01-01")
            amount = ag.get("monthlyPayment", 0)
            if amount > 0:
                # Простой расчёт: следующий платёж — в этом месяце или следующем
                today = datetime.today()
                next_date = today.replace(day=5)  # допустим, 5-е число
                if next_date < today:
                    next_date = (today.replace(day=1) + timedelta(days=32)).replace(day=5)
                payments.append({
                    "creditor": ag.get("bankName", "Bank") + " " + ag.get("productName", "Loan"),
                    "amount": amount,
                    "next_date": next_date.strftime("%Y-%m-%d"),
                    "type": product_type,
                    "source": "agreement"
                })
    return payments

# === 7. Основной запуск ===
def main():
    print("🔍 Получение токена...")
    token = get_access_token()
    print("✅ Токен получен.")

    print("\n🏦 Получение счетов...")
    accounts = get_accounts(token)
    account_ids = [acc["accountId"] for acc in accounts]
    print(f"Найдено счетов: {len(accounts)}")

    print("\n📑 Получение договоров...")
    agreements = get_agreements(token)
    print(f"Найдено договоров: {len(agreements)}")

    all_transactions = []
    for acc_id in account_ids:
        print(f"  → Загрузка транзакций для счёта {acc_id[:8]}...")
        txs = get_transactions(token, acc_id)
        all_transactions.extend(txs)

    print(f"\n🧾 Всего транзакций: {len(all_transactions)}")

    # Анализ
    recurring_from_tx = detect_recurring_payments(all_transactions)
    payments_from_agr = extract_payments_from_agreements(agreements)

    all_payments = recurring_from_tx + payments_from_agr

    # Сортируем по дате
    all_payments.sort(key=lambda x: x["next_date"])

    # === Вывод в консоль (UI-аналог) ===
    print("\n" + "="*60)
    print("📅 ПРЕДСТОЯЩИЕ ПЛАТЕЖИ")
    print("="*60)
    for p in all_payments:
        print(f"• {p['next_date']} | {p['amount']:>8.2f} ₽ | {p['creditor']} ({p['type']})")
    print("="*60)

if __name__ == "__main__":
    main()