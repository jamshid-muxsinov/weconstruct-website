# src/pages/admin/api.py

import json
from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Form, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from src.core.db import get_db_session
from src.core.security import get_current_active_user
from src.models.shop_models import User, QuoteRequest, Notification
from src.schemas.crm_schemas import QuoteRequestStatusUpdate
from src.services import crm_service

router = APIRouter(prefix="/api", tags=["Admin API"])


@router.post("/quoterequests/update-status", name="admin_api_update_request_status")
async def update_request_status(
    update_data: QuoteRequestStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    req = await crm_service.update_quote_request_status(db, update_data, current_user.id)
    if not req:
        raise HTTPException(status_code=404, detail="QuoteRequest not found")
    
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    trigger_payload = {
        "updateKanban": True,
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
    req = await crm_service.assign_quote_request_to_user(db, pk, assigned_to_id)
    if not req:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
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

class BulkAssignRequest(BaseModel):
    card_ids: List[int]
    user_id: int

class BulkStatusRequest(BaseModel):
    card_ids: List[int]
    status: str

class CardStatusRequest(BaseModel):
    card_id: int
    status: str

@router.post("/bulk-assign", name="api_bulk_assign")
async def bulk_assign_requests(
    card_ids: List[int] = Form(...),
    user_id: int = Form(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """Массовое назначение заявок пользователю"""
    updated_count = await crm_service.bulk_assign_requests(
        db, card_ids, user_id, current_user.id
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.headers["HX-Trigger"] = "updateKanban"
    return response


@router.post("/bulk-status", name="api_bulk_status")
async def bulk_update_status(
    card_ids: List[int] = Form(...),
    # --- ИЗМЕНЕНИЕ: Переименовали 'status' в 'new_status' ---
    new_status: str = Form(..., alias="status"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """Массовое обновление статуса заявок"""
    updated_count = await crm_service.bulk_update_status(
        db, card_ids, new_status, current_user.id
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.headers["HX-Trigger"] = "updateKanban"
    return response


@router.post("/update-status", name="api_update_single_status")
async def update_single_card_status(
    card_id: int = Form(...),
    # --- ИЗМЕНЕНИЕ: Переименовали 'status' в 'new_status' ---
    new_status: str = Form(..., alias="status"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """Обновление статуса одной карточки (для Drag & Drop)"""
    req = await crm_service.update_single_card_status(
        db, card_id, new_status, current_user.id
    )
    if not req:
        raise HTTPException(status_code=404, detail="QuoteRequest not found")
    return {"status": "ok"}