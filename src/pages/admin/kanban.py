from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.services import crm_service
from .dependencies import get_common_context

router = APIRouter()

@router.get("/kanban", response_class=HTMLResponse, name="admin_kanban_board")
async def get_kanban_board(
    request: Request,
    show_archived: bool = False,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session),
):
    kanban_data = await crm_service.get_kanban_data(db, show_archived)
    
    context.update({
        "title": "Воронка заявок (Kanban)",
        "requests_by_status": kanban_data,
        "show_archived": show_archived,
        "htmx_request": "HX-Request" in request.headers
    })
    
    return templates.TemplateResponse("admin/kanban_board.html", context)