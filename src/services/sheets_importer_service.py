# src/services/sheets_importer_service.py

import logging
import re
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

from src.services.shop_service import _get_or_create_contact, _create_quote_request, _notify_managers
from src.models.shop_models import QuoteRequest, GoogleSheetLead, Contact

log = logging.getLogger(__name__)


async def process_single_lead_row(db: AsyncSession, row: list):
    if not row or len(row) < 1 or not row[0] or not str(row[0]).strip():
        log.warning(f"Получена некорректная или пустая строка для обработки, пропуск: {row}")
        return

    sheet_row_id = str(row[0]).strip()
    original_row_number_info = f"(ID: {sheet_row_id})"

    try:
        async with db.begin_nested():
            stmt = select(GoogleSheetLead).where(GoogleSheetLead.sheet_row_id == sheet_row_id)
            result = await db.execute(stmt)
            existing_lead = result.scalars().first()

            if existing_lead:
                log.info(f"Лид {original_row_number_info} уже существует в базе. Пропуск.")
                return

            client_name = (row[1].strip() if len(row) > 1 else "Без имени")[:150]
            business_type = (row[2].strip() if len(row) > 2 else "")[:255]
            phone_1 = (row[3].strip() if len(row) > 3 else "")
            telegram = (row[4].strip() if len(row) > 4 else "")[:100]
            phone_2 = (row[5].strip() if len(row) > 5 else "")
            status_from_sheet_raw = (row[6].strip() if len(row) > 6 else "")
            comment = (row[7].strip() if len(row) > 7 else "")

            phone_number = _normalize_phone(phone_1 or phone_2)[:50]

            if not phone_number:
                raise ValueError("Не найден или некорректен номер телефона.")

            contact = await _get_or_create_contact(db, name=client_name, phone=phone_number)
            
            # --- ГЛАВНОЕ ИСПРАВЛЕНИЕ: ПРОВЕРКА, ЧТО КОНТАКТ БЫЛ СОЗДАН ---
            if not contact:
                # Это может произойти в редких случаях гонки состояний
                raise Exception("Не удалось создать или найти контакт.")
            
            await db.flush()

            message_parts = []
            if status_from_sheet_raw: message_parts.append(f"Статус из таблицы: {status_from_sheet_raw}")
            if business_type: message_parts.append(f"Тип бизнеса: {business_type}")
            if telegram: message_parts.append(f"Telegram: {telegram}")
            if comment: message_parts.append(f"Комментарий из таблицы: {comment}")
            message_for_crm = "\n".join(message_parts)

            quote = await _create_quote_request(db, contact.id, message_for_crm, source="contact_form")
            quote.business_type = business_type
            quote.status = QuoteRequest.StatusEnum.IMPORTED
            
            await db.flush()

            new_lead_entry = GoogleSheetLead(
                sheet_row_id=sheet_row_id, 
                spreadsheet_id="16dZ3_sWE1yYUhYmtfpdNlbWDhRrltNNGMtroTmzkNpo",
                status=GoogleSheetLead.StatusEnum.IMPORTED,
                processed_at=datetime.utcnow(),
                quote_request_id=quote.id,
                raw_data=row
            )
            db.add(new_lead_entry)
            
            await _notify_managers(db, quote, contact.full_name)
            log.info(f"Создана новая заявка #{quote.id} для лида {original_row_number_info}")

        await db.commit()

    except IntegrityError as e:
        await db.rollback()
        log.error(f"Ошибка целостности данных при обработке строки {original_row_number_info}: {e}", exc_info=False)
    except Exception as e:
        await db.rollback()
        log.error(f"Непредвиденная ошибка при обработке строки {original_row_number_info}: {e}", exc_info=False)


def _normalize_phone(phone: str) -> str:
    if not phone: return ""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 12 and digits.startswith('998'): return f"+{digits}"
    if len(digits) == 9: return f"+998{digits}"
    return phone