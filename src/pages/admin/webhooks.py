# src/pages/admin/webhooks.py

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Request, Header, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.db import async_session_factory, get_db_session
from src.core.config import get_settings
from src.core.db import async_session_factory
from src.services import sheets_importer_service
from sqlalchemy.future import select 
from src.models.shop_models import GoogleSheetLead
from src.services import telegram_service

log = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

class Lead(BaseModel):
    sheet_row_id: str
    client_name: str
    phone: str
    business_type: str
    raw_data: str
    region: str
    raw_data: str

class NewLeadPayload(BaseModel):
    leads: List[Lead]

@router.post("/new-lead", status_code=status.HTTP_202_ACCEPTED)
async def receive_new_lead_from_google(
    payload: NewLeadPayload,
    request: Request,
    x_secret_token: str = Header(None),
):
    if not settings.GOOGLE_SHEET_WEBHOOK_SECRET or x_secret_token != settings.GOOGLE_SHEET_WEBHOOK_SECRET:
        log.warning(f"Попытка доступа к вебхуку с неверным токеном с IP: {request.client.host}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token.")

    log.info(f"Получено {len(payload.leads)} новых лидов из Google Sheets через вебхук.")
    
    processed_count = 0
    skipped_count = 0

    for lead in payload.leads:
        lead_dict = lead.model_dump()
        async with async_session_factory() as session:
            try:
                async with session.begin():
                    await sheets_importer_service.process_single_lead_row(session, lead_dict)
            
                processed_count += 1
                await telegram_service.send_new_lead_notification(lead_dict)
            
            except Exception as e:
                skipped_count += 1
                log.error(f"Ошибка при обработке лида {lead_dict.get('sheet_row_id')}: {e}", exc_info=True)

    log.info(f"Обработка завершена. Успешно импортировано: {processed_count}. Пропущено/ошибки: {skipped_count}.")
    
    return {"status": "ok", "message": f"Processed: {processed_count}, Skipped/Errors: {skipped_count}."}

class CheckExistingLeadsRequest(BaseModel):
    sheet_row_ids: List[str]

@router.post("/check-existing-leads", response_model=List[str])
async def check_existing_leads(
    payload: CheckExistingLeadsRequest,
    db: AsyncSession = Depends(get_db_session),
    x_secret_token: str = Header(None)
):
    """
    Принимает список ID лидов и возвращает те, которые уже существуют в БД.
    """
    if not settings.GOOGLE_SHEET_WEBHOOK_SECRET or x_secret_token != settings.GOOGLE_SHEET_WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token.")
    
    if not payload.sheet_row_ids:
        return []
        
    stmt = select(GoogleSheetLead.sheet_row_id).where(GoogleSheetLead.sheet_row_id.in_(payload.sheet_row_ids))
    result = await db.execute(stmt)
    existing_ids = result.scalars().all()
    
    return existing_ids