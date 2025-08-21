# src/services/sheets_importer_service.py

import logging
import re
import requests
import csv
import io
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select # <-- Добавь импорт

from src.services.shop_service import _get_or_create_contact, _create_quote_request, _notify_managers
from src.models.shop_models import QuoteRequest

log = logging.getLogger(__name__)

def _normalize_phone(phone: str) -> str:
    """Приводит номер телефона к единому формату E.164 (+998...)."""
    if not phone:
        return ""
    # Оставляем только цифры
    digits = re.sub(r'\D', '', phone)
    
    # Если номер начинается с 998 и имеет 12 цифр, просто добавляем +
    if len(digits) == 12 and digits.startswith('998'):
        return f"+{digits}"
    # Если номер имеет 9 цифр (код оператора + номер), добавляем +998
    if len(digits) == 9:
        return f"+998{digits}"
        
    # Возвращаем как есть, если формат неизвестен
    return phone

async def import_leads_from_sheet(db: AsyncSession, spreadsheet_id: str, gid: int = 0):
    """
    Основная функция для импорта лидов из Google Sheets.
    Проверяет наличие дубликатов перед созданием новой заявки.
    """
    log.info(f"Starting import from Google Sheet ID: {spreadsheet_id}, GID: {gid}")

    export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
    try:
        response = requests.get(export_url, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
        csv_data = io.StringIO(response.text)
        reader = csv.reader(csv_data)
        
        header = next(reader) # Читаем заголовок
        rows = list(reader)

        if not rows:
            log.info("No data found in the sheet.")
            return {"status": "success", "message": "В таблице нет данных для импорта.", "processed": 0, "created": 0}

    except requests.exceptions.RequestException as e:
        error_message = f"Ошибка доступа к Google Sheets: {e}. Убедитесь, что таблица доступна по ссылке."
        log.error(error_message)
        return {"status": "error", "message": error_message}
    except Exception as e:
        error_message = f"Непредвиденная ошибка при чтении таблицы: {e}"
        log.error(error_message)
        return {"status": "error", "message": error_message}

    processed_count = 0
    new_quotes_count = 0
    skipped_count = 0
    
    for i, row in enumerate(rows):
        original_row_number = i + 2 
        try:
            client_name = row[15].strip() if len(row) > 15 and row[15] else "Без имени"
            phone_number = _normalize_phone(row[16]) if len(row) > 16 and row[16] else ""
            business_type = row[13].strip() if len(row) > 13 and row[13] else None
            
            message = f"Лид из рекламной кампании. Бизнес: {business_type or 'не указан'}"

            if not phone_number:
                log.warning(f"Пропуск строки {original_row_number}: не указан номер телефона.")
                continue

            contact = await _get_or_create_contact(db, name=client_name, phone=phone_number)
            await db.flush()

            # --- ПРОВЕРКА НА ДУБЛИКАТЫ ---
            stmt = select(QuoteRequest).where(
                QuoteRequest.contact_id == contact.id,
                QuoteRequest.message == message
            )
            existing_quote = (await db.execute(stmt)).scalars().first()
            if existing_quote:
                log.info(f"Пропуск дубликата для '{contact.full_name}'. Заявка с таким сообщением уже существует.")
                skipped_count += 1
                continue
            # --- КОНЕЦ ПРОВЕРКИ ---

            quote = await _create_quote_request(
                db=db,
                contact_id=contact.id,
                message=message,
                source=QuoteRequest.SourceEnum.CONTACT_FORM
            )
            
            if business_type:
                quote.business_type = business_type
                db.add(quote)
            
            await db.flush()
            await _notify_managers(db, quote, contact.full_name)

            processed_count += 1
            new_quotes_count += 1
            log.info(f"Обработан лид для '{contact.full_name}'. Создана новая заявка #{quote.id}")

        except IndexError:
            log.warning(f"Пропуск строки {original_row_number}: неверная структура. Строка: {row}")
        except Exception as e:
            log.error(f"Ошибка при обработке строки {original_row_number}: {row}. Ошибка: {e}")
            await db.rollback()

    await db.commit()
    
    message = f"Импорт завершен! Обработано строк: {processed_count}. Создано новых заявок: {new_quotes_count}. Пропущено дубликатов: {skipped_count}."
    log.info(message)
    return {"status": "success", "message": message, "processed": processed_count, "created": new_quotes_count}