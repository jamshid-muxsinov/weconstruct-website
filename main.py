import traceback
from starlette.responses import Response, FileResponse
from src.pages.jinja_config import templates 
import uvicorn
from fastapi import FastAPI, Request, Depends, APIRouter, Path 
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from pathlib import Path as FilePath 
from starlette.middleware.sessions import SessionMiddleware
from starlette_wtf import CSRFProtectMiddleware
from src.core.config import get_settings
from src.core.db import check_db_connection
from src.core.security import get_current_active_user
from src.pages.admin.router import router as admin_router, unprotected_router
from src.pages.shop_pages import router as shop_router, root_router as shop_root_router
from src.core.db import check_db_connection, async_session_factory 
from src.services.user_service import create_first_superuser
from src.core.cache import init_cache, cleanup_cache
from src.core.middleware import CacheMiddleware, RateLimitMiddleware
from src.core.cache_utils import schedule_cache_cleanup, warm_up_cache

app = FastAPI(
    title="WeConstruct CRM & Website",
    description="Backend for WeConstruct CRM and public website",
    version="1.0.0"
)

settings = get_settings()
BASE_DIR = FilePath(__file__).resolve().parent

async def set_locale(request: Request, locale: str = Path(..., description="Код языка (ru или uz)")):
    if locale not in ["ru", "uz"]:
        locale = "ru" 
    request.state.locale = locale

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.add_middleware(CSRFProtectMiddleware, csrf_secret=settings.SECRET_KEY)

if settings.CACHE_ENABLED:
    app.add_middleware(CacheMiddleware, cache_ttl=settings.REDIS_TTL)
app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)

@app.on_event("startup")
async def on_startup():
    print("Application startup...")
    await check_db_connection()
    print("Creating first superuser if necessary...")
    async with async_session_factory() as session:
        await create_first_superuser(session)
    print("Superuser check complete.")
    print("Initializing cache...")
    await init_cache()
    print("Cache initialization complete.")
    await warm_up_cache()
    import asyncio
    asyncio.create_task(schedule_cache_cleanup())
    print("Cache cleanup scheduler started.")

@app.on_event("shutdown")
async def on_shutdown():
    print("Application shutdown...")
    await cleanup_cache()
    print("Cache cleanup complete.")

app.mount("/static", StaticFiles(directory=BASE_DIR / "src" / "static"), name="static")
app.mount("/media", StaticFiles(directory=BASE_DIR / "media"), name="media")

add_pagination(app)

app.include_router(unprotected_router)
app.include_router(admin_router, dependencies=[Depends(get_current_active_user)])

site_router = APIRouter(prefix="/{locale}", dependencies=[Depends(set_locale)])
site_router.include_router(shop_root_router)
site_router.include_router(shop_router, prefix="/shop")
app.include_router(site_router)

@app.get("/", include_in_schema=False)
async def root_redirect(request: Request):
    return RedirectResponse(url="/ru")

@app.get("/robots.txt", include_in_schema=False, name="robots_txt")
@app.get("/robots.txt/", include_in_schema=False)
async def robots_txt():
    # ИЗМЕНЕНИЕ: Используем BASE_DIR для правильного пути внутри контейнера
    return FileResponse(BASE_DIR / "src/static/robots.txt")

@app.exception_handler(401)
async def unauthorized_exception_handler(request: Request, exc: Exception):
    if "text/html" in request.headers.get("accept", ""):
        login_url = request.url_for('admin_login')
        return RedirectResponse(url=f"{login_url}?next={request.url.path}", status_code=302)
    return JSONResponse(
        status_code=401,
        content={"detail": "Not authenticated"},
        headers={"WWW-Authenticate": "Bearer"},
    )

def _ensure_locale(request: Request):
    if not hasattr(request.state, "locale"):
        path_parts = request.url.path.split('/')
        if len(path_parts) > 1 and path_parts[1] in ['ru', 'uz']:
            request.state.locale = path_parts[1]
        else:
            request.state.locale = 'ru'

@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: Exception) -> Response:
    is_main_site = request.url.path.startswith(("/ru", "/uz")) or request.url.path == "/"
    
    if is_main_site and "text/html" in request.headers.get("accept", ""):
        _ensure_locale(request)
        context = {
            "request": request,
            "error_title": "Страница не найдена",
            "error_code": "404",
            "error_message": "Запрашиваемая страница не существует. Возможно, она была удалена или перемещена."
        }
        return templates.TemplateResponse("shop/error.html", context, status_code=404)
    else:
        # Check if the route exists before trying to access its name
        if hasattr(request.scope.get('route'), 'name') and request.scope['route'].name == 'robots_txt':
            return Response(status_code=404, content="Not found")
        return JSONResponse(status_code=404, content={"detail": "Not found"})

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> Response:
    print("="*100)
    print(f"Unhandled exception for path: {request.url.path}")
    traceback.print_exc()
    print("="*100)
    
    is_main_site = request.url.path.startswith(("/ru", "/uz")) or request.url.path == "/"
    
    if is_main_site and "text/html" in request.headers.get("accept", ""):
        _ensure_locale(request)
        context = {
            "request": request,
            "error_title": "Внутренняя ошибка сервера",
            "error_code": "500",
            "error_message": "Произошла непредвиденная ошибка. Мы уже работаем над ее устранением.",
            "error_details": str(exc) if settings.DEBUG else None
        }
        return templates.TemplateResponse("shop/error.html", context, status_code=500)
    elif "application/json" in request.headers.get("accept", ""):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(exc) if settings.DEBUG else None}
        )
    else:
        context = {"request": request, "error_message": "Произошла внутренняя ошибка сервера."}
        return templates.TemplateResponse("admin/500.html", context, status_code=500)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)