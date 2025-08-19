# /src/pages/admin/dependencies.py
import json # Добавьте этот импорт
from fastapi import Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from src.core.db import get_db_session
from src.core.security import get_current_active_user
from src.models.shop_models import User, Notification, QuoteRequest, Contact
from src.core.cache import cache_manager
from src.pages.jinja_config import templates

async def get_unread_notifications_count(db: AsyncSession, user_id: int) -> int:
    """Подсчитывает непрочитанные уведомления для пользователя."""
    stmt = select(func.count(Notification.id)).where(
        Notification.user_id == user_id,
        Notification.is_read == False
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() or 0

async def get_common_context(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user)
) -> dict:
    """Возвращает общий контекст для всех страниц админки."""
    unread_count = await get_unread_notifications_count(db, user.id)
    return {
        "request": request,
        "user": user,
        "unread_notifications_count": unread_count,
        "getattr": getattr,
        "url_for": request.url_for 
    }

async def publish_kanban_update(db: AsyncSession, quote_id: int, request: Request):
    """
    Находит заявку, рендерит её HTML-карточку и публикует в Redis 
    вместе с временной меткой.
    """
    if not cache_manager.is_redis_available:
        return

    stmt = (
        select(QuoteRequest).where(QuoteRequest.id == quote_id)
        .options(
            joinedload(QuoteRequest.contact).selectinload(Contact.timeline_notes),
            joinedload(QuoteRequest.product),
            joinedload(QuoteRequest.assigned_to)
        )
    )
    result = await db.execute(stmt)
    quote_to_render = result.scalars().first()
    
    if quote_to_render:
        card_html = templates.TemplateResponse(
            "admin/partials/_kanban_card.html",
            {"request": request, "req": quote_to_render}
        ).body.decode("utf-8")
        
        payload = {
            "html": card_html,
            "created_at": quote_to_render.created_at.isoformat() 
        }
        
        # Публикуем JSON-строку
        await cache_manager.redis_client.publish("kanban_updates", json.dumps(payload))