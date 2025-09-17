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

STATUS_MAPPING = {
    'yopildi': QuoteRequest.StatusEnum.ARCHIVED,
    'javob berdi': QuoteRequest.StatusEnum.CONTACTED,
    "2ta qo'ng'iroq": QuoteRequest.StatusEnum.CONTACTED,
    'тели учик': QuoteRequest.StatusEnum.ARCHIVED,
    'нархи екмади': QuoteRequest.StatusEnum.ARCHIVED,
    'бино курилган': QuoteRequest.StatusEnum.ARCHIVED,
    'пули ва жойи йук': QuoteRequest.StatusEnum.ARCHIVED,
    'пул керак экан': QuoteRequest.StatusEnum.ARCHIVED,
    'маблаги йук': QuoteRequest.StatusEnum.ARCHIVED,
    'хужжатини турилаб берадигани кк': QuoteRequest.StatusEnum.ARCHIVED,
    'пул топиб берадиган хомий кк экан': QuoteRequest.StatusEnum.ARCHIVED,
    'нарх киммат экан': QuoteRequest.StatusEnum.ARCHIVED,
    'текин дизайн ва лойиха кк экан': QuoteRequest.StatusEnum.ARCHIVED,
}

async def process_single_lead_row(db: AsyncSession, row: list):
    """
    Обрабатывает одну строку данных, полученную из Google Sheets через вебхук,
    используя вложенные транзакции для изоляции ошибок.
    """
    # Сначала проверяем, есть ли в строке вообще телефон
    phone_1 = (row[3].strip() if len(row) > 3 else "")
    phone_2 = (row[5].strip() if len(row) > 5 else "")
    if not (phone_1 or phone_2):
        sheet_row_id = str(row[0]).strip() if row and row[0] else "N/A"
        log.warning(f"Строка с ID: {sheet_row_id} пропущена, так как не содержит номера телефона.")
        return

    sheet_row_id = str(row[0]).strip()
    original_row_number_info = f"(ID: {sheet_row_id})"

    try:
        # Вложенная транзакция для изоляции ошибок
        async with db.begin_nested():
            stmt = select(GoogleSheetLead).where(GoogleSheetLead.sheet_row_id == sheet_row_id)
            result = await db.execute(stmt)
            existing_lead = result.scalars().first()

            if existing_lead:
                log.info(f"Лид {original_row_number_info} уже существует в базе. Пропуск.")
                return

            client_name = (row[1].strip() if len(row) > 1 else "Без имени")[:150]

            if client_name.startswith(("IMG_", "2025-", "+998")) or client_name.lower() in ["a", "x", "y", "r"]:
                log.info(f"Обнаружен технический или неполный лид (ID: {sheet_row_id}, Имя: {client_name}). Пропуск.")
                return

            business_type = (row[2].strip() if len(row) > 2 else "")[:255]
            telegram = (row[4].strip() if len(row) > 4 else "")[:100]
            status_from_sheet_raw = (row[6].strip() if len(row) > 6 else "")
            comment = (row[7].strip() if len(row) > 7 else "")

            phone_number = _normalize_phone(phone_1 or phone_2)[:50]

            contact = await _get_or_create_contact(db, name=client_name, phone=phone_number)
            if not contact:
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
            
            status_from_sheet_lower = status_from_sheet_raw.lower()
            crm_status = STATUS_MAPPING.get(status_from_sheet_lower)
            quote.status = crm_status if crm_status else QuoteRequest.StatusEnum.IMPORTED
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
        
        log.info(f"Успешно подготовлена к сохранению заявка для лида {original_row_number_info}")

    except (ValueError, IntegrityError) as e:
        log.error(f"Ошибка при обработке строки {original_row_number_info}: {e}", exc_info=False)
    except Exception as e:
        log.error(f"Непредвиденная ошибка при обработке строки {original_row_number_info}: {e}", exc_info=True)

def _normalize_phone(phone: str) -> str:
    if not phone: return ""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 12 and digits.startswith('998'): return f"+{digits}"
    if len(digits) == 9: return f"+998{digits}"
    return phone