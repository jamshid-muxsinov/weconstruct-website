# src/pages/admin/webhooks.py

import logging
from typing import List
from fastapi import APIRouter, Depends, Request, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.db import get_db_session
from src.services import sheets_importer_service

log = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

class NewLeadPayload(BaseModel):
    # Google Apps Script будет присылать нам массив строк, где каждая строка - это массив ячеек
    rows: List[List[str]]

@router.post("/new-lead", status_code=status.HTTP_202_ACCEPTED)
async def receive_new_lead_from_google(
    payload: NewLeadPayload,
    request: Request,
    x_secret_token: str = Header(None),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Принимает данные о новых лидах из Google Sheets, проверяет секретный токен
    и ставит их в очередь на обработку.
    """
    if not settings.GOOGLE_SHEET_WEBHOOK_SECRET or x_secret_token != settings.GOOGLE_SHEET_WEBHOOK_SECRET:
        log.warning(f"Попытка доступа к вебхуку с неверным токеном с IP: {request.client.host}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token.")

    log.info(f"Получено {len(payload.rows)} новых лидов из Google Sheets через вебхук.")
    
    successful_count = 0
    # Обрабатываем каждую новую строку
    for row_data in payload.rows:
        try:
            await sheets_importer_service.process_single_lead_row(db, row_data)
            successful_count += 1
        except Exception as e:
            # Логирование уже происходит внутри process_single_lead_row
            pass
    
    # Делаем один коммит в самом конце, чтобы сохранить все успешно обработанные строки
    try:
        await db.commit()
        log.info(f"Успешно сохранено {successful_count} из {len(payload.rows)} лидов.")
    except Exception as e:
        log.error(f"Критическая ошибка при финальном коммите импорта: {e}", exc_info=True)
        await db.rollback()
    
    return {"status": "ok", "message": "Leads received and are being processed."}