# src/services/telegram_service.py

import logging
import httpx
from typing import Dict, Any
from src.core.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

def _escape_markdown(text: Any) -> str:
    """
    Экранирует специальные символы для Telegram MarkdownV2.
    """
    if not isinstance(text, str):
        text = str(text)
    
    # --- НАЧАЛО ИЗМЕНЕНИЯ: ИСПОЛЬЗУЕМ ПОЛНЫЙ СПИСОК СИМВОЛОВ ---
    # Telegram требует экранировать эти символы в режиме MarkdownV2
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    return "".join(f'\\{char}' if char in escape_chars else char for char in text)


async def send_new_lead_notification(lead_data: Dict[str, Any]):
    """
    Отправляет отформатированное уведомление о новом лиде в Telegram.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        log.warning("TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не установлены. Уведомление не отправлено.")
        return

    # Экранируем данные перед вставкой в сообщение
    client_name = _escape_markdown(lead_data.get("client_name", "N/A"))
    phone_raw = lead_data.get("phone", "")
    phone_escaped = _escape_markdown(phone_raw) # Экранированная версия для отображения
    business_type = _escape_markdown(lead_data.get("business_type", "N/A"))
    
    # URL для звонка должен содержать только цифры
    phone_url = f"tel:{''.join(filter(str.isdigit, phone_raw))}"

    message = (
        f"🔥 *Новый лид из Facebook/Instagram*\n\n"
        f"👤 *Клиент:* {client_name}\n"
        f"📞 *Телефон:* [{phone_escaped}]({phone_url})\n"
        f"🏢 *Тип бизнеса:* {business_type}"
    )

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "MarkdownV2"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(api_url, json=params)
            response.raise_for_status() # Вызовет ошибку для кодов 4xx и 5xx
            log.info(f"Уведомление о лиде '{lead_data.get('client_name')}' успешно отправлено в Telegram.")
        except httpx.HTTPStatusError as e:
            # --- НАЧАЛО ИЗМЕНЕНИЯ: УЛУЧШЕННОЕ ЛОГИРОВАНИЕ ---
            log.error(
                f"Ошибка API Telegram: {e.response.status_code} - {e.response.text}\n"
                f"Отправляемый текст (до форматирования): {message}",
                exc_info=True
            )
            # --- КОНЕЦ ИЗМЕНЕНИЯ ---
        except Exception as e:
            log.error(f"Не удалось отправить уведомление в Telegram: {e}", exc_info=True)