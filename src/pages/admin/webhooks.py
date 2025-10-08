import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Request, Header, HTTPException, status
from pydantic import BaseModel

from src.core.config import get_settings
from src.core.db import async_session_factory
from src.services import sheets_importer_service

log = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

# --- ИЗМЕНЕНИЕ 1: Новая модель для входящих данных ---
class Lead(BaseModel):
    sheet_row_id: str
    client_name: str
    phone: str
    business_type: str
    raw_data: str

class NewLeadPayload(BaseModel):
    leads: List[Lead]

@router.post("/new-lead", status_code=status.HTTP_202_ACCEPTED) # Меняем статус-код на 202
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

    # --- ИЗМЕНЕНИЕ 2: Обрабатываем структурированные данные ---
    for lead_data in payload.leads:
        async with async_session_factory() as session:
            # Передаем словарь вместо списка
            success = await sheets_importer_service.process_single_lead_row(session, lead_data.model_dump())
            if success:
                processed_count += 1
            else:
                skipped_count += 1

    log.info(f"Обработка завершена. Успешно импортировано: {processed_count}. Пропущено/ошибки: {skipped_count}.")
    
    return {"status": "ok", "message": f"Processed: {processed_count}, Skipped/Errors: {skipped_count}."}