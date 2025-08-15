import json
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Body, Request, Form, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import joinedload, selectinload

from src.core.db import get_db_session
from src.core.security import get_current_active_user
from src.models.shop_models import User, QuoteRequest, Contact, Notification
from src.schemas.crm_schemas import QuoteRequestStatusUpdate
from src.services import crm_service
from src.pages.jinja_config import templates

router = APIRouter(prefix="/api", tags=["Admin API"])

@router.post("/quoterequests/update-status", name="admin_api_update_request_status")
async def update_request_status(
    request: Request,
    update_data: QuoteRequestStatusUpdate = Body(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    req = await crm_service.update_quote_request_status(db, update_data, current_user.id)
    if not req:
        raise HTTPException(status_code=404, detail="QuoteRequest not found")
    
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    trigger_payload = {
        "updateKanban": True,
        "update-notifications": True,
        "show-toast": {"message": "Статус обновлен!"}
    }
    response.headers["HX-Trigger"] = json.dumps(trigger_payload)
    return response


@router.post("/quoterequests/{pk}/assign", name="admin_api_quote_assign")
async def assign_quote_request(
    pk: int,
    assigned_to_id: int = Form(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Назначает ответственного за заявку (из модального окна/слайдовера).
    """
    req = await crm_service.assign_quote_request_to_user(db, pk, assigned_to_id)
    if not req:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    # ИЗМЕНЕНИЕ: Добавляем updateKanban в триггер
    trigger_payload = {
        "updateKanban": True,
        "closeSlideOver": True,
        "show-toast": {"message": "Исполнитель назначен!", "type": "success"}
    }
    response.headers["HX-Trigger"] = json.dumps(trigger_payload)
    return response

@router.post("/notifications/mark-as-read", name="admin_api_notifications_mark_read")
async def mark_notifications_as_read(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Помечает все непрочитанные уведомления пользователя как прочитанные.
    """
    stmt = (
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.execute(stmt)
    await db.commit()

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.headers["HX-Trigger"] = json.dumps({"notifications-read": True})
    return response