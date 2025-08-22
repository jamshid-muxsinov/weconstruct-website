from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db_session
from src.core.security import get_current_active_user
from src.models.shop_models import User
from src.schemas.crm_schemas import QuoteRequestStatusUpdate, TaskCreate, TaskRead
from src.services import crm_service

router = APIRouter(tags=["CRM API"])

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