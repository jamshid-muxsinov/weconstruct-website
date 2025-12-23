# src/services/sheets_importer_service.py

import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.services.shop_service import _get_or_create_contact, _create_quote_request, _notify_managers
from src.models.shop_models import QuoteRequest, GoogleSheetLead

log = logging.getLogger(__name__)

async def process_single_lead_row(session: AsyncSession, lead_data: Dict[str, Any]):
    """
    Обрабатывает один лид. Поле сообщения клиента теперь всегда будет пустым.
    """
    sheet_row_id = lead_data.get("sheet_row_id")
    if not sheet_row_id or not lead_data.get("phone"):
        log.warning(f"Лид пропущен из-за отсутствия ID или телефона. Данные: {lead_data}")
        return

    # Проверка на дубликат импорта
    stmt = select(GoogleSheetLead).where(GoogleSheetLead.sheet_row_id == sheet_row_id)
    result = await session.execute(stmt)
    if result.scalars().first():
        log.info(f"Лид с ID {sheet_row_id} уже существует в базе. Пропуск.")
        return

    client_name = lead_data.get("client_name", "Без имени")
    phone_number = lead_data.get("phone")
    business_type = lead_data.get("business_type", "")
    region = lead_data.get("region", "")

    # Поиск или создание контакта
    contact = await _get_or_create_contact(session, name=client_name, phone=phone_number)
    if not contact:
        raise Exception(f"Не удалось создать/найти контакт для телефона {phone_number}")

    # Формирование темы
    subject_parts = []
    if region and region not in ["Не указан", "Неизвестно (старый формат)"]:
        subject_parts.append(region)
    if business_type:
        subject_parts.append(business_type)
    
    subject = f"Лид из Facebook ({' / '.join(subject_parts)})" if subject_parts else "Лид из Facebook"
    
    # Сделано пустым по вашему запросу
    message_for_crm = ""

    # Создание заявки в CRM
    quote = await _create_quote_request(session, contact.id, message_for_crm, subject, source="contact_form")
    quote.business_type = business_type

    # Регистрация факта импорта из Google Sheets
    new_lead_entry = GoogleSheetLead(
        sheet_row_id=sheet_row_id,
        spreadsheet_id="16dZ3_sWE1yYUhYmtfpdNlbWDhRrltNNGMtroTmzkNpo",
        status=GoogleSheetLead.StatusEnum.IMPORTED,
        processed_at=datetime.utcnow(),
        quote_request_id=quote.id,
        raw_data=lead_data
    )
    session.add(new_lead_entry)
    
    # Уведомления менеджеров и в Telegram
    await _notify_managers(session, quote, contact.full_name)
    
    log.info(f"Успешно обработан и добавлен в сессию лид с ID {sheet_row_id}")