import asyncio
import re
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

sys.path.append('.')

from src.core.config import get_settings
from src.models.shop_models import Contact

settings = get_settings()
DATABASE_URL = settings.DATABASE_URL

def normalize_phone_number(phone: str) -> str:
    """Приводит номер телефона к единому формату E.164 (+998...)."""
    if not phone:
        return phone
    
    digits = re.sub(r'\D', '', phone)
    
    if len(digits) == 12 and digits.startswith('998'):
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
        
    return phone # Возвращаем без изменений, если формат не подходит

async def run_normalization():
    """Асинхронный скрипт для нормализации номеров телефонов в базе данных."""
    print("--- Запуск нормализации номеров телефонов ---")
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        try:
            stmt = select(Contact)
            result = await db.execute(stmt)
            contacts = result.scalars().all()
            
            print(f"Найдено {len(contacts)} контактов для проверки.")
            updated_count = 0
            
            for contact in contacts:
                original_phone = contact.phone
                normalized_phone = normalize_phone_number(original_phone)
                
                if original_phone != normalized_phone:
                    print(f"  Обновление: '{original_phone}' -> '{normalized_phone}'")
                    contact.phone = normalized_phone
                    db.add(contact)
                    updated_count += 1

            if updated_count > 0:
                await db.commit()
                print(f"\nУспешно обновлено {updated_count} номеров.")
            else:
                print("\nВсе номера уже в правильном формате. Обновление не требуется.")

        except Exception as e:
            await db.rollback()
            print(f"Произошла ошибка: {e}")
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_normalization())