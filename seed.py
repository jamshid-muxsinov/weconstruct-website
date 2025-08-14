import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from slugify import slugify
import random

from src.core.config import settings
from src.models.shop_models import Category, Product, Base
from src.services.shop_service import process_quote_request

def get_async_database_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    return url

ASYNC_DB_URL = get_async_database_url(settings.DATABASE_URL)

CATEGORIES_DATA = [
    "Каркасные дома", "Модульные дома", "Дома из бруса", 
    "Бани и сауны", "Беседки и террасы"
]
PRODUCTS_DATA = {
    "Каркасные дома": [
        {"name": "Проект 'Сканди-120'", "price": 120000000, "area": 120},
        {"name": "Проект 'Лофт-90'", "price": 95000000, "area": 90},
        {"name": "Проект 'Шале-150'", "price": 155000000, "area": 150},
    ],
    "Модульные дома": [
        {"name": "Модуль 'ДубльДом-40'", "price": 45000000, "area": 40},
        {"name": "Модуль 'BoxHouse-65'", "price": 70000000, "area": 65},
    ],
}

async def seed_database():
    engine = create_async_engine(ASYNC_DB_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    print("Starting database seeding...")
    async with AsyncSessionLocal() as db:
        try:
            # --- ИСПРАВЛЕНИЕ ЗДЕСЬ: Мы будем хранить созданный товар ---
            target_product_id = None

            # 1. Создаем категории
            print("Creating categories...")
            created_categories = {}
            for cat_name in CATEGORIES_DATA:
                stmt = select(Category).where(Category.name == cat_name)
                result = await db.execute(stmt)
                existing_category = result.scalars().first()
                
                if not existing_category:
                    new_category = Category(name=cat_name, slug=slugify(cat_name))
                    db.add(new_category)
                    await db.flush()
                    created_categories[cat_name] = new_category
                    print(f"  - Category '{cat_name}' created.")
                else:
                    created_categories[cat_name] = existing_category
                    print(f"  - Category '{cat_name}' already exists.")
            
            await db.commit()

            # 2. Создаем товары
            print("\nCreating products...")
            for cat_name, products_list in PRODUCTS_DATA.items():
                if cat_name in created_categories:
                    category_obj = created_categories[cat_name]
                    for prod_data in products_list:
                        stmt = select(Product).where(Product.name == prod_data["name"])
                        result = await db.execute(stmt)
                        existing_product = result.scalars().first()

                        if not existing_product:
                            new_product = Product(
                                name=prod_data["name"],
                                slug=slugify(prod_data["name"]),
                                price=prod_data["price"],
                                area=prod_data["area"],
                                description=f"Отличный проект. Площадь: {prod_data['area']} кв.м.",
                                is_active=True,
                                status=random.choice(list(Product.StatusEnum)),
                                category_id=category_obj.id
                            )
                            db.add(new_product)
                            await db.flush() # Получаем ID
                            # Сохраняем ID первого созданного товара
                            if not target_product_id:
                                target_product_id = new_product.id
                            print(f"  - Product '{prod_data['name']}' created with ID: {new_product.id}.")
                        else:
                             # Если товар уже существует, берем его ID
                            if not target_product_id:
                                target_product_id = existing_product.id
                            print(f"  - Product '{prod_data['name']}' already exists with ID: {existing_product.id}.")
            
            await db.commit()

            # 3. Создаем тестовую заявку
            if target_product_id:
                print("\nCreating a test quote request to trigger notification...")
                await process_quote_request(
                    db=db,
                    name="Алиса Ыв",
                    phone="+99890188765556",
                    message="Здравствуйте, интересует проект. Какие сроки строительства?",
                    product_id=target_product_id, # Используем реальный ID
                    source="website"
                )
                print(f"  - Test quote request for product ID {target_product_id} created successfully!")
            else:
                print("\nSkipping quote request creation as no products were found or created.")
            
            print("\nDatabase seeding completed successfully!")

        except Exception as e:
            await db.rollback()
            print(f"\nAn error occurred: {e}")
            print("Transaction rolled back.")
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_database())