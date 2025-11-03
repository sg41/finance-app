# create_test_user.py
import sys
from sqlalchemy.orm import Session
import models
from database import SessionLocal, engine

def reset_database():
    """
    Полностью удаляет все таблицы и создает их заново,
    а затем добавляет одного тестового пользователя.
    """
    # --- Блок безопасности ---
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("!! ВНИМАНИЕ: Этот скрипт ПОЛНОСТЬЮ УНИЧТОЖИТ все данные !!")
    print("!! в таблицах (users, connected_banks) и создаст их заново. !!")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    
    confirmation = input("Вы уверены, что хотите продолжить? (y/n): ")
    if confirmation.lower() != 'y':
        print("Операция отменена.")
        sys.exit() # Выходим из скрипта

    print("\nНачинаем процесс сброса базы данных...")
    
    db: Session = SessionLocal()
    
    try:
        # 1. Удаление всех таблиц, известных Base.metadata
        print("-> Удаляю старые таблицы...")
        models.Base.metadata.drop_all(bind=engine)
        print("   ...старые таблицы успешно удалены.")

        # 2. Создание всех таблиц заново
        print("-> Создаю новые таблицы...")
        models.Base.metadata.create_all(bind=engine)
        print("   ...новые таблицы успешно созданы.")

        # 3. Создание тестового пользователя
        print("-> Создаю тестового пользователя с ID=1...")
        # ID указывается вручную, чтобы он был предсказуемым для тестов
        # full_name=None, так как имя мы получаем позже из API
        new_user = models.User(id=1, email="testuser@example.com")
        db.add(new_user)
        db.commit()
        print("   ...тестовый пользователь успешно создан!")
        
        print("\nПроцесс сброса и инициализации базы данных успешно завершен!")

    except Exception as e:
        print(f"\nПроизошла ошибка во время сброса базы данных: {e}")
        db.rollback() # Откатываем транзакцию в случае ошибки
    finally:
        db.close() # Всегда закрываем сессию

if __name__ == "__main__":
    reset_database()