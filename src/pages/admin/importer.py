# src/pages/admin/importer.py

import re
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.pages.jinja_config import templates
from src.core.db import get_db_session
from .dependencies import get_common_context
from src.services import crm_service
router = APIRouter()

@router.post("/merge-duplicates", response_class=HTMLResponse, name="admin_merge_duplicates")
async def merge_duplicates(
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Запускает процесс поиска и слияния дубликатов контактов.
    Возвращает HTMX-фрагмент с результатом.
    """
    result = await crm_service.merge_duplicate_contacts(db)
    
    message = result.get("message", "Произошла неизвестная ошибка.")
    status_class = "success" if result.get("merged_groups", 0) > 0 or "не найдены" in message else "warning"
    
    html_content = f"""
    <div id="merge-results" class="card" style="margin-top: 16px; border-left: 4px solid var(--status-{'green' if status_class == 'success' else 'yellow'});">
        <p style="font-weight: 500;">Результат очистки:</p>
        <p style="color: var(--text-secondary); margin-top: 4px;">{message}</p>
    </div>
    """
    return HTMLResponse(content=html_content)

@router.post("/find-duplicates", response_class=HTMLResponse, name="admin_find_duplicates")
async def find_duplicates_view(
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    """Находит, но не объединяет дубликаты, и рендерит результат."""
    duplicate_groups = await crm_service.find_potential_duplicates(db)
    context["duplicate_groups"] = duplicate_groups
    return templates.TemplateResponse("admin/partials/_duplicate_results.html", context)