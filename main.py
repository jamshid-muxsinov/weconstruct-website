# src/main.py

import logging
import sys
import traceback
from typing import Callable

import uvicorn
from fastapi import FastAPI, Request, Depends, APIRouter, Path
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from pathlib import Path as FilePath
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response
from starlette_wtf import CSRFProtectMiddleware

from src.core.config import get_settings
from src.core.db import check_db_connection, async_session_factory
from src.core.security import get_current_active_user
from src.pages.admin.router import router as admin_router, unprotected_router as admin_unprotected_router
from src.pages.shop_pages import router as shop_router, root_router as shop_root_router
from src.services.user_service import create_first_superuser
from src.core.cache import init_cache, cleanup_cache
from src.core.middleware import CacheMiddleware, RateLimitMiddleware
from src.core.cache_utils import schedule_cache_cleanup, warm_up_cache
from src.pages.jinja_config import templates

# --- БАЗОВАЯ НАСТРОЙКА ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)
settings = get_settings()
BASE_DIR = FilePath(__file__).resolve().parent

# --- ОБЩИЕ ОБРАБОТЧИКИ СОБЫТИЙ ---
async def on_startup():
    log.info("Application startup...")
    await check_db_connection()
    log.info("Creating first superuser if necessary...")
    async with async_session_factory() as session:
        await create_first_superuser(session)
    log.info("Superuser check complete.")
    log.info("Initializing cache...")
    await init_cache()
    log.info("Cache initialization complete.")
    await warm_up_cache()
    import asyncio
    asyncio.create_task(schedule_cache_cleanup())
    log.info("Cache cleanup scheduler started.")

async def on_shutdown():
    log.info("Application shutdown...")
    await cleanup_cache()
    log.info("Cache cleanup complete.")

# --- ФАБРИКА ДЛЯ ПРИЛОЖЕНИЯ АДМИНКИ (admin.weconstruct.uz) ---
def create_admin_app() -> FastAPI:
    fastapi_kwargs = {"title": "WeConstruct CRM"}
    if not settings.DEBUG:
        fastapi_kwargs.update({"docs_url": None, "redoc_url": None, "openapi_url": None})

    app = FastAPI(**fastapi_kwargs, on_startup=[on_startup], on_shutdown=[on_shutdown])

    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
    app.add_middleware(CSRFProtectMiddleware, csrf_secret=settings.SECRET_KEY)
    app.add_middleware(RateLimitMiddleware, max_requests=200, window_seconds=60)

    app.mount("/static", StaticFiles(directory=BASE_DIR / "src" / "static"), name="static")
    app.mount("/media", StaticFiles(directory=BASE_DIR / "media"), name="media")

    async def set_locale_admin(request: Request, locale: str = Path(..., description="Код языка (ru или uz)")):
        if locale not in ["ru", "uz"]:
            locale = "ru"
        request.state.locale = locale

    admin_router_with_locale = APIRouter(
        prefix="/{locale}", 
        dependencies=[Depends(set_locale_admin)]
    )
    admin_router_with_locale.include_router(admin_router)

    # <<< НАЧАЛО ИЗМЕНЕНИЯ: Убираем префиксы /admin >>>
    app.include_router(admin_unprotected_router) 
    app.include_router(
        admin_router_with_locale,
        dependencies=[Depends(get_current_active_user)]
    )
    
    @app.get("/", include_in_schema=False)
    async def admin_root_redirect(request: Request):
        # Редиректим на /ru/dashboard, так как префикса /admin в приложении больше нет
        return RedirectResponse(url=request.url_for('admin_dashboard', locale='ru'))
    # <<< КОНЕЦ ИЗМЕНЕНИЯ >>>
        
    add_pagination(app)

    @app.exception_handler(401)
    async def unauthorized_exception_handler(request: Request, exc: Exception):
        login_url = request.url_for('admin_login')
        return RedirectResponse(url=f"{login_url}?next={request.url.path}", status_code=302)

    @app.exception_handler(Exception)
    async def generic_admin_exception_handler(request: Request, exc: Exception):
        traceback.print_exc()
        context = {"request": request, "error_message": "Произошла внутренняя ошибка сервера."}
        return templates.TemplateResponse("admin/500.html", context, status_code=500)

    return app

# --- ФАБРИКА ДЛЯ ПРИЛОЖЕНИЯ ОСНОВНОГО САЙТА (weconstruct.uz) ---
def create_site_app() -> FastAPI:
    fastapi_kwargs = {"title": "WeConstruct Website"}
    if not settings.DEBUG:
        fastapi_kwargs.update({"docs_url": None, "redoc_url": None, "openapi_url": None})

    app = FastAPI(**fastapi_kwargs, root_path=settings.ROOT_PATH)

    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
    app.add_middleware(CSRFProtectMiddleware, csrf_secret=settings.SECRET_KEY)

    if settings.CACHE_ENABLED:
        app.add_middleware(CacheMiddleware, cache_ttl=settings.REDIS_TTL)
    app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)

    async def set_locale(request: Request, locale: str = Path(..., description="Код языка (ru или uz)")):
        if locale not in ["ru", "uz"]: locale = "ru"
        request.state.locale = locale

    site_router = APIRouter(prefix="/{locale}", dependencies=[Depends(set_locale)])
    site_router.include_router(shop_root_router)
    site_router.include_router(shop_router, prefix="/shop")
    app.include_router(site_router)

    @app.get("/", include_in_schema=False)
    async def root_redirect(request: Request):
        return RedirectResponse(url="/ru")

    app.mount("/static", StaticFiles(directory=BASE_DIR / "src" / "static"), name="static")
    app.mount("/media", StaticFiles(directory=BASE_DIR / "media"), name="media")
    
    @app.get("/robots.txt", include_in_schema=False)
    async def robots_txt(): return FileResponse(BASE_DIR / "src/static/robots.txt")

    @app.get("/sitemap.xml", include_in_schema=False)
    async def get_sitemap(): return FileResponse(BASE_DIR / "src/static/sitemap.xml", media_type="application/xml")

    def _ensure_locale(request: Request):
        if not hasattr(request.state, "locale"):
            path_parts = request.url.path.split('/')
            request.state.locale = path_parts[1] if len(path_parts) > 1 and path_parts[1] in ['ru', 'uz'] else 'ru'

    @app.exception_handler(404)
    async def not_found_exception_handler(request: Request, exc: Exception):
        _ensure_locale(request)
        context = {"request": request, "error_code": "404", "error_message": "Страница не найдена."}
        return templates.TemplateResponse("shop/error.html", context, status_code=404)
    
    @app.exception_handler(Exception)
    async def generic_site_exception_handler(request: Request, exc: Exception):
        traceback.print_exc()
        _ensure_locale(request)
        context = {"request": request, "error_code": "500", "error_message": "Внутренняя ошибка сервера."}
        return templates.TemplateResponse("shop/error.html", context, status_code=500)

    return app

admin_app = create_admin_app()
site_app = create_site_app()

if __name__ == "__main__":
    uvicorn.run("main:admin_app", host="0.0.0.0", port=8000, reload=True)