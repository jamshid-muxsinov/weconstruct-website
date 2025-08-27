# src/pages/admin/router.py

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from . import auth
from . import dashboard
from . import kanban
from . import crud
from . import contact
from . import profile
from . import htmx
from . import api
from . import importer

# Original routers with /admin prefix (for legacy main app)
router = APIRouter(prefix="/admin")
unprotected_router = APIRouter(prefix="/admin")

# New routers without prefix (for admin subdomain app)
admin_router_no_prefix = APIRouter()
unprotected_admin_router_no_prefix = APIRouter()


@router.get("/", include_in_schema=False, name="admin_root")
async def admin_root_redirect(request: Request):
    """
    Перенаправляет с /admin/ на /admin/dashboard.
    """
    dashboard_url = request.url_for('admin_dashboard')
    return RedirectResponse(url=dashboard_url)

# Подключаем все модули админки к главному роутеру (с префиксом /admin)
router.include_router(dashboard.router)
router.include_router(kanban.router)
router.include_router(crud.router)
router.include_router(contact.router)
router.include_router(profile.router)
router.include_router(importer.router)
router.include_router(htmx.router)
router.include_router(api.router)

# Роутер аутентификации подключаем к unprotected_router
unprotected_router.include_router(auth.router)

# Подключаем все модули админки к роутеру без префикса (для admin.weconstruct.uz)
admin_router_no_prefix.include_router(dashboard.router)
admin_router_no_prefix.include_router(kanban.router)
admin_router_no_prefix.include_router(crud.router)
admin_router_no_prefix.include_router(contact.router)
admin_router_no_prefix.include_router(profile.router)
admin_router_no_prefix.include_router(importer.router)
admin_router_no_prefix.include_router(htmx.router)
admin_router_no_prefix.include_router(api.router)

# Роутер аутентификации для subdomain app
unprotected_admin_router_no_prefix.include_router(auth.router)