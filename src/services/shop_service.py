# src/services/shop_service.py
import httpx 
from src.core.config import get_settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
import logging
from typing import Optional, Union
from typing import Any
# Импортируем все необходимые модули
from src.services import telegram_service
from src.models.shop_models import Category, Product, Contact, QuoteRequest, User, Notification
from src.core.cache import cache_result, invalidate_cache

log = logging.getLogger(__name__)

async def _get_or_create_contact(db: AsyncSession, name: str, phone: str) -> Contact | None:
    """
    Надежная версия для поиска или создания контакта, которая корректно
    работает внутри транзакционных блоков.
    """
    if not phone:
        return None

    stmt = select(Contact).where(Contact.phone == phone)
    result = await db.execute(stmt)
    contact = result.scalars().first()
    if contact:
        return contact
    
    first_name, _, last_name = name.partition(" ")
    
    new_contact = Contact(
        phone=phone,
        name=first_name,
        last_name=last_name or None
    )
    db.add(new_contact)
    
    await db.flush()
    await db.refresh(new_contact)
    
    return new_contact


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
    """
    Отправляет уведомления о новой заявке и менеджерам в CRM, и в Telegram.
    """
    settings = get_settings()
    
    # --- ЧАСТЬ 1: Уведомления внутри CRM (остается без изменений) ---
    managers_stmt = select(User).where(User.is_staff == True, User.is_active == True)
    managers_result = await db.execute(managers_stmt)
    managers = managers_result.scalars().all()
    
    if managers:
        quote_url = f"/ru/admin/quoterequest/{quote.id}/change/"
        message_text = f"Новая заявка #{quote.id} от {contact_name}"

        notifications = [
            Notification(user_id=manager.id, message=message_text, link=quote_url)
            for manager in managers
        ]
        db.add_all(notifications)

    # --- ЧАСТЬ 2: Уведомление в Telegram (новая улучшенная логика) ---
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        log.warning("TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не установлены. Уведомление в Telegram не отправлено.")
        return

    # Экранируем спецсимволы для MarkdownV2
    def _escape_markdown(text: Any) -> str:
        if not isinstance(text, str): text = str(text)
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        return "".join(f'\\{char}' if char in escape_chars else char for char in text)

    # Собираем данные из заявки
    client_name_escaped = _escape_markdown(contact_name)
    phone_raw = quote.contact.phone if quote.contact else ""
    phone_escaped = _escape_markdown(phone_raw)
    
    # Ищем регион и тип бизнеса в теме (subject)
    subject = quote.subject or ""
    business_type_escaped = _escape_markdown(quote.business_type or "Не указан")
    
    # Пытаемся извлечь регион из темы, если он там есть
    region_escaped = "Не указан"
    if "Лид из Facebook (" in subject:
        try:
            content = subject.split("(", 1)[1].rsplit(")", 1)[0]
            parts = content.split(" / ")
            if len(parts) > 1:
                region_escaped = _escape_markdown(parts[0])
        except IndexError:
            pass # Если парсинг не удался, останется "Не указан"
    
    phone_url = f"tel:{''.join(filter(str.isdigit, phone_raw))}"

    # Формируем сообщение
    message = (
        f"🔥 *Новый лид из Facebook/Instagram*\n\n"
        f"👤 *Клиент:* {client_name_escaped}\n"
        f"📞 *Телефон:* [{phone_escaped}]({phone_url})\n"
        f"🏢 *Тип бизнеса:* {business_type_escaped}\n"
        f"📍 *Регион:* {region_escaped}"
    )

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "MarkdownV2"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=params)
            response.raise_for_status()
            log.info(f"Уведомление о заявке #{quote.id} успешно отправлено в Telegram.")
    except httpx.HTTPStatusError as e:
        log.error(f"Ошибка API Telegram при отправке заявки #{quote.id}: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        log.error(f"Не удалось отправить уведомление о заявке #{quote.id} в Telegram: {e}", exc_info=True)

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