import logging 
import sys  
import traceback
from starlette.responses import Response, FileResponse
from src.pages.jinja_config import templates 
import uvicorn
from fastapi import FastAPI, Request, Depends, APIRouter
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from pathlib import Path as FilePath 
from starlette.middleware.sessions import SessionMiddleware
from starlette_wtf import CSRFProtectMiddleware
from src.core.config import get_settings
from src.core.db import check_db_connection
from src.core.security import get_current_active_user
from src.pages.admin.router import admin_router_no_prefix, unprotected_admin_router_no_prefix
from src.core.db import check_db_connection, async_session_factory 
from src.services.user_service import create_first_superuser
from src.core.cache import init_cache, cleanup_cache
from src.core.middleware import CacheMiddleware, RateLimitMiddleware
from src.core.cache_utils import schedule_cache_cleanup, warm_up_cache

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)
settings = get_settings()
BASE_DIR = FilePath(__file__).resolve().parent

fastapi_kwargs = {
    "title": "WeConstruct Admin Panel",
    "description": "Admin panel for WeConstruct CRM",
    "version": "1.0.0"
}

if not settings.DEBUG:
    fastapi_kwargs["docs_url"] = None
    fastapi_kwargs["redoc_url"] = None
    fastapi_kwargs["openapi_url"] = None

admin_app = FastAPI(**fastapi_kwargs, root_path=settings.ROOT_PATH)

admin_app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
admin_app.add_middleware(CSRFProtectMiddleware, csrf_secret=settings.SECRET_KEY)

if settings.CACHE_ENABLED:
    admin_app.add_middleware(CacheMiddleware, cache_ttl=settings.REDIS_TTL)
admin_app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)

@admin_app.on_event("startup")
async def on_startup():
    log.info("Admin application startup...")
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

@admin_app.on_event("shutdown")
async def on_shutdown():
    log.info("Admin application shutdown...") 
    await cleanup_cache()
    log.info("Cache cleanup complete.")

admin_app.mount("/static", StaticFiles(directory=BASE_DIR / "src" / "static"), name="static")
admin_app.mount("/media", StaticFiles(directory=BASE_DIR / "media"), name="media")

add_pagination(admin_app)

# Include admin routers without /admin prefix
admin_app.include_router(unprotected_admin_router_no_prefix)
admin_app.include_router(admin_router_no_prefix, dependencies=[Depends(get_current_active_user)]) 

@admin_app.get("/", include_in_schema=False, name="admin_root")
async def admin_root_redirect(request: Request):
    """
    Redirect from / to /dashboard for admin panel.
    """
    dashboard_url = request.url_for('admin_dashboard')
    return RedirectResponse(url=dashboard_url)

@admin_app.exception_handler(401)
async def unauthorized_exception_handler(request: Request, exc: Exception):
    if "text/html" in request.headers.get("accept", ""):
        login_url = request.url_for('admin_login')
        return RedirectResponse(url=f"{login_url}?next={request.url.path}", status_code=302)
    return JSONResponse(
        status_code=401,
        content={"detail": "Not authenticated"},
        headers={"WWW-Authenticate": "Bearer"},
    )

@admin_app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: Exception) -> Response:
    if "text/html" in request.headers.get("accept", ""):
        context = {
            "request": request,
            "error_title": "Page not found",
            "error_code": "404",
            "error_message": "The requested page does not exist."
        }
        return templates.TemplateResponse("admin/404.html", context, status_code=404)
    else:
        return JSONResponse(status_code=404, content={"detail": "Not found"})

@admin_app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> Response:
    print("="*100)
    print(f"Unhandled exception for admin path: {request.url.path}")
    traceback.print_exc()
    print("="*100)
    
    if "text/html" in request.headers.get("accept", ""):
        context = {
            "request": request, 
            "error_message": "An internal server error occurred.",
            "error_details": str(exc) if settings.DEBUG else None
        }
        return templates.TemplateResponse("admin/500.html", context, status_code=500)
    elif "application/json" in request.headers.get("accept", ""):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(exc) if settings.DEBUG else None}
        )
    else:
        context = {"request": request, "error_message": "An internal server error occurred."}
        return templates.TemplateResponse("admin/500.html", context, status_code=500)

if __name__ == "__main__":
    uvicorn.run("admin_app:admin_app", host="0.0.0.0", port=8001, reload=True)