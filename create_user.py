import asyncio
import getpass
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from src.core.config import get_settings

from src.core.password import get_password_hash
from src.models.shop_models import User, Base

settings = get_settings()
DATABASE_URL = settings.DATABASE_URL

async def create_superuser():
    """
    Асинхронный скрипт для создания суперпользователя (администратора).
    """
    print("--- Создание суперпользователя ---")

    username = input("Введите имя пользователя (admin): ") or "admin"
    password = getpass.getpass("Введите пароль: ")
    if not password:
        print("Пароль не может быть пустым. Выход.")
        return

    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        try:
            stmt = select(User).where(User.username == username)
            result = await db.execute(stmt)
            existing_user = result.scalars().first()

            if existing_user:
                print(f"Ошибка: Пользователь с именем '{username}' уже существует.")
                return

            hashed_password = get_password_hash(password)
            new_user = User(
                username=username,
                hashed_password=hashed_password,
                is_active=True,
                is_staff=True,
            )
            db.add(new_user)
            await db.commit()
            print(f"Пользователь '{username}' успешно создан!")

        except Exception as e:
            await db.rollback()
            print(f"Произошла ошибка: {e}")
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_superuser())