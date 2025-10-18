# src/services/shop_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
import logging
from typing import Optional, Union

# Импортируем все необходимые модули
from src.services import telegram_service
from src.models.shop_models import Category, Product, Contact, QuoteRequest, User, Notification
from src.core.cache import cache_result, invalidate_cache

log = logging.getLogger(__name__)


async def _get_or_create_contact(db: AsyncSession, name: str, phone: str) -> Contact | None:
    if not phone:
        return None

    first_name, _, last_name = name.partition(" ")
    
    insert_stmt = pg_insert(Contact).values(
        phone=phone,
        name=first_name,
        last_name=last_name or None
    ).on_conflict_do_nothing(
        index_elements=['phone']
    )
    await db.execute(insert_stmt)
    await db.commit() 

    stmt = select(Contact).where(Contact.phone == phone)
    result = await db.execute(stmt)
    contact = result.scalars().first()
    
    return contact

async def _create_quote_request(db: AsyncSession, contact_id: int, message: str, subject: str, source: str = "website") -> QuoteRequest:
    quote = QuoteRequest(
        contact_id=contact_id,
        subject=subject,
        message=message,
        source=QuoteRequest.SourceEnum(source),
        status=QuoteRequest.StatusEnum.IMPORTED
    )
    db.add(quote)
    await db.flush()
    return quote

async def _notify_managers(db: AsyncSession, quote: QuoteRequest, contact_name: str):
    managers_stmt = select(User).where(User.is_staff == True, User.is_active == True)
    managers = (await db.execute(managers_stmt)).scalars().all()
    
    if not managers: return

    quote_url = f"/ru/admin/quoterequest/{quote.id}/change/"
    message_text = f"Новая заявка #{quote.id} от {contact_name}"

    notifications = [
        Notification(user_id=manager.id, message=message_text, link=quote_url)
        for manager in managers
    ]
    db.add_all(notifications)

@invalidate_cache("categories_with_products") 
async def process_quote_request(db: AsyncSession, name: str, phone: str, message: str, subject: Optional[str] = "Заявка с сайта", source: str = "website") -> Union[QuoteRequest, str]:
    """
    Обрабатывает входящую заявку: создает контакт, заявку, уведомляет менеджеров в CRM и Telegram.
    Реализована проверка на дубликаты.
    """
    try:
        contact = await _get_or_create_contact(db, name, phone)
        if not contact:
            return "invalid_contact"

        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        stmt = select(QuoteRequest).where(
            QuoteRequest.contact_id == contact.id,
            QuoteRequest.created_at >= seven_days_ago
        )
        if message:
            stmt = stmt.where(QuoteRequest.message == message)
        if subject:
            stmt = stmt.where(QuoteRequest.subject == subject)

        recent_requests = (await db.execute(stmt)).scalars().all()
        
        if recent_requests:
            log.warning(f"Обнаружена дублирующая заявка от {name} ({phone}). Пропуск.")
            return "duplicate"
        
        quote = await _create_quote_request(db, contact.id, message, subject, source)
        await _notify_managers(db, quote, contact.full_name)
        
        await db.commit()
        
        await db.refresh(quote)

        try:
            source_text = "Новая заявка с сайта" if source == "website" else "Новая заявка (общая)"
            lead_data_for_tg = {
                "source_text": source_text,
                "client_name": contact.full_name,
                "phone": contact.phone,
                "subject": subject,
            }
            await telegram_service.send_new_lead_notification(lead_data_for_tg)
        except Exception as e:
            log.error(f"Не удалось отправить Telegram-уведомление для заявки #{quote.id} (но она сохранена в CRM): {e}", exc_info=True)

        return quote

    except Exception as e:
        log.error(f"Критическая ошибка при обработке заявки от {name} ({phone}): {e}", exc_info=True)
        await db.rollback()
        return "error"

# --- ВОССТАНОВЛЕННАЯ ФУНКЦИЯ ---
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

# --- ВОССТАНОВЛЕННАЯ ФУНКЦИЯ ---
@cache_result("product_modal", ttl=3600) 
async def get_product_for_modal(db: AsyncSession, product_id: int):
    stmt = (
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id == product_id)
    )
    result = await db.execute(stmt)
    return result.scalars().first()