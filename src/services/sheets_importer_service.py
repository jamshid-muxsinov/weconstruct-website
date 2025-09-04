# src/services/sheets_importer_service.py

import logging
import re
import requests
import csv
import io
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

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
        pass

    # Пробуем форматы MM.DD.YY и DD.MM.YY
    formats_to_try = [
        "%m.%d.%y",  # 8.13.25
        "%d.%m.%y",  # 13.8.25
        "%m/%d/%y",
        "%d/%m/%y",
        "%Y-%m-%d",
    ]
    
    for fmt in formats_to_try:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            # Если год двузначный, считаем, что это 20xx год
            if parsed_date.year < 100:
                 parsed_date = parsed_date.replace(year=parsed_date.year + 2000)
            log.info(f"Успешно распарсена дата '{date_str}' как {parsed_date.strftime('%Y-%m-%d')}")
            return parsed_date
        except ValueError:
            continue
    
    log.warning(f"Не удалось распарсить дату: '{date_str}'")
    return None

def _normalize_phone(phone: str) -> str:
    """Приводит номер телефона к единому формату +998..."""
    if not phone:
        return ""
    # Удаляем все не-цифры
    digits = re.sub(r'\D', '', phone)
    
    if len(digits) == 12 and digits.startswith('998'):
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
        
    return phone # Возвращаем как есть, если формат неизвестен

def _clean_prefixed_value(value: str) -> str:
    """Удаляет префиксы типа 'l:', 'p:' и т.д., которые добавляет Facebook."""
    if value and ':' in value and len(value.split(':', 1)[0]) <= 2:
        return value.split(':', 1)[1]
    return value

async def import_leads_from_sheet(db: AsyncSession, spreadsheet_id: str, gid: int = 0):
    """
    Основная функция для импорта лидов из Google Sheets.
    Теперь настроена на вашу структуру таблицы.
    """
    log.info(f"Запуск импорта из Google Sheet ID: {spreadsheet_id}, GID: {gid}")
    export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
    try:
        response = requests.get(export_url, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
        csv_data = io.StringIO(response.text)
        reader = csv.reader(csv_data)
        all_rows = list(reader)
        if not all_rows:
            return {"status": "success", "message": "В таблице нет данных для импорта.", "processed": 0, "created": 0}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Ошибка доступа к Google Sheets: {e}. Убедитесь, что таблица доступна по ссылке."}
    except Exception as e:
        return {"status": "error", "message": f"Непредвиденная ошибка при чтении таблицы: {e}"}

    processed_count = 0
    new_quotes_count = 0
    skipped_duplicates_count = 0
    skipped_headers_count = 0
    
    for i, row in enumerate(all_rows):
        original_row_number = i + 1
        try:
            # Пропускаем пустые строки или строки-заголовки
            if not row or not any(field.strip() for field in row) or row[0].strip().lower() == 'id':
                log.info(f"Пропуск строки {original_row_number}: это заголовок или пустая строка.")
                skipped_headers_count += 1
                continue

            # <<< ИЗМЕНЕНИЕ: Новая логика извлечения данных по колонкам >>>
            # B: created_time (индекс 1)
            date_str = _clean_prefixed_value(row[1]).strip() if len(row) > 1 else None
            # N: qaysi_biznes... (индекс 13)
            business_type = _clean_prefixed_value(row[13]).strip() if len(row) > 13 else "Не указан"
            # P: full_name (индекс 15)
            client_name = _clean_prefixed_value(row[15]).strip() if len(row) > 15 else "Без имени"
            # Q: phone_number (индекс 16)
            phone_number_raw = _clean_prefixed_value(row[16]).strip() if len(row) > 16 else ""
            
            # Если имя в колонке P пустое, пробуем взять его из колонки M (ism_familiyangiz?)
            if not client_name or client_name == "Без имени":
                client_name = _clean_prefixed_value(row[12]).strip() if len(row) > 12 else "Без имени"
            
            # Если телефон в колонке Q пустой, пробуем взять его из колонки O (telefon_raqamingiz?)
            if not phone_number_raw:
                phone_number_raw = _clean_prefixed_value(row[14]).strip() if len(row) > 14 else ""

            phone_number = _normalize_phone(phone_number_raw)
            # <<< КОНЕЦ ИЗМЕНЕНИЙ >>>

            if not phone_number:
                log.warning(f"Пропуск строки {original_row_number}: не указан номер телефона.")
                continue

            # Создаем или находим контакт
            contact = await _get_or_create_contact(db, name=client_name, phone=phone_number)
            await db.flush()

            # Проверяем на дубликаты более надежно
            parsed_date = _parse_date(date_str)
            duplicate_check_stmt = select(QuoteRequest).where(
                QuoteRequest.contact_id == contact.id,
                QuoteRequest.business_type == business_type
            )
            if parsed_date:
                # Ищем дубликат только за тот же день
                duplicate_check_stmt = duplicate_check_stmt.where(func.date(QuoteRequest.created_at) == parsed_date.date())

            existing_quote = (await db.execute(duplicate_check_stmt)).scalars().first()
            if existing_quote:
                log.info(f"Пропуск дубликата для '{contact.full_name}' от {parsed_date.strftime('%Y-%m-%d') if parsed_date else 'N/A'}.")
                skipped_duplicates_count += 1
                continue

            # Создаем новую заявку
            message_for_crm = f"Лид из рекламной кампании. Тип бизнеса: {business_type}"
            quote = await _create_quote_request(
                db=db,
                contact_id=contact.id,
                message=message_for_crm,
                source=QuoteRequest.SourceEnum.CONTACT_FORM # Источник - импорт
            )
            
            quote.business_type = business_type
            
            # <<< ИЗМЕНЕНИЕ: Присваиваем дату из таблицы >>>
            # Если дата была успешно распознана, устанавливаем ее как дату создания заявки
            if parsed_date:
                quote.created_at = parsed_date
            
            db.add(quote)
            await db.flush() # Получаем ID для логгирования
            
            await _notify_managers(db, quote, contact.full_name)

            processed_count += 1
            new_quotes_count += 1
            log.info(f"Обработан лид для '{contact.full_name}'. Создана новая заявка #{quote.id} с датой {quote.created_at}")

        except IndexError as e:
            log.warning(f"Пропуск строки {original_row_number}: неверная структура (не хватает колонок). Ошибка: {e}. Строка: {row}")
        except Exception as e:
            log.error(f"Критическая ошибка при обработке строки {original_row_number}: {row}. Ошибка: {e}")
            await db.rollback()

    await db.commit()
    
    message = f"Импорт завершен! Создано новых заявок: {new_quotes_count}. Пропущено дубликатов: {skipped_duplicates_count}. Пропущено заголовков/пустых строк: {skipped_headers_count}."
    log.info(message)
    return {"status": "success", "message": message, "processed": processed_count, "created": new_quotes_count}