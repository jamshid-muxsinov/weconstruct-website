# src/pages/jinja_config.py

import os
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from datetime import datetime
from cachetools import TTLCache
from starlette_wtf import csrf_token
from urllib.parse import urlencode
import re
import pytz
from pathlib import Path
import jinja2

from .translations import TRANSLATIONS

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

templates = Jinja2Templates(directory=TEMPLATE_DIR, extensions=['jinja2.ext.do'])

def configure_jinja_templates(app_templates: Jinja2Templates):
    """Применяет все глобальные переменные и фильтры к экземпляру Jinja2Templates."""
    
    translation_cache = TTLCache(maxsize=2000, ttl=3600)

    @jinja2.pass_context
    def translate_ui(context: dict, key: str, **kwargs) -> str:
        request = context.get('request')
        if not request:
            return key
        locale = getattr(request.state, 'locale', 'ru')
        translation_dict = TRANSLATIONS.get(key, {})
        translation = translation_dict.get(locale, TRANSLATIONS.get(key, {}).get('ru', key))
        if kwargs:
            try:
                return translation.format(**kwargs)
            except (KeyError, ValueError):
                return translation
        return translation

    @jinja2.pass_context
    def get_status_display(context: dict, status, locale: str = None) -> str:
        if locale is None:
            request = context.get('request')
            if request:
                locale = getattr(request.state, 'locale', 'ru')
            else:
                locale = 'ru' 

        status_key = getattr(status, 'value', str(status))
        
        translation_key = f"status_{status_key}"
        translation_dict = TRANSLATIONS.get(translation_key, {})
        translation = translation_dict.get(locale, TRANSLATIONS.get(translation_key, {}).get('ru', status_key))

        return translation

    def format_phone(value: str) -> str:
        if not value: return "—"
        digits = re.sub(r'\D', '', value)
        if len(digits) == 12 and digits.startswith('998'): pass
        elif len(digits) == 9: digits = '998' + digits
        else: return value
        return f"+{digits[0:3]} ({digits[3:5]}) {digits[5:8]}-{digits[8:10]}-{digits[10:12]}"

    def format_number(value):
        if value is None: return ""
        try: return f"{int(value):,}".replace(",", " ")
        except (ValueError, TypeError): return value

    def t_get(request: Request, obj: object, field_name: str) -> str:
        locale = getattr(request.state, 'locale', 'ru')
        obj_id = getattr(obj, 'id', None)
        if obj_id:
            cache_key = f"translation_{obj.__class__.__name__}_{obj_id}_{field_name}_{locale}"
            cached_value = translation_cache.get(cache_key)
            if cached_value is not None: return cached_value
        value = getattr(obj, f"{field_name}_{locale}", None)
        if value is None or value == '': value = getattr(obj, f"{field_name}_ru", None)
        result = value or ''
        if obj_id: translation_cache[cache_key] = result
        return result

    def format_localtime(utc_dt):
        if not utc_dt: return ""
        if utc_dt.tzinfo is None: utc_dt = utc_dt.replace(tzinfo=pytz.utc)
        tashkent_tz = pytz.timezone('Asia/Tashkent')
        local_dt = utc_dt.astimezone(tashkent_tz)
        return local_dt.strftime('%d.%m.%Y %H:%M')

    app_templates.env.globals['_'] = translate_ui
    app_templates.env.globals['hasattr'] = hasattr
    app_templates.env.globals['current_year'] = datetime.now().year
    app_templates.env.globals['t_get'] = t_get
    app_templates.env.globals['csrf_token'] = csrf_token
    app_templates.env.globals['urlencode'] = urlencode
    app_templates.env.globals['get_status_display'] = get_status_display
    app_templates.env.filters['capfirst'] = lambda x: x.capitalize() if x else ''
    app_templates.env.filters['format_number'] = format_number
    app_templates.env.filters['format_phone'] = format_phone
    app_templates.env.filters['localtime'] = format_localtime
    
    print(f"--- Jinja templates instance {id(app_templates)} configured successfully ---")