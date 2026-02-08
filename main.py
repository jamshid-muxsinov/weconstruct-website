# src/main.py

import logging
import sys
import traceback
import os 
from typing import Callable
import asyncio
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.exceptions import StarletteHTTPException  
import uvicorn
from fastapi import FastAPI, Request, Depends, APIRouter, Path
from fastapi.responses import RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from pathlib import Path as FilePath
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response
from starlette_wtf import CSRFProtectMiddleware
 
from src.core.middleware import HTMXMiddleware
from src.pages.admin.router import router as admin_router, unprotected_router as admin_unprotected_router
from src.pages.admin.api import router as api_router
from src.core.config import get_settings
from src.core.db import check_db_connection, async_session_factory, get_db_session 
from src.core.security import get_current_active_user
from src.pages.shop_pages import router as shop_router, root_router as shop_root_router
from src.services.user_service import create_first_superuser
from src.core.cache import init_cache, cleanup_cache
from src.core.middleware import CacheMiddleware, RateLimitMiddleware
from src.core.cache_utils import schedule_cache_cleanup, warm_up_cache
from src.pages.jinja_config import templates, configure_jinja_templates


logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)
settings = get_settings()

configure_jinja_templates(templates)

BASE_DIR = FilePath("/app")

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
    
    if os.getenv("APP_TO_RUN") == "admin":
        asyncio.create_task(warm_up_cache())
        asyncio.create_task(schedule_cache_cleanup())
        log.info("Cache warm-up and cleanup scheduler started in background.")

async def on_shutdown():
    log.info("Application shutdown...")
    await cleanup_cache()
    log.info("Cache cleanup complete.")

def create_admin_app() -> FastAPI:
    fastapi_kwargs = {"title": "WeConstruct CRM"}
    if not settings.DEBUG:
        fastapi_kwargs.update({"docs_url": None, "redoc_url": None, "openapi_url": None})

    app = FastAPI(**fastapi_kwargs, on_startup=[on_startup], on_shutdown=[on_shutdown])
    
    from src.pages.admin.webhooks import router as webhooks_router

    app.add_middleware(HTMXMiddleware, templates=templates)
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
    app.add_middleware(CSRFProtectMiddleware, csrf_secret=settings.SECRET_KEY)
    app.add_middleware(RateLimitMiddleware, max_requests=200, window_seconds=60)

    app.mount("/static", StaticFiles(directory=BASE_DIR / "src" / "static"), name="static")
    app.mount("/media", StaticFiles(directory=BASE_DIR / "media"), name="media")

    async def set_locale_admin(request: Request, locale: str = Path(..., description="Код языка (ru или uz)")):
        if locale not in ["ru", "uz"]:
            locale = "uz" 
        request.state.locale = locale

    locale_router = APIRouter(prefix="/{locale}", dependencies=[Depends(set_locale_admin)])

    protected_admin_router = APIRouter(dependencies=[Depends(get_current_active_user)])
    protected_admin_router.include_router(admin_router)

    locale_router.include_router(protected_admin_router)
    
    app.include_router(admin_unprotected_router) 
    app.include_router(webhooks_router) 
    app.include_router(api_router, dependencies=[Depends(get_current_active_user)])
    app.include_router(locale_router) 
    
    @app.get("/", include_in_schema=False)
    async def admin_root_redirect(request: Request):
        return RedirectResponse(url=request.url_for('admin_kanban_board', locale='uz'))
        
    add_pagination(app)

    # --- ОБРАБОТЧИКИ ОШИБОК ---

    @app.exception_handler(401)
    async def unauthorized_exception_handler(request: Request, exc: Exception):
        if not hasattr(request.state, "locale"): request.state.locale = "uz"
        try:
            login_url = request.url_for('admin_login')
            next_path = request.url.path if request.url.path != '/' else request.url_for('admin_kanban_board', locale='uz')
            return RedirectResponse(url=f"{login_url}?next={next_path}", status_code=302)
        except:
            return RedirectResponse(url="/admin/login", status_code=302)

    @app.exception_handler(404)
    async def not_found_error(request: Request, exc: Exception):
        if not hasattr(request.state, "locale"): request.state.locale = "uz"
        return templates.TemplateResponse("admin/error.html", {
            "request": request,
            "status_code": 404,
            "title": "Страница не найдена",
            "message": "Мы не смогли найти то, что вы искали."
        }, status_code=404)

    @app.exception_handler(500)
    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        traceback.print_exc()
        if not hasattr(request.state, "locale"): request.state.locale = "ru"
        return templates.TemplateResponse("admin/error.html", {
            "request": request,
            "status_code": 500,
            "title": "Ошибка сервера",
            "message": "Произошла внутренняя ошибка. Мы уже работаем над этим."
        }, status_code=500)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if not hasattr(request.state, "locale"): request.state.locale = "ru"
        return templates.TemplateResponse("admin/error.html", {
            "request": request,
            "status_code": exc.status_code,
            "title": "Ошибка",
            "message": str(exc.detail)
        }, status_code=exc.status_code)

    return app


def create_site_app() -> FastAPI:
    fastapi_kwargs = {"title": "WeConstruct Website"}
    if not settings.DEBUG:
        fastapi_kwargs.update({"docs_url": None, "redoc_url": None, "openapi_url": None})
    app = FastAPI(**fastapi_kwargs, root_path=settings.ROOT_PATH, on_startup=[on_startup], on_shutdown=[on_shutdown]) # --- ИЗМЕНЕНО: добавлены on_startup/on_shutdown
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
        return RedirectResponse(url="/uz")
    app.mount("/static", StaticFiles(directory=BASE_DIR / "src" / "static"), name="static")
    app.mount("/media", StaticFiles(directory=BASE_DIR / "media"), name="media")
    @app.get("/robots.txt", include_in_schema=False)
    async def robots_txt(): return FileResponse(BASE_DIR / "src/static/robots.txt")

    @app.get("/sitemap.xml", include_in_schema=False)
    async def get_sitemap(request: Request, db: AsyncSession = Depends(get_db_session)):
        base_url = "https://www.weconstruct.uz"
        today = date.today().strftime("%Y-%m-%d")
        
        static_pages = {
            "": 1.0,      
            "/about": 0.8  
        }

        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'

        for path, priority in static_pages.items():
            xml_content += f"""
    <url>
        <loc>{base_url}/ru{path}</loc>
        <xhtml:link rel="alternate" hreflang="ru" href="{base_url}/ru{path}"/>
        <xhtml:link rel="alternate" hreflang="uz" href="{base_url}/uz{path}"/>
        <xhtml:link rel="alternate" hreflang="x-default" href="{base_url}/ru{path}"/>
        <lastmod>{today}</lastmod>
        <priority>{priority}</priority>
    </url>
"""

        xml_content += '</urlset>'
        
        return Response(content=xml_content, media_type="application/xml")

    def _ensure_locale(request: Request):
        if not hasattr(request.state, "locale"):
            path_parts = request.url.path.split('/')
            request.state.locale = path_parts[1] if len(path_parts) > 1 and path_parts[1] in ['ru', 'uz'] else 'uz'
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

app: FastAPI
app_to_run = os.getenv("APP_TO_RUN")

if app_to_run == "site":
    log.info("Creating SITE application instance.")
    app = create_site_app()
elif app_to_run == "admin":
    log.info("Creating ADMIN application instance.")
    app = create_admin_app()
else:
    log.info("APP_TO_RUN not set, creating ADMIN application by default.")
    app = create_admin_app()