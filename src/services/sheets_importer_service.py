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
from src.models.shop_models import QuoteRequest

log = logging.getLogger(__name__)

def _parse_date(date_str: str) -> datetime | None:
    """Парсит дату из различных форматов (MM.DD.YY, DD.MM.YY, ISO) и возвращает datetime объект."""
    if not date_str or not date_str.strip():
        return None
    
    date_str = date_str.strip()
    
    # Сначала пробуем распознать формат ISO 8601 (YYYY-MM-DDTHH:MM:SS-HH:MM)
    try:
        if 'T' in date_str:
            # Отбрасываем информацию о часовом поясе для простоты
            iso_date_str = date_str.split('-05:00')[0]
            parsed_date = datetime.fromisoformat(iso_date_str)
            log.info(f"Успешно распарсена дата ISO '{date_str}' как {parsed_date.strftime('%Y-%m-%d %H:%M:%S')}")
            return parsed_date
    except (ValueError, TypeError):
        pass # Если не получилось, пробуем другие форматы

    # Старые форматы
    formats_to_try = [
        "%m.%d.%y",  # 8.13.25
        "%d.%m.%y",  # 13.8.25
        "%m/%d/%y",  # 8/13/25
        "%d/%m/%y",  # 13/8/25
        "%m-%d-%y",  # 8-13-25
        "%d-%m-%y",  # 13-8-25
        "%m.%d.%Y",  # 8.13.2025
        "%d.%m.%Y",  # 13.8.2025
        "%m/%d/%Y",  # 8/13/2025
        "%d/%m/%Y",  # 13/8/2025
        "%Y-%m-%d",  # 2025-08-13
    ]
    
    for fmt in formats_to_try:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            if parsed_date.year < 100:
                 parsed_date = parsed_date.replace(year=parsed_date.year + 2000)
            log.info(f"Успешно распарсена дата '{date_str}' как {parsed_date.strftime('%Y-%m-%d %H:%M:%S')}")
            return parsed_date
        except ValueError:
            continue
    
    log.warning(f"Не удалось распарсить дату: '{date_str}'")
    return None

def _normalize_phone(phone: str) -> str:
    """Приводит номер телефона к единому формату E.164 (+998...)."""
    if not phone:
        return ""
    # Удаляем все не-цифры, включая префикс 'p:'
    digits = re.sub(r'\D', '', phone)
    
    if len(digits) == 12 and digits.startswith('998'):
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
        
    return phone # Возвращаем как есть, если формат неизвестен

def _clean_prefixed_value(value: str) -> str:
    """Удаляет префиксы типа 'l:', 'p:' и т.д."""
    if value and ':' in value and len(value.split(':')[0]) <= 2:
        return value.split(':', 1)[1]
    return value

async def import_leads_from_sheet(db: AsyncSession, spreadsheet_id: str, gid: int = 0, date_column_ignored: int = 0):
    """
    Основная функция для импорта лидов из Google Sheets.
    Проверяет наличие дубликатов и строк-заголовков перед созданием новой заявки.
    """
    log.info(f"Starting import from Google Sheet ID: {spreadsheet_id}, GID: {gid}")

    export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
    try:
        response = requests.get(export_url, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
        csv_data = io.StringIO(response.text)
        reader = csv.reader(csv_data)
        
        # Пропускаем заголовки, они нам не нужны, так как мы используем фиксированные индексы
        all_rows = list(reader)
        if not all_rows:
            return {"status": "success", "message": "В таблице нет данных для импорта.", "processed": 0, "created": 0}

    except requests.exceptions.RequestException as e:
        error_message = f"Ошибка доступа к Google Sheets: {e}. Убедитесь, что таблица доступна по ссылке."
        return {"status": "error", "message": error_message}
    except Exception as e:
        error_message = f"Непредвиденная ошибка при чтении таблицы: {e}"
        return {"status": "error", "message": error_message}

    processed_count = 0
    new_quotes_count = 0
    skipped_count = 0
    skipped_headers_count = 0
    
    for i, row in enumerate(all_rows):
        original_row_number = i + 1
        try:
            # Пропускаем пустые строки или строки-заголовки
            if not row or not any(field.strip() for field in row) or row[0].strip().lower() in ['id', 'l:id']:
                log.info(f"Пропуск строки {original_row_number}: это заголовок или пустая строка.")
                skipped_headers_count += 1
                continue

            # Определяем индексы колонок
            date_str = _clean_prefixed_value(row[1]).strip() if len(row) > 1 else None
            client_name = _clean_prefixed_value(row[15]).strip() if len(row) > 15 else "Без имени"
            phone_number = _normalize_phone(row[16]) if len(row) > 16 else ""
            business_type = _clean_prefixed_value(row[13]).strip() if len(row) > 13 else None
            
            # Если имя пустое, пробуем взять его из другой колонки
            if client_name == "Без имени" and len(row) > 12:
                client_name = _clean_prefixed_value(row[12]).strip()

            parsed_date = _parse_date(date_str)

            message = f"Лид из рекламной кампании. Бизнес: {business_type or 'не указан'}"
            if parsed_date:
                message += f". Дата из таблицы: {parsed_date.strftime('%d.%m.%Y')}"

            if not phone_number:
                log.warning(f"Пропуск строки {original_row_number}: не указан номер телефона.")
                continue

            contact = await _get_or_create_contact(db, name=client_name, phone=phone_number)
            await db.flush()

            stmt = select(QuoteRequest).where(
                QuoteRequest.contact_id == contact.id,
                QuoteRequest.message == message
            )
            existing_quote = (await db.execute(stmt)).scalars().first()
            if existing_quote:
                log.info(f"Пропуск дубликата для '{contact.full_name}'. Заявка с таким сообщением уже существует.")
                skipped_count += 1
                continue

            quote = await _create_quote_request(
                db=db,
                contact_id=contact.id,
                message=message,
                source=QuoteRequest.SourceEnum.CONTACT_FORM
            )
            
            if business_type:
                quote.business_type = business_type
            
            if parsed_date:
                quote.created_at = parsed_date
            
            db.add(quote)
            await db.flush()
            await _notify_managers(db, quote, contact.full_name)

            processed_count += 1
            new_quotes_count += 1
            log.info(f"Обработан лид для '{contact.full_name}'. Создана новая заявка #{quote.id}")

        except IndexError as e:
            log.warning(f"Пропуск строки {original_row_number}: неверная структура. Ошибка: {e}. Строка: {row}")
        except Exception as e:
            log.error(f"Ошибка при обработке строки {original_row_number}: {row}. Ошибка: {e}")
            await db.rollback()

    await db.commit()
    
    message = f"Импорт завершен! Обработано строк: {processed_count}. Создано новых заявок: {new_quotes_count}. Пропущено дубликатов: {skipped_count}. Пропущено заголовков/пустых строк: {skipped_headers_count}."
    log.info(message)
    return {"status": "success", "message": message, "processed": processed_count, "created": new_quotes_count}