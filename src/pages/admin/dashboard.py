from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.services import crm_service
from .dependencies import get_common_context

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse, name="admin_dashboard")
async def get_dashboard(
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session),
):
    dashboard_data = await crm_service.get_dashboard_data(db, context["user"].id)
    top_managers_data = await crm_service.get_top_managers(db)
    
    context.update({
        "title": "Статистика и Обзор",
        "sales_funnel": dashboard_data.get("sales_funnel", []),
        "my_tasks": dashboard_data.get("my_tasks", []),
        "new_unassigned_requests": dashboard_data.get("new_unassigned_requests", []),
        "top_managers": top_managers_data,
        "htmx_request": "HX-Request" in request.headers
    })
    return templates.TemplateResponse("admin/dashboard.html", context)