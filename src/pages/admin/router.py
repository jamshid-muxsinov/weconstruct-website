# src/pages/admin/router.py

from fastapi import APIRouter, Request, Depends
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
from . import invites
from src.core.security import get_current_superuser
router = APIRouter()
unprotected_router = APIRouter()


@router.get("/", include_in_schema=False, name="admin_root")
async def admin_root_redirect(request: Request):
    """
    Перенаправляет с / на /dashboard.
    """
    dashboard_url = request.url_for('admin_dashboard', locale='ru')
    return RedirectResponse(url=dashboard_url)

router.include_router(dashboard.router)
router.include_router(kanban.router)
router.include_router(
    crud.router, 
    dependencies=[Depends(get_current_superuser)]
)
router.include_router(contact.router)
router.include_router(profile.router)
router.include_router(
    importer.router,
    dependencies=[Depends(get_current_superuser)]
)
router.include_router(htmx.router)
router.include_router(api.router)
router.include_router(
    invites.router,
    dependencies=[Depends(get_current_superuser)]
)

unprotected_router.include_router(auth.router)