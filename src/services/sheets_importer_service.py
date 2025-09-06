# src/services/sheets_importer_service.py

import logging
import re
import requests
import csv
import io
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from src.services.shop_service import _get_or_create_contact, _create_quote_request, _notify_managers
from src.models.shop_models import QuoteRequest, GoogleSheetLead 

log = logging.getLogger(__name__)

def _parse_date(date_str: str) -> datetime | None:
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    try:
        if 'T' in date_str:
            iso_date_str = date_str.split('-05:00')[0]
            parsed_date = datetime.fromisoformat(iso_date_str)
            return parsed_date
    except (ValueError, TypeError):
        pass
    formats_to_try = ["%m.%d.%y", "%d.%m.%y", "%m/%d/%y", "%d/%m/%y", "%Y-%m-%d"]
    for fmt in formats_to_try:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            if parsed_date.year < 100:
                 parsed_date = parsed_date.replace(year=parsed_date.year + 2000)
            return parsed_date
        except ValueError:
            continue
    log.warning(f"Не удалось распарсить дату: '{date_str}'")
    return None

def _normalize_phone(phone: str) -> str:
    if not phone: return ""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 12 and digits.startswith('998'): return f"+{digits}"
    if len(digits) == 9: return f"+998{digits}"
    return phone

def _clean_prefixed_value(value: str) -> str:
    if value and ':' in value and len(value.split(':', 1)[0]) <= 2:
        return value.split(':', 1)[1]
    return value

async def import_leads_from_sheet(db: AsyncSession, spreadsheet_id: str, gid: int = 0):
    """
    Финальная, отказоустойчивая версия для синхронизации лидов.
    Обрабатывает каждого лида в отдельной под-транзакции.
    """
    log.info(f"Запуск синхронизации из Google Sheet ID: {spreadsheet_id}, GID: {gid}")
    export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
    try:
        # ... (блок получения данных из Google Sheets остается без изменений) ...
        response = requests.get(export_url, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
        csv_data = io.StringIO(response.text)
        reader = csv.reader(csv_data)
        all_rows = list(reader)
        if not all_rows:
            return {"status": "success", "message": "В таблице нет данных.", "processed": 0, "created": 0, "skipped": 0}
    except Exception as e:
        return {"status": "error", "message": f"Ошибка доступа к Google Sheets: {e}."}

    sheet_row_ids = []
    header_row = True
    for row in all_rows:
        if header_row:
            if any(field.strip() for field in row): header_row = False
            continue
        if row and any(field.strip() for field in row) and row[0].strip():
            sheet_row_ids.append(row[0].strip())

    if not sheet_row_ids:
        return {"status": "success", "message": "В таблице не найдено строк с ID.", "processed": 0, "created": 0, "skipped": 0}

    existing_leads_stmt = select(GoogleSheetLead).where(GoogleSheetLead.sheet_row_id.in_(sheet_row_ids))
    existing_leads_result = await db.execute(existing_leads_stmt)
    existing_leads_map = {lead.sheet_row_id: lead for lead in existing_leads_result.scalars().all()}
    
    log.info(f"Найдено {len(sheet_row_ids)} лидов в таблице. Из них {len(existing_leads_map)} уже известны системе.")

    new_quotes_count = 0
    skipped_count = 0
    processed_count = 0
    error_count = 0
    header_row = True

    for i, row in enumerate(all_rows):
        original_row_number = i + 1
        
        if header_row:
            if any(field.strip() for field in row): header_row = False
            continue
        if not row or not any(field.strip() for field in row) or not row[0].strip():
            continue
            
        sheet_row_id = row[0].strip()
        
        if sheet_row_id in existing_leads_map:
            lead_record = existing_leads_map[sheet_row_id]
            if lead_record.status in [GoogleSheetLead.StatusEnum.IMPORTED, GoogleSheetLead.StatusEnum.ARCHIVED]:
                skipped_count += 1
                continue
        
        processed_count += 1
        
        # <<< НАЧАЛО ГЛАВНОГО ИЗМЕНЕНИЯ: Изолированная транзакция для каждого лида >>>
        try:
            async with db.begin_nested():
                lead_record = existing_leads_map.get(sheet_row_id)
                if not lead_record:
                    lead_record = GoogleSheetLead(sheet_row_id=sheet_row_id, spreadsheet_id=spreadsheet_id, raw_data=row)
                    db.add(lead_record)

                # Логика извлечения данных (остается той же)
                client_name = row[1].strip() if len(row) > 1 else "Без имени"
                business_type = row[2].strip() if len(row) > 2 else "Не указан"
                phone_1 = row[3].strip() if len(row) > 3 else ""
                telegram = row[4].strip() if len(row) > 4 else ""
                phone_2 = row[5].strip() if len(row) > 5 else ""
                external_status = row[6].strip() if len(row) > 6 else ""
                comment = row[7].strip() if len(row) > 7 else ""

                phone_number_raw = phone_1 or _clean_prefixed_value(phone_2)
                phone_number = _normalize_phone(phone_number_raw)

                if not phone_number:
                    log.warning(f"Пропуск лида #{sheet_row_id} (строка {original_row_number}): не указан номер телефона.")
                    lead_record.status = GoogleSheetLead.StatusEnum.SKIPPED
                    lead_record.processing_notes = "Номер телефона не найден или некорректен."
                    skipped_count += 1
                    # continue здесь не нужен, так как мы внутри транзакции
                else:
                    contact = await _get_or_create_contact(db, name=client_name, phone=phone_number)
                    await db.flush() # flush нужен здесь, чтобы получить contact.id

                    message_parts = []
                    if business_type: message_parts.append(f"Тип бизнеса: {business_type}")
                    if external_status: message_parts.append(f"Статус в таблице: {external_status}")
                    if telegram: message_parts.append(f"Telegram: {telegram}")
                    message_for_crm = "\n".join(message_parts)

                    quote = await _create_quote_request(db, contact.id, message_for_crm, source="contact_form")
                    quote.business_type = business_type
                    quote.investment_details = comment

                    parsed_date = _parse_date(comment)
                    if parsed_date:
                        quote.created_at = parsed_date
                    
                    db.add(quote)
                    await db.flush()

                    lead_record.status = GoogleSheetLead.StatusEnum.IMPORTED
                    lead_record.processed_at = datetime.utcnow()
                    lead_record.quote_request_id = quote.id
                    lead_record.processing_notes = f"Создана заявка #{quote.id}"
                    
                    await _notify_managers(db, quote, contact.full_name)
                    
                    new_quotes_count += 1
                    log.info(f"Успешно обработан лид #{sheet_row_id}. Создана заявка #{quote.id}.")

        except Exception as e:
            # Если внутри `async with` произошла ошибка, транзакция автоматически откатится
            log.error(f"ОШИБКА при обработке лида #{sheet_row_id}: {e}", exc_info=True)
            error_count += 1
            # Мы можем сохранить информацию об ошибке в основной сессии
            async with db.begin_nested():
                lead_record = existing_leads_map.get(sheet_row_id)
                if not lead_record:
                    lead_record = GoogleSheetLead(sheet_row_id=sheet_row_id, spreadsheet_id=spreadsheet_id, raw_data=row)
                    db.add(lead_record)
                lead_record.status = GoogleSheetLead.StatusEnum.ERROR
                lead_record.processing_notes = str(e)

        # <<< КОНЕЦ ГЛАВНОГО ИЗМЕНЕНИЯ >>>
            
    await db.commit() # Сохраняем все успешные транзакции и записи об ошибках
    
    message = f"Синхронизация завершена! Создано новых заявок: {new_quotes_count}. Пропущено: {skipped_count}. Ошибок: {error_count}."
    log.info(message)
    return {"status": "success", "message": message, "processed": processed_count, "created": new_quotes_count, "skipped": skipped_count}