# manage_users.py
import argparse
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User

def set_admin_status(email: str, is_admin: bool):
    """Назначает или снимает права администратора для пользователя."""
    db: Session = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        print(f"❌ Ошибка: Пользователь с email '{email}' не найден.")
        return

    try:
        user.is_admin = is_admin
        db.commit()
        status = "администратором" if is_admin else "обычным пользователем"
        print(f"✅ Успех: Пользователь '{email}' теперь является {status}.")
    except Exception as e:
        db.rollback()
        print(f"🔥 Произошла ошибка: {e}")
    finally:
        db.close()

def list_admins():
    """Выводит список всех администраторов."""
    db: Session = SessionLocal()
    admins = db.query(User).filter(User.is_admin == True).all()
    db.close()
    
    if not admins:
        print("ℹ️ В системе нет администраторов.")
        return
        
    print("--- 👑 Список администраторов ---")
    for admin in admins:
        print(f"- {admin.email} (ID: {admin.id})")
    print("---------------------------------")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Управление ролями пользователей.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Команда для назначения админа
    promote_parser = subparsers.add_parser("promote", help="Назначить пользователя администратором.")
    promote_parser.add_argument("email", type=str, help="Email пользователя.")

    # Команда для снятия прав админа
    demote_parser = subparsers.add_parser("demote", help="Снять права администратора.")
    demote_parser.add_argument("email", type=str, help="Email пользователя.")
    
    # Команда для вывода списка админов
    list_parser = subparsers.add_parser("list", help="Показать всех администраторов.")

    args = parser.parse_args()

    if args.command == "promote":
        set_admin_status(args.email, is_admin=True)
    elif args.command == "demote":
        set_admin_status(args.email, is_admin=False)
    elif args.command == "list":
        list_admins()