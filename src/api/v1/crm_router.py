from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel

from src.core.db import get_db_session
from src.core.security import get_current_active_user
from src.models.shop_models import User
from src.schemas.crm_schemas import QuoteRequestStatusUpdate, TaskCreate, TaskRead
from src.services import crm_service

router = APIRouter(tags=["CRM API"])

# Bulk operation data models
class BulkAssignRequest(BaseModel):
    card_ids: List[int]
    user_id: int

class BulkStatusRequest(BaseModel):
    card_ids: List[int]
    status: str

class CardStatusRequest(BaseModel):
    card_id: int
    status: str

@router.post("/quoterequests/update-status", name="api_update_request_status")
async def update_request_status(
    update_data: QuoteRequestStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    try:
        req = await crm_service.update_quote_request_status(db, update_data, current_user.id)
        if not req:
            raise HTTPException(status_code=404, detail="QuoteRequest not found")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating quote request status: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Internal server error while updating status"
        )

@router.post("/quoterequests/{req_id}/assign", name="api_assign_request")
async def assign_request(
    req_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    req = await crm_service.assign_quote_request_to_user(db, req_id, current_user.id)
    if not req:
        raise HTTPException(status_code=404, detail="QuoteRequest not found or already assigned")
    return {"status": "ok"}

@router.post("/tasks/{task_id}/toggle", name="api_toggle_task")
async def toggle_task(
    task_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    task = await crm_service.toggle_task_completion(db, task_id, current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or you don't have permission")
    return {"status": "ok", "completed": task.completed}

@router.post("/quoterequests/{req_id}/tasks", response_model=list[TaskRead], name="api_add_task_to_request")
async def add_task_to_request(
    req_id: int,
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    task_data.quote_request_id = req_id
    if task_data.assigned_to_id is None: # Assign to current user if not specified
        task_data.assigned_to_id = current_user.id

    tasks = await crm_service.create_task_for_quote(db, task_data)
    if tasks is None:
        raise HTTPException(status_code=404, detail="QuoteRequest not found")
    return tasks

@router.post("/bulk-assign", name="api_bulk_assign")
async def bulk_assign_requests(
    bulk_data: BulkAssignRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """Bulk assign multiple quote requests to a user"""
    try:
        updated_count = await crm_service.bulk_assign_requests(
            db, bulk_data.card_ids, bulk_data.user_id, current_user.id
        )
        return {"status": "ok", "updated_count": updated_count}
    except Exception as e:
        print(f"Error in bulk assign: {e}")
        raise HTTPException(status_code=500, detail="Error assigning requests")

@router.post("/bulk-status", name="api_bulk_status")
async def bulk_update_status(
    bulk_data: BulkStatusRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """Bulk update status of multiple quote requests"""
    try:
        updated_count = await crm_service.bulk_update_status(
            db, bulk_data.card_ids, bulk_data.status, current_user.id
        )
        return {"status": "ok", "updated_count": updated_count}
    except Exception as e:
        print(f"Error in bulk status update: {e}")
        raise HTTPException(status_code=500, detail="Error updating status")

@router.post("/update-status", name="api_update_single_status")
async def update_single_card_status(
    status_data: CardStatusRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """Update status of a single card (for drag & drop and swipe gestures)"""
    try:
        req = await crm_service.update_single_card_status(
            db, status_data.card_id, status_data.status, current_user.id
        )
        if not req:
            raise HTTPException(status_code=404, detail="QuoteRequest not found")
        return {"status": "ok"}
    except Exception as e:
        print(f"Error updating single card status: {e}")
        raise HTTPException(status_code=500, detail="Error updating status")

@router.get("/export-requests", name="api_export_requests")
async def export_requests(
    card_ids: str = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """Export selected requests to CSV"""
    try:
        if card_ids:
            ids = [int(id.strip()) for id in card_ids.split(',') if id.strip()]
        else:
            ids = []
        
        csv_content = await crm_service.export_requests_csv(db, ids)
        
        from fastapi.responses import Response
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=quote_requests.csv"}
        )
    except Exception as e:
        print(f"Error exporting requests: {e}")
        raise HTTPException(status_code=500, detail="Error exporting requests")