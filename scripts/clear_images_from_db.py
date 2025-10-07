# scripts/clear_images_from_db.py
import asyncio
import sys
from pathlib import Path
from sqlalchemy import update

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.db import async_session_factory
from src.models.shop_models import Product, ProductImage

async def clear_image_references():
    print("--- Запуск очистки ссылок на изображения в базе данных ---")
    
    async with async_session_factory() as session:
        async with session.begin():
            # 1. Удаляем все записи из ProductImage (дополнительные изображения)
            # Это проще, чем обновлять, так как их все равно нужно будет загружать заново.
            # await session.execute(delete(ProductImage)) 
            # Лучше обновим, чтобы не было проблем с внешними ключами
            stmt_product_image = update(ProductImage).values(image=None)
            await session.execute(stmt_product_image)
            print("- Все записи в ProductImage очищены (image=None).")

            # 2. Обнуляем поле main_image в таблице Product
            stmt_product = update(Product).values(main_image=None)
            await session.execute(stmt_product)
            print("- Поля main_image во всех продуктах очищены (main_image=None).")

        await session.commit()
    
    print("\n--- Очистка базы данных завершена! ---")
    print("Теперь вы можете заново загружать изображения через админ-панель.")

if __name__ == "__main__":
    asyncio.run(clear_image_references())