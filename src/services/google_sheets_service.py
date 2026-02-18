# src/services/google_sheets_service.py

import logging
import os
import time

import gspread
from google.oauth2.service_account import Credentials

from src.core.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]

SPREADSHEET_ID = "16dZ3_sWE1yYUhYmtfpdNlbWDhRrltNNGMtroTmzkNpo"
WORKSHEET_NAME = "Gullola" 
STATUS_COLUMN = 7 


def get_gspread_client() -> gspread.Client | None:
    """Аутентифицируется и возвращает клиент gspread."""
    credentials_path = settings.GOOGLE_CREDENTIALS_FILE
    
    if not credentials_path:
        log.warning("Путь к файлу ключей GOOGLE_CREDENTIALS_FILE не указан в .env файле.")
        return None

    if not os.path.exists(credentials_path):
        log.error(f"Файл ключей не найден по пути: {credentials_path}. Убедитесь, что файл существует и правильно смонтирован в Docker.")
        return None

    if not os.path.isfile(credentials_path):
        log.error(f"Ошибка: Путь '{credentials_path}' указывает на папку, а не на файл. Проверьте ваш Docker-монтирование.")
        return None

    try:
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        log.error(f"Ошибка аутентификации в Google Sheets: {e}", exc_info=True)
        return None


def update_status_in_sheet(sheet_row_id: str, new_status_text: str):
    """
    Находит строку по ID и обновляет статус. 
    Это блокирующая функция, ее нужно запускать в отдельном потоке.
    """
    client = get_gspread_client()
    if not client:
        return

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

            cell = worksheet.find(sheet_row_id, in_column=1)

            if cell:
                worksheet.update_cell(cell.row, STATUS_COLUMN, new_status_text)
                log.info(f"Статус для лида ID '{sheet_row_id}' обновлен на '{new_status_text}' в Google Sheets.")
            else:
                log.warning(f"Лид с ID '{sheet_row_id}' не найден в Google Sheets.")
            return
        except gspread.exceptions.WorksheetNotFound:
            log.error(f"Лист '{WORKSHEET_NAME}' не найден в таблице.")
            return
        except gspread.exceptions.APIError as e:
            if attempt == max_attempts:
                log.error(f"Ошибка API Google Sheets: {e}", exc_info=True)
                return
        except Exception as e:
            if attempt == max_attempts:
                log.error(f"Непредвиденная ошибка при обновлении Google Sheets: {e}", exc_info=True)
                return
        time.sleep(attempt)
