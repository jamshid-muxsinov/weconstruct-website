import os
from fastapi.templating import Jinja2Templates
from fastapi import Request
from datetime import datetime
from cachetools import TTLCache
from starlette_wtf import csrf_token
templates = Jinja2Templates(directory="src/templates")

translation_cache = TTLCache(maxsize=2000, ttl=3600)

def static(request: Request, path: str) -> str:
    try:
        return request.url_for('static', path=path)
    except RuntimeError:
        return f"/static/{path}"

def media(request: Request, path: str) -> str:
    if not path:
        return static(request, 'img/placeholder.png')
    try:
        return request.url_for('media', path=path)
    except RuntimeError:
        return f"/media/{path}"

def format_number(value):
    if value is None:
        return ""
    try:
        return f"{int(value):,}".replace(",", " ")
    except (ValueError, TypeError):
        return value

def t_get(request: Request, obj: object, field_name: str) -> str:
    """
    СИНХРОННАЯ функция для получения перевода поля объекта.
    Использует собственный in-memory кэш.
    """
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
templates.env.globals['static'] = static
templates.env.globals['media'] = media
templates.env.globals['hasattr'] = hasattr
templates.env.globals['current_year'] = datetime.now().year
templates.env.globals['t_get'] = t_get
templates.env.globals['csrf_token'] = csrf_token
templates.env.filters['capfirst'] = lambda x: x.capitalize() if x else ''
templates.env.filters['format_number'] = format_number