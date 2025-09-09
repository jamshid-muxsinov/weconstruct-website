# src/pages/admin/dependencies.py

from fastapi import Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import undefer
from src.core.db import get_db_session
from src.core.security import get_current_active_user
from src.models.shop_models import User, Notification
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
    await db.refresh(user) 
    
    unread_count = await get_unread_notifications_count(db, user.id)
    
    return {
        "request": request,
        "user": user,
        "unread_notifications_count": unread_count,
        "getattr": getattr,
        "url_for": request.url_for,
    }