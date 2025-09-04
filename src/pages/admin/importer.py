# src/pages/admin/importer.py

import re
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.pages.jinja_config import templates
from src.core.db import get_db_session
from .dependencies import get_common_context
from src.services.sheets_importer_service import import_leads_from_sheet
from src.services import crm_service
router = APIRouter()

@router.get("/import", response_class=HTMLResponse, name="admin_import_page")
async def get_import_page(
    request: Request,
    context: dict = Depends(get_common_context)
):
    context["title"] = "Импорт из Google Sheets"
    context["htmx_request"] = "HX-Request" in request.headers
    return templates.TemplateResponse("admin/importer_page.html", context)


@router.post("/import", response_class=HTMLResponse, name="admin_run_import")
async def run_import_from_sheet(
    request: Request,
    sheet_url: str = Form(...),
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    # --- И ДОБАВЬТЕ ЭТУ СТРОКУ СЮДА ТОЖЕ ---
    context["htmx_request"] = "HX-Request" in request.headers

    # Извлекаем ID таблицы из URL
    sheet_id_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', sheet_url)
    if not sheet_id_match:
        context["error"] = "Неверный URL таблицы Google Sheets. Не найден ID таблицы."
        context["title"] = "Импорт из Google Sheets"
        return templates.TemplateResponse("admin/importer_page.html", context, status_code=400)
    
    spreadsheet_id = sheet_id_match.group(1)
    
    gid_match = re.search(r'#gid=(\d+)', sheet_url)
    gid = int(gid_match.group(1)) if gid_match else 0

    # Запускаем импорт
    result = await import_leads_from_sheet(db, spreadsheet_id=spreadsheet_id, gid=gid)

    context["title"] = "Результат импорта"
    context["result"] = result
    context["current_sheet_url"] = sheet_url 

    return templates.TemplateResponse("admin/importer_page.html", context)

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