# src/pages/admin/api.py

import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Form, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from src.core.db import get_db_session
from src.core.security import get_current_active_user
from src.models.shop_models import User, Notification
from src.services import crm_service
from src.schemas.crm_schemas import QuoteRequestStatusUpdate

router = APIRouter(prefix="/api", tags=["Admin API"])

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

@router.post("/quoterequests/{pk}/assign", name="admin_api_quote_assign")
async def assign_quote_request(
    pk: int,
    assigned_to_id: int = Form(...),
    db: AsyncSession = Depends(get_db_session)
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

@router.post("/bulk-assign", name="api_bulk_assign")
async def bulk_assign_api(
    card_ids: List[int] = Form(...),
    user_id: int = Form(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    await crm_service.bulk_assign_requests(db, card_ids, user_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/bulk-status", name="api_bulk_status")
async def bulk_status_api(
    card_ids: List[int] = Form(...),
    status: str = Form(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    await crm_service.bulk_update_status(db, card_ids, status, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/update-status", name="api_update_single_status")
async def update_single_card_status(
    update_data: QuoteRequestStatusUpdate, 
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """Обновление статуса одной карточки (для Drag & Drop)"""
    print(f"DEBUG: Updating card {update_data.id} to status {update_data.status}")
    
    req = await crm_service.update_quote_request_status(db, update_data, current_user.id)
    
    if not req:
        raise HTTPException(status_code=404, detail="QuoteRequest not found")
        
    return {"status": "ok", "new_status": req.status}