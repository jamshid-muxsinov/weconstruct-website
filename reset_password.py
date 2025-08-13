import asyncio
import getpass
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

sys.path.append('.')

from src.core.config import get_settings
from src.core.password import get_password_hash
from src.models.shop_models import User

settings = get_settings()
DATABASE_URL = settings.DATABASE_URL

async def reset_password():
    """Асинхронный скрипт для сброса пароля пользователя."""
    if len(sys.argv) < 2:
        print("Ошибка: Пожалуйста, укажите имя пользователя.")
        print("Пример: python reset_password.py admin")
        return

    username_to_reset = sys.argv[1]
    print(f"--- Сброс пароля для пользователя: {username_to_reset} ---")

    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        try:
            stmt = select(User).where(User.username == username_to_reset)
            result = await db.execute(stmt)
            user = result.scalars().first()

            if not user:
                print(f"Ошибка: Пользователь с именем '{username_to_reset}' не найден.")
                return

            new_password = getpass.getpass("Введите новый пароль: ")
            if not new_password:
                print("Пароль не может быть пустым. Выход.")
                return

            confirm_password = getpass.getpass("Повторите новый пароль: ")
            if new_password != confirm_password:
                print("Пароли не совпадают. Выход.")
                return

            user.hashed_password = get_password_hash(new_password)
            db.add(user)
            await db.commit()
            print(f"Пароль для пользователя '{username_to_reset}' успешно обновлен!")

        except Exception as e:
            await db.rollback()
            print(f"Произошла ошибка: {e}")
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(reset_password())