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
    rows: List[List[str]]

@router.post("/new-lead", status_code=status.HTTP_202_ACCEPTED)
async def receive_new_lead_from_google(
    payload: NewLeadPayload,
    request: Request,
    x_secret_token: str = Header(None),
    db: AsyncSession = Depends(get_db_session)
):
    if not settings.GOOGLE_SHEET_WEBHOOK_SECRET or x_secret_token != settings.GOOGLE_SHEET_WEBHOOK_SECRET:
        log.warning(f"Попытка доступа к вебхуку с неверным токеном с IP: {request.client.host}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token.")

    log.info(f"Получено {len(payload.rows)} новых лидов из Google Sheets через вебхук.")
    
    for row_data in payload.rows:
        await sheets_importer_service.process_single_lead_row(db, row_data)
    
    try:
        await db.commit()
        log.info(f"Финальный коммит импорта успешно выполнен.")
    except Exception as e:
        log.error(f"Критическая ошибка при финальном коммите импорта: {e}", exc_info=True)
        await db.rollback()
    
    return {"status": "ok", "message": "Leads received and are being processed."}