# src/pages/admin/kanban.py

from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.services import crm_service
from .dependencies import get_common_context
from src.models.shop_models import QuoteRequest, User

router = APIRouter()

@router.get("/kanban", response_class=HTMLResponse, name="admin_kanban_board")
async def get_kanban_board(
    request: Request,
    show_archived: bool = Query(False),
    q: Optional[str] = Query(None),
    assignee: Optional[str] = Query(None),
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session),
):
    assignee_id = None
    if assignee == 'me':
        assignee_id = context["user"].id
    elif assignee and assignee.isdigit():
        assignee_id = int(assignee)

    kanban_data = await crm_service.get_kanban_data(db, show_archived, search_query=q, assignee_id=assignee_id)
    
    staff_users = (await db.execute(select(User).where(User.is_staff == True).order_by(User.username))).scalars().all()

    context.update({
        "title": "Воронка заявок (Kanban)",
        "requests_by_status": kanban_data,
        "staff_users": staff_users,  
        "QuoteRequest": QuoteRequest,
        "current_filters": {
            "q": q,
            "assignee": assignee,
            "show_archived": show_archived
        }
    })
    
    return templates.TemplateResponse("admin/kanban_board.html", context)