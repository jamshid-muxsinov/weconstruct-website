# src/services/sheets_importer_service.py

import logging
import re
import requests
import csv
import io
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.services.shop_service import _get_or_create_contact, _create_quote_request, _notify_managers
from src.models.shop_models import QuoteRequest, GoogleSheetLead, Contact 

log = logging.getLogger(__name__)

def _parse_date(date_str: str) -> datetime | None:
    """Пытается распарсить дату из строки, пробуя несколько популярных форматов."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    
    # Сначала пробуем стандартные форматы
    formats_to_try = [
        "%d.%m.%Y %H:%M:%S", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
        "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%y", "%m.%d.%y"
    ]
    for fmt in formats_to_try:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
            
    # Пробуем более сложный ISO формат с отсечением таймзоны
    try:
        if 'T' in date_str:
            iso_date_str = date_str.split('+')[0].split('-0')[0] # Обрезаем таймзону
            return datetime.fromisoformat(iso_date_str)
    except (ValueError, TypeError):
        pass

    log.warning(f"Не удалось распарсить дату: '{date_str}'")
    return None

def _normalize_phone(phone: str) -> str:
    """Приводит номер телефона к единому формату +998..."""
    if not phone: return ""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 12 and digits.startswith('998'): return f"+{digits}"
    if len(digits) == 9: return f"+998{digits}"
    return phone # Возвращаем как есть, если формат неизвестен

def _clean_prefixed_value(value: str) -> str:
    """Убирает префиксы типа '1:' или '2:' из строк."""
    if value and ':' in value and len(value.split(':', 1)[0]) <= 2:
        return value.split(':', 1)[1].strip()
    return value.strip()

async def import_leads_from_sheet(db: AsyncSession, spreadsheet_id: str, gid: int = 0):
    """
    Финальная, отказоустойчивая версия для синхронизации лидов.
    Обрабатывает каждого лида в отдельной под-транзакции.
    """
    log.info(f"Запуск синхронизации из Google Sheet ID: {spreadsheet_id}, GID: {gid}")
    export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
    try:
        response = requests.get(export_url, timeout=20)
        response.raise_for_status()
        response.encoding = 'utf-8'
        csv_data = io.StringIO(response.text)
        reader = csv.reader(csv_data)
        all_rows = list(reader)
        if not all_rows:
            return {"status": "success", "message": "В таблице нет данных.", "processed": 0, "created": 0, "skipped": 0, "errors": 0}
    except Exception as e:
        log.error(f"Ошибка доступа к Google Sheets: {e}", exc_info=True)
        return {"status": "error", "message": f"Ошибка доступа к Google Sheets: {e}."}

    # Собираем все ID строк из таблицы для быстрой проверки
    sheet_row_ids = [row[0].strip() for i, row in enumerate(all_rows) if i > 0 and row and row[0].strip()]
    if not sheet_row_ids:
        return {"status": "success", "message": "В таблице не найдено строк с ID.", "processed": 0, "created": 0, "skipped": 0, "errors": 0}

    # Один раз запрашиваем все уже существующие в БД записи по этим ID
    existing_leads_stmt = select(GoogleSheetLead).where(GoogleSheetLead.sheet_row_id.in_(sheet_row_ids))
    existing_leads_result = await db.execute(existing_leads_stmt)
    existing_leads_map = {lead.sheet_row_id: lead for lead in existing_leads_result.scalars().all()}
    
    log.info(f"Найдено {len(sheet_row_ids)} лидов в таблице. Из них {len(existing_leads_map)} уже известны системе.")

    created_count = 0
    skipped_count = 0
    processed_count = 0
    error_count = 0
    
    # Пропускаем заголовок
    for i, row in enumerate(all_rows[1:]):
        original_row_number = i + 2
        
        if not row or not any(field.strip() for field in row) or not row[0].strip():
            continue
            
        sheet_row_id = row[0].strip()
        processed_count += 1
        
        # Пропускаем уже успешно импортированные или заархивированные лиды
        if sheet_row_id in existing_leads_map:
            lead_record = existing_leads_map[sheet_row_id]
            if lead_record.status in [GoogleSheetLead.StatusEnum.IMPORTED, GoogleSheetLead.StatusEnum.ARCHIVED]:
                skipped_count += 1
                continue
        
        # --- ГЛАВНОЕ ИЗМЕНЕНИЕ: Изолированная транзакция для каждой строки ---
        try:
            async with db.begin_nested(): # Создаем SAVEPOINT
                lead_record = existing_leads_map.get(sheet_row_id)
                if not lead_record:
                    lead_record = GoogleSheetLead(sheet_row_id=sheet_row_id, spreadsheet_id=spreadsheet_id, raw_data=row)
                    db.add(lead_record)

                # --- ИСПРАВЛЕНИЕ: Извлекаем данные и ОБРЕЗАЕМ их до безопасной длины ---
                client_name_raw = row[1].strip() if len(row) > 1 else "Без имени"
                client_name = client_name_raw[:150] # Лимит из модели Contact.name
                
                business_type = (row[2].strip() if len(row) > 2 else "Не указан")[:255]
                phone_1 = row[3].strip() if len(row) > 3 else ""
                telegram = row[4].strip() if len(row) > 4 else ""
                phone_2 = row[5].strip() if len(row) > 5 else ""
                external_status = row[6].strip() if len(row) > 6 else ""
                comment = row[7].strip() if len(row) > 7 else ""

                phone_number_raw = (phone_1 or _clean_prefixed_value(phone_2))[:50] # Лимит из модели Contact.phone
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
                    if comment: message_parts.append(f"Комментарий: {comment}")
                    message_for_crm = "\n".join(message_parts)

                    quote = await _create_quote_request(db, contact.id, message_for_crm, source="contact_form")
                    quote.business_type = business_type
                    
                    parsed_date = _parse_date(row[8].strip() if len(row) > 8 else "") # Предположим, дата в 9-й колонке
                    if parsed_date:
                        quote.created_at = parsed_date
                    
                    db.add(quote)
                    await db.flush() # Получаем ID заявки для связи

                    lead_record.status = GoogleSheetLead.StatusEnum.IMPORTED
                    lead_record.processed_at = datetime.utcnow()
                    lead_record.quote_request_id = quote.id
                    lead_record.processing_notes = f"Создана заявка #{quote.id}"
                    
                    await _notify_managers(db, quote, contact.full_name)
                    
                    created_count += 1
                    log.info(f"Успешно обработан лид #{sheet_row_id}. Создана заявка #{quote.id}.")

        except Exception as e:
            # Если внутри `async with` произошла ошибка, транзакция автоматически отменяется (ROLLBACK TO SAVEPOINT)
            log.error(f"ОШИБКА при обработке лида #{sheet_row_id} (строка {original_row_number}): {e}", exc_info=True)
            error_count += 1
            # Мы можем сохранить информацию об ошибке в основной сессии, чтобы не пытаться обработать эту строку снова
            async with db.begin_nested():
                lead_record = existing_leads_map.get(sheet_row_id)
                if not lead_record:
                    lead_record = GoogleSheetLead(sheet_row_id=sheet_row_id, spreadsheet_id=spreadsheet_id, raw_data=row)
                    db.add(lead_record)
                lead_record.status = GoogleSheetLead.StatusEnum.ERROR
                lead_record.processing_notes = f"Ошибка: {str(e)[:1000]}" # Обрезаем сообщение об ошибке

    await db.commit() # Сохраняем все успешные "под-транзакции" и записи об ошибках
    
    message = (f"Синхронизация завершена! Обработано строк: {processed_count}. "
               f"Создано новых заявок: {created_count}. Пропущено (уже были): {skipped_count}. Ошибок: {error_count}.")
    log.info(message)
    return {"status": "success", "message": message, "processed": processed_count, "created": created_count, "skipped": skipped_count, "errors": error_count}