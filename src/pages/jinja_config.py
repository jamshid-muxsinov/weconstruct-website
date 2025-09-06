import os
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from datetime import datetime
from cachetools import TTLCache
from starlette_wtf import csrf_token
from urllib.parse import urlencode
import re
import pytz
templates = Jinja2Templates(directory="src/templates", extensions=['jinja2.ext.do'])


translation_cache = TTLCache(maxsize=2000, ttl=3600)

STATUS_DISPLAY_MAP = {
    'imported': 'Импортировано',
    'qualification': 'Квалификация',
    'contacted': 'Контакт установлен',
    'proposal': 'Предложение',
    'negotiation': 'Переговоры',
    'closed': 'Успешно закрыто',
    'archived': 'В архиве',
}

def get_status_display(status):
    status_key = getattr(status, 'value', str(status))
    return STATUS_DISPLAY_MAP.get(status_key, status_key.replace('_', ' ').capitalize())


def format_phone(value: str) -> str:
    """Форматирует номер телефона в вид +998 (XX) XXX-XX-XX."""
    if not value:
        return "—"
    
    digits = re.sub(r'\D', '', value)
    
    if len(digits) == 12 and digits.startswith('998'):
        pass
    elif len(digits) == 9:
        digits = '998' + digits
    else:
        return value
        
    return f"+{digits[0:3]} ({digits[3:5]}) {digits[5:8]}-{digits[8:10]}-{digits[10:12]}"

def format_number(value):
    if value is None:
        return ""
    try:
        return f"{int(value):,}".replace(",", " ")
    except (ValueError, TypeError):
        return value

def t_get(request: Request, obj: object, field_name: str) -> str:
    locale = getattr(request.state, 'locale', 'ru')
    obj_id = getattr(obj, 'id', None)
    if obj_id:
        cache_key = f"translation_{obj.__class__.__name__}_{obj_id}_{field_name}_{locale}"
        cached_value = translation_cache.get(cache_key)
        if cached_value is not None:
            return cached_value
    value = getattr(obj, f"{field_name}_{locale}", None)
    if value is None or value == '':
        value = getattr(obj, f"{field_name}_ru", None)
    result = value or ''
    if obj_id:
        translation_cache[cache_key] = result
    return result

def format_localtime(utc_dt):
    """Конвертирует UTC datetime в локальное время Ташкента и форматирует."""
    if not utc_dt:
        return ""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=pytz.utc)
    
    tashkent_tz = pytz.timezone('Asia/Tashkent')
    local_dt = utc_dt.astimezone(tashkent_tz)
    return local_dt.strftime('%d.%m.%Y %H:%M')

templates.env.globals['hasattr'] = hasattr
templates.env.globals['current_year'] = datetime.now().year
templates.env.globals['t_get'] = t_get
templates.env.globals['csrf_token'] = csrf_token
templates.env.globals['urlencode'] = urlencode
templates.env.globals['get_status_display'] = get_status_display
templates.env.filters['capfirst'] = lambda x: x.capitalize() if x else ''
templates.env.filters['format_number'] = format_number
templates.env.filters['format_phone'] = format_phone
templates.env.filters['localtime'] = format_localtime