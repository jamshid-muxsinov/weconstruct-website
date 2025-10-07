# scripts/fix_filenames.py
import asyncio
import os
import sys
from pathlib import Path
from slugify import slugify
from sqlalchemy.future import select

# Добавляем путь к src, чтобы можно было импортировать модули
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.db import async_session_factory
from src.models.shop_models import Product, ProductImage

BASE_DIR = Path("/app") # Убедитесь, что это правильный путь внутри Docker-контейнера
MEDIA_DIR = BASE_DIR / "media"

async def fix_filenames():
    print("--- Запуск скрипта исправления имен файлов ---")
    
    async with async_session_factory() as session:
        # 1. Исправляем основные изображения продуктов (Product.main_image)
        products_stmt = select(Product).where(Product.main_image.isnot(None))
        products = (await session.execute(products_stmt)).scalars().all()
        
        print(f"\nНайдено {len(products)} продуктов с основными изображениями...")
        for product in products:
            if ' ' in product.main_image or '%' in product.main_image:
                original_path_str = product.main_image
                
                # Разбираем путь
                parts = original_path_str.split('/')
                dirname = '/'.join(parts[:-1])
                filename = parts[-1]
                
                # Создаем новое, безопасное имя
                new_filename = slugify(filename)
                new_path_str = f"{dirname}/{new_filename}"
                
                # Физически переименовываем файл
                old_file_path = MEDIA_DIR / original_path_str
                new_file_path = MEDIA_DIR / new_path_str
                
                if old_file_path.exists():
                    print(f"Переименование: {original_path_str} -> {new_path_str}")
                    os.rename(old_file_path, new_file_path)
                    
                    # Обновляем запись в базе данных
                    product.main_image = new_path_str
                    session.add(product)
                else:
                    print(f"[ПРЕДУПРЕЖДЕНИЕ] Файл не найден: {old_file_path}")

        # 2. Исправляем дополнительные изображения (ProductImage.image)
        images_stmt = select(ProductImage).where(ProductImage.image.isnot(None))
        images = (await session.execute(images_stmt)).scalars().all()

        print(f"\nНайдено {len(images)} дополнительных изображений...")
        for image in images:
            if ' ' in image.image or '%' in image.image:
                original_path_str = image.image
                parts = original_path_str.split('/')
                dirname = '/'.join(parts[:-1])
                filename = parts[-1]
                new_filename = slugify(filename)
                new_path_str = f"{dirname}/{new_filename}"
                
                old_file_path = MEDIA_DIR / original_path_str
                new_file_path = MEDIA_DIR / new_path_str

                if old_file_path.exists():
                    print(f"Переименование: {original_path_str} -> {new_path_str}")
                    os.rename(old_file_path, new_file_path)
                    
                    image.image = new_path_str
                    session.add(image)
                else:
                    print(f"[ПРЕДУПРЕЖДЕНИЕ] Файл не найден: {old_file_path}")
        
        await session.commit()
        print("\n--- Исправление завершено! ---")

if __name__ == "__main__":
    # Перед запуском убедитесь, что у вас установлена slugify
    # pip install python-slugify
    asyncio.run(fix_filenames())