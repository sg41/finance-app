# finance-app-master/create_test_user.py
import sys
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session

import backend.models as models
# from backend import models
from backend.database import SessionLocal, engine
from backend.security import get_password_hash

load_dotenv()

def reset_database():
    """
    Полностью удаляет все таблицы и создает их заново,
    а затем добавляет банки, одного тестового пользователя и одного администратора.
    """
    # --- Блок безопасности ---
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("!! ВНИМАНИЕ: Этот скрипт ПОЛНОСТЬЮ УНИЧТОЖИТ все данные !!")
    print("!! в таблицах (users, connected_banks, banks) и создаст их заново. !!")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    
    confirmation = input("Вы уверены, что хотите продолжить? (y/n): ")
    if confirmation.lower() != 'y':
        print("Операция отменена.")
        sys.exit()

    print("\nНачинаем процесс сброса базы данных...")
    
    db: Session = SessionLocal()
    
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    if not CLIENT_ID or not CLIENT_SECRET:
        print("!! ОШИБКА: CLIENT_ID и CLIENT_SECRET должны быть установлены в .env файле.")
        sys.exit()

    try:
        print("-> Удаляю старые таблицы...")
        models.Base.metadata.drop_all(bind=engine)
        print("   ...старые таблицы успешно удалены.")

        print("-> Создаю новые таблицы...")
        models.Base.metadata.create_all(bind=engine)
        print("   ...новые таблицы успешно созданы.")

        print("-> Добавляю информацию о банках...")
        banks_to_add = [
            # Теперь иконки не указываются здесь. Их нужно загружать через API.
            models.Bank(name="vbank", client_id=CLIENT_ID, client_secret=CLIENT_SECRET, base_url="https://vbank.open.bankingapi.ru", auto_approve=True),
            models.Bank(name="abank", client_id=CLIENT_ID, client_secret=CLIENT_SECRET, base_url="https://abank.open.bankingapi.ru", auto_approve=True),
            models.Bank(name="sbank", client_id=CLIENT_ID, client_secret=CLIENT_SECRET, base_url="https://sbank.open.bankingapi.ru", auto_approve=False)
        ]
        db.add_all(banks_to_add)
        print("   ...банки vbank, abank, sbank успешно добавлены (без иконок).")

        
        print("-> Создаю обычного тестового пользователя (ID=1)...")
        hashed_pw_user = get_password_hash("password")
        new_user = models.User(email="testuser@example.com", hashed_password=hashed_pw_user, is_admin=False)
        db.add(new_user)
        print("   ...обычный пользователь 'testuser@example.com' (пароль: 'password') успешно создан!")
        
        print("-> Создаю пользователя-администратора (ID=2)...")
        hashed_pw_admin = get_password_hash("adminpass")
        new_admin = models.User(email="admin@example.com", hashed_password=hashed_pw_admin, is_admin=True)
        db.add(new_admin)
        print("   ...администратор 'admin@example.com' (пароль: 'adminpass') успешно создан!")
        
        db.commit()
        
        print("\nПроцесс сброса и инициализации базы данных успешно завершен!")

    except Exception as e:
        print(f"\nПроизошла ошибка во время сброса базы данных: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_database()