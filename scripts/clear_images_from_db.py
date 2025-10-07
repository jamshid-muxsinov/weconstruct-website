import asyncio
import sys
from pathlib import Path
from sqlalchemy import update, delete # <<< 1. ДОБАВЛЕН ИМПОРТ delete

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.db import async_session_factory
from src.models.shop_models import Product, ProductImage

async def clear_image_references():
    print("--- Запуск очистки ссылок на изображения в базе данных ---")
    
    async with async_session_factory() as session:
        async with session.begin():
            # =============================================================
            # === ИСПРАВЛЕНИЕ ЗДЕСЬ =======================================
            # =============================================================
            # 1. Полностью УДАЛЯЕМ все записи из ProductImage
            stmt_product_image = delete(ProductImage)
            result = await session.execute(stmt_product_image)
            print(f"- Удалено {result.rowcount} записей из таблицы дополнительных изображений (ProductImage).")

            # 2. Обнуляем поле main_image в таблице Product (здесь NULL разрешен)
            stmt_product = update(Product).values(main_image=None)
            result = await session.execute(stmt_product)
            print(f"- Очищено {result.rowcount} ссылок на основные изображения в таблице продуктов (Product).")

        await session.commit()
    
    print("\n--- Очистка базы данных завершена! ---")
    print("Теперь вы можете заново загружать изображения через админ-панель.")

if __name__ == "__main__":
    asyncio.run(clear_image_references())