import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.services.shop_service import _get_or_create_contact, _create_quote_request, _notify_managers
from src.models.shop_models import QuoteRequest, GoogleSheetLead

log = logging.getLogger(__name__)

# --- ИЗМЕНЕНИЕ 1: Убираем старую логику, она больше не нужна ---
# Функция _normalize_phone и STATUS_MAPPING удалены

async def process_single_lead_row(session: AsyncSession, lead_data: Dict[str, Any]) -> bool:
    """
    Обрабатывает один структурированный лид в рамках сессии.
    Возвращает True в случае успеха и False в случае любой ошибки.
    """
    sheet_row_id = lead_data.get("sheet_row_id")
    if not sheet_row_id:
        log.warning(f"Лид пропущен, так как отсутствует sheet_row_id. Данные: {lead_data}")
        return False

    phone_number = lead_data.get("phone")
    if not phone_number:
        log.warning(f"Лид {sheet_row_id} пропущен, так как отсутствует номер телефона.")
        return False

    try:
        async with session.begin():
            # Проверяем, не импортировали ли мы этот лид ранее
            stmt = select(GoogleSheetLead).where(GoogleSheetLead.sheet_row_id == sheet_row_id)
            result = await session.execute(stmt)
            existing_lead = result.scalars().first()

            if existing_lead:
                log.info(f"Лид с ID {sheet_row_id} уже существует в базе. Пропуск.")
                return True 

            client_name = lead_data.get("client_name", "Без имени")
            business_type = lead_data.get("business_type", "")
            
            # Создаем или находим контакт по номеру телефона
            contact = await _get_or_create_contact(session, name=client_name, phone=phone_number)
            if not contact:
                # На всякий случай, если что-то пошло не так
                raise Exception(f"Не удалось создать/найти контакт для телефона {phone_number}")

            # Формируем тему и сообщение для CRM
            subject = f"Лид из Facebook ({business_type})" if business_type else "Лид из Facebook"
            message_for_crm = f"Автоматический импорт из Google Sheets.\nИсходные данные:\n{lead_data.get('raw_data', '')}"

            # Создаем заявку
            quote = await _create_quote_request(session, contact.id, message_for_crm, subject, source="contact_form")
            quote.business_type = business_type
            
            # Создаем запись в реестре GoogleSheetLead
            new_lead_entry = GoogleSheetLead(
                sheet_row_id=sheet_row_id, 
                spreadsheet_id="16dZ3_sWE1yYUhYmtfpdNlbWDhRrltNNGMtroTmzkNpo",
                status=GoogleSheetLead.StatusEnum.IMPORTED,
                processed_at=datetime.utcnow(),
                quote_request_id=quote.id,
                raw_data=lead_data 
            )
            session.add(new_lead_entry)
            
            # Уведомляем менеджеров
            await _notify_managers(session, quote, contact.full_name)
        
        log.info(f"Успешно импортирован лид с ID {sheet_row_id}")
        return True

    except Exception as e:
        log.error(f"Ошибка при обработке лида {sheet_row_id}: {e}", exc_info=True)
        # Откатываем транзакцию session.begin() сделает это автоматически
        return False