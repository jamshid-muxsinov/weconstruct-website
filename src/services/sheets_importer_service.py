# src/services/sheets_importer_service.py

import logging
import re
import httpx
import csv
import io
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.services.shop_service import _get_or_create_contact, _create_quote_request, _notify_managers
from src.models.shop_models import QuoteRequest, GoogleSheetLead, Contact 

log = logging.getLogger(__name__)

STATUS_MAPPING = {
    'yopildi': QuoteRequest.StatusEnum.ARCHIVED,
    'тели учик': QuoteRequest.StatusEnum.ARCHIVED,
    'нархи екмади': QuoteRequest.StatusEnum.ARCHIVED,
    'бино курилган': QuoteRequest.StatusEnum.ARCHIVED,
    'пули ва жойи йук': QuoteRequest.StatusEnum.ARCHIVED,
    'пул керак экан': QuoteRequest.StatusEnum.ARCHIVED,
    'маблаги йук': QuoteRequest.StatusEnum.ARCHIVED,
    
    'javob berdi': QuoteRequest.StatusEnum.CONTACTED,
    '2ta qo\'ng\'iroq': QuoteRequest.StatusEnum.CONTACTED,
}

def _parse_date(date_str: str) -> datetime | None:
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    
    formats_to_try = [
        "%d.%m.%Y %H:%M:%S", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
        "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%y", "%m.%d.%y"
    ]
    for fmt in formats_to_try:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
            
    try:
        if 'T' in date_str:
            iso_date_str = date_str.split('+')[0].split('-0')[0]
            return datetime.fromisoformat(iso_date_str)
    except (ValueError, TypeError):
        pass

    log.warning(f"Не удалось распарсить дату: '{date_str}'")
    return None

def _normalize_phone(phone: str) -> str:
    if not phone: return ""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 12 and digits.startswith('998'): return f"+{digits}"
    if len(digits) == 9: return f"+998{digits}"
    return phone

async def import_leads_from_sheet(db: AsyncSession, spreadsheet_id: str, gid: int = 0):
    log.info(f"Запуск импорта из Google Sheet ID: {spreadsheet_id}, GID: {gid}")
    export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(export_url, timeout=30.0)
        
        response.raise_for_status()
        response.encoding = 'utf-8'
        csv_data = io.StringIO(response.text)
        reader = csv.reader(csv_data)
        all_rows = list(reader)
    except Exception as e:
        log.error(f"Ошибка доступа к Google Sheets: {e}", exc_info=True)
        return {"status": "error", "message": f"Ошибка доступа к Google Sheets: {e}."}

    sheet_row_ids = [row[0].strip() for i, row in enumerate(all_rows) if i > 0 and row and len(row) > 0 and row[0].strip()]
    
    if not sheet_row_ids:
        return {"status": "success", "message": "В таблице не найдено строк с ID."}

    # --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: "Жадно" загружаем связанные quote_request ---
    existing_leads_stmt = (
        select(GoogleSheetLead)
        .where(GoogleSheetLead.sheet_row_id.in_(sheet_row_ids))
        .options(selectinload(GoogleSheetLead.quote_request))
    )
    existing_leads_result = await db.execute(existing_leads_stmt)
    existing_leads_map = {lead.sheet_row_id: lead for lead in existing_leads_result.scalars().all()}
    
    log.info(f"Найдено {len(sheet_row_ids)} лидов в таблице. Из них {len(existing_leads_map)} уже известны системе.")

    created_count, skipped_count, processed_count, error_count = 0, 0, 0, 0
    errors_log = []

    for i, row in enumerate(all_rows[1:]):
        original_row_number = i + 2
        
        if not row or len(row) == 0 or not row[0].strip():
            continue
            
        sheet_row_id = row[0].strip()
        processed_count += 1
        
        existing_lead = existing_leads_map.get(sheet_row_id)
        if existing_lead and existing_lead.status == GoogleSheetLead.StatusEnum.IMPORTED:
            skipped_count += 1
            continue
        
        try:
            async with db.begin_nested():
                client_name = (row[1].strip() if len(row) > 1 else "Без имени")[:150]
                business_type = (row[2].strip() if len(row) > 2 else "")[:255]
                phone_1 = row[3].strip() if len(row) > 3 else ""
                telegram = (row[4].strip() if len(row) > 4 else "")[:100]
                phone_2 = row[5].strip() if len(row) > 5 else ""
                status_from_sheet_raw = row[6].strip() if len(row) > 6 else ""
                comment = row[7].strip() if len(row) > 7 else ""
                
                phone_number = _normalize_phone(phone_1 or phone_2)[:50]
                
                if not phone_number:
                    raise ValueError(f"Не найден или некорректен номер телефона.")

                contact = await _get_or_create_contact(db, name=client_name, phone=phone_number)
                await db.flush()

                status_from_sheet_lower = status_from_sheet_raw.lower()
                crm_status = STATUS_MAPPING.get(status_from_sheet_lower)
                
                message_parts = []
                if crm_status is None and status_from_sheet_raw:
                    crm_status = QuoteRequest.StatusEnum.IMPORTED
                    message_parts.append(f"Статус из таблицы: {status_from_sheet_raw}")
                elif crm_status is None:
                    crm_status = QuoteRequest.StatusEnum.IMPORTED

                if business_type: message_parts.append(f"Тип бизнеса: {business_type}")
                if telegram: message_parts.append(f"Telegram: {telegram}")
                if comment: message_parts.append(f"Комментарий из таблицы: {comment}")
                message_for_crm = "\n".join(message_parts)

                quote = await _create_quote_request(db, contact.id, message_for_crm, source="contact_form")
                quote.business_type = business_type
                quote.status = crm_status
                
                lead_record = existing_lead
                if not lead_record:
                    lead_record = GoogleSheetLead(sheet_row_id=sheet_row_id, spreadsheet_id=spreadsheet_id)
                    db.add(lead_record)
                
                lead_record.status = GoogleSheetLead.StatusEnum.IMPORTED
                lead_record.processed_at = datetime.utcnow()
                lead_record.quote_request_id = quote.id
                lead_record.raw_data = row
                lead_record.processing_notes = f"Создана заявка #{quote.id} со статусом '{crm_status.value}'"
                
                await _notify_managers(db, quote, contact.full_name)
                created_count += 1

        except Exception as e:
            error_msg = f"Ошибка в строке {original_row_number} (ID: {sheet_row_id}): {e}"
            log.error(error_msg, exc_info=False)
            errors_log.append(error_msg)
            error_count += 1
            await db.rollback()

    await db.commit()
    
    message = (f"Синхронизация завершена! Обработано строк: {processed_count}. "
               f"Создано/обновлено: {created_count}. Пропущено: {skipped_count}. Ошибок: {error_count}.")
    if errors_log:
        message += "\n\nОшибки при импорте:\n- " + "\n- ".join(errors_log)

    log.info(message)
    return {"status": "success", "message": message}