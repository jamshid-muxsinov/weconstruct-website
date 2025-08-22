# src/pages/admin/importer.py

import re
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.pages.jinja_config import templates
from src.core.db import get_db_session
from .dependencies import get_common_context
from src.services.sheets_importer_service import import_leads_from_sheet # Наш новый сервис

router = APIRouter()

@router.get("/import", response_class=HTMLResponse, name="admin_import_page")
async def get_import_page(
    request: Request,
    context: dict = Depends(get_common_context)
):
    context["title"] = "Импорт из Google Sheets"
    return templates.TemplateResponse("admin/importer_page.html", context)


@router.post("/import", response_class=HTMLResponse, name="admin_run_import")
async def run_import_from_sheet(
    request: Request,
    sheet_url: str = Form(...),
    date_column: int = Form(0, description="Колонка с датой (0-индексация)"),
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    # Извлекаем ID таблицы из URL
    sheet_id_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', sheet_url)
    if not sheet_id_match:
        context["error"] = "Неверный URL таблицы Google Sheets. Не найден ID таблицы."
        context["title"] = "Импорт из Google Sheets"
        return templates.TemplateResponse("admin/importer_page.html", context, status_code=400)
    
    spreadsheet_id = sheet_id_match.group(1)
    
    # Извлекаем ID листа (gid) из URL. Если его нет, по умолчанию 0 (первый лист)
    gid_match = re.search(r'#gid=(\d+)', sheet_url)
    gid = int(gid_match.group(1)) if gid_match else 0

    # Запускаем импорт
    result = await import_leads_from_sheet(db, spreadsheet_id=spreadsheet_id, gid=gid, date_column=date_column)

    context["title"] = "Результат импорта"
    context["result"] = result
    # Передаем обратно введенный URL, чтобы он сохранился в форме
    context["current_sheet_url"] = sheet_url 

    return templates.TemplateResponse("admin/importer_page.html", context)