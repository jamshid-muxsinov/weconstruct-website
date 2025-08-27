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

router = APIRouter()

@router.get("/", include_in_schema=False)
async def admin_root_redirect(request: Request):
    """
    Главная функция этого файла.
    Перенаправляет с корневого адреса админки (/admin/) на дашборд (/admin/dashboard).
    Это "домашняя страница" по умолчанию для CRM.
    """
    dashboard_url = request.url_for('admin_dashboard')
    return RedirectResponse(url=dashboard_url)

router.include_router(dashboard.router)
router.include_router(kanban.router)
router.include_router(crud.router)
router.include_router(contact.router)
router.include_router(profile.router)
router.include_router(importer.router)
router.include_router(htmx.router)
router.include_router(api.router)

unprotected_router = APIRouter()
unprotected_router.include_router(auth.router)