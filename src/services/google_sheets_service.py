# src/services/google_sheets_service.py

import logging
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
    if not settings.GOOGLE_CREDENTIALS_FILE:
        log.warning("Путь к файлу ключей GOOGLE_CREDENTIALS_FILE не указан.")
        return None
    try:
        creds = Credentials.from_service_account_file(settings.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        return client
    except FileNotFoundError:
        log.error(f"Файл ключей не найден: {settings.GOOGLE_CREDENTIALS_FILE}")
        return None
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

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        
        cell = worksheet.find(sheet_row_id, in_column=1) 
        
        if cell:
            worksheet.update_cell(cell.row, STATUS_COLUMN, new_status_text)
            log.info(f"Статус для лида ID '{sheet_row_id}' обновлен на '{new_status_text}' в Google Sheets.")
        else:
            log.warning(f"Лид с ID '{sheet_row_id}' не найден в Google Sheets.")

    except gspread.exceptions.WorksheetNotFound:
        log.error(f"Лист '{WORKSHEET_NAME}' не найден в таблице.")
    except gspread.exceptions.APIError as e:
        log.error(f"Ошибка API Google Sheets: {e}")
    except Exception as e:
        log.error(f"Непредвиденная ошибка при обновлении Google Sheets: {e}", exc_info=True)