# src/services/shop_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, Session # <<< Добавлен импорт Session
from sqlalchemy import func # <<< Добавлен импорт func
from datetime import datetime, timedelta

from src.models.shop_models import Category, Product, Contact, QuoteRequest, User, Notification
from src.core.cache import cache_result, invalidate_cache

async def _get_or_create_contact(db: AsyncSession, name: str, phone: str) -> Contact:
    """
    Находит или создает контакт, используя надежный поиск по нормализованному номеру телефона.
    Эта версия устойчива к дубликатам в рамках одной транзакции.
    """
    if not phone or not phone.strip():
        first_name, _, last_name = name.partition(" ")
        return Contact(name=first_name, last_name=last_name or None, phone="N/A")

    # 1. Нормализуем входящий номер телефона до последних 9 цифр
    search_phone_normalized = "".join(filter(str.isdigit, phone))[-9:]

    # 2. ПРОВЕРКА В ТЕКУЩЕЙ СЕССИИ (чтобы избежать ошибки дубликата внутри одной транзакции)
    # Проверяем, не добавляли ли мы уже контакт с таким номером в этой же "пачке" данных
    sync_session: Session = db.sync_session
    for obj in sync_session.new:
        if isinstance(obj, Contact):
            existing_phone_normalized = "".join(filter(str.isdigit, obj.phone))[-9:]
            if existing_phone_normalized == search_phone_normalized:
                # Если нашли - возвращаем его и не идем в базу
                return obj

    # 3. ПОИСК В БАЗЕ ДАННЫХ (если в сессии не нашли)
    # Создаем SQL-выражение для нормализации номера прямо в базе данных
    phone_normalized_in_db = func.substr(func.regexp_replace(Contact.phone, r'\D', '', 'g'), -9)
    stmt = select(Contact).where(phone_normalized_in_db == search_phone_normalized)
    contact = (await db.execute(stmt)).scalars().first()

    if not contact:
        first_name, _, last_name = name.partition(" ")
        contact = Contact(
            phone=phone, # Сохраняем оригинальный формат для отображения
            name=first_name,
            last_name=last_name or None
        )
        db.add(contact)
        # Убираем await db.flush() отсюда, чтобы все сохранилось в конце одной транзакцией
    elif name and name.strip() and name.lower() != 'без имени':
        # Обновляем имя, если пришел более полный вариант
        first_name, _, last_name = name.partition(" ")
        contact.name = first_name
        contact.last_name = last_name or contact.last_name
    
    return contact

async def _create_quote_request(db: AsyncSession, contact_id: int, message: str, product_id: int = None, source: str = "website") -> QuoteRequest:
    quote = QuoteRequest(
        contact_id=contact_id,
        product_id=product_id,
        message=message,
        source=QuoteRequest.SourceEnum(source),
        status=QuoteRequest.StatusEnum.IMPORTED
    )
    db.add(quote)
    return quote

async def _notify_managers(db: AsyncSession, quote: QuoteRequest, contact_name: str):
    managers_stmt = select(User).where(User.is_staff == True, User.is_active == True)
    managers = (await db.execute(managers_stmt)).scalars().all()
    
    if not managers: return

    # Используем относительный URL, который будет работать везде
    quote_url = f"/admin/quoterequest/{quote.id}/change/"
    message_text = f"Новая заявка #{quote.id} от {contact_name}"

    notifications = [
        Notification(user_id=manager.id, message=message_text, link=quote_url)
        for manager in managers
    ]
    db.add_all(notifications)


@invalidate_cache("categories_with_products") 
async def process_quote_request(db: AsyncSession, name: str, phone: str, message: str, product_id: int = None, source: str = "website") -> QuoteRequest | str:
    """
    Обрабатывает заявку. Возвращает объект QuoteRequest в случае успеха
    или строку 'duplicate', если заявка является дубликатом.
    """
    contact = await _get_or_create_contact(db, name, phone)
    await db.flush() # Здесь flush нужен, чтобы получить contact.id

    # Проверка на дубликаты: ищем заявки от этого контакта за последнюю неделю
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    stmt = select(QuoteRequest).where(
        QuoteRequest.contact_id == contact.id,
        QuoteRequest.created_at >= seven_days_ago
    )
    # Добавим проверку на сообщение, чтобы можно было отправить разные заявки
    if message:
        stmt = stmt.where(QuoteRequest.message == message)

    recent_requests = (await db.execute(stmt)).scalars().all()
    
    if recent_requests:
        print(f"Duplicate quote request detected for contact {contact.id}. Not creating a new one.")
        return "duplicate"

    quote = await _create_quote_request(db, contact.id, message, product_id, source)
    
    await db.flush()
    await _notify_managers(db, quote, contact.full_name)
    await db.commit()
    await db.refresh(quote) 

    return quote

@cache_result("categories_with_products", ttl=1800)  
async def get_categories_with_active_products(db: AsyncSession):
    stmt = (
        select(Category)
        .options(selectinload(Category.products))
        .join(Category.products)
        .where(Product.is_active == True)
        .distinct()
        .order_by(Category.name_ru)
    )
    result = await db.execute(stmt)
    categories = result.scalars().all()
    
    filtered_categories = []
    for category in categories:
        active_products = [p for p in category.products if p.is_active]
        if active_products:
            category.products = active_products
            filtered_categories.append(category)
    
    return filtered_categories

@cache_result("product_modal", ttl=3600) 
async def get_product_for_modal(db: AsyncSession, product_id: int):
    stmt = (
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id == product_id)
    )
    result = await db.execute(stmt)
    return result.scalars().first()