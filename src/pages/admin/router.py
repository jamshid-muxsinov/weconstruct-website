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
from . import users 
from src.core.security import get_current_superuser, get_current_staff_user

router = APIRouter()
unprotected_router = APIRouter()
htmx_router = htmx.router

# Роутер для страниц, доступных всем сотрудникам (менеджерам)
staff_crud_router = APIRouter(dependencies=[Depends(get_current_staff_user)])
staff_crud_router.include_router(crud.quoterequest_router, prefix="/quoterequest", tags=["CRUD QuoteRequest"])
staff_crud_router.include_router(contact.router, prefix="/contact", tags=["CRUD Contact"])

# Роутер для страниц, доступных только админам
admin_only_crud_router = APIRouter(dependencies=[Depends(get_current_superuser)])
# --- ИЗМЕНЕНИЕ: Возвращаем роутеры для продуктов и категорий ---
admin_only_crud_router.include_router(crud.product_router, prefix="/product", tags=["CRUD Product"])
admin_only_crud_router.include_router(crud.category_router, prefix="/category", tags=["CRUD Category"])
admin_only_crud_router.include_router(users.router, prefix="/users", tags=["CRUD Users"])
admin_only_crud_router.include_router(importer.router)


@router.get("/", include_in_schema=False, name="admin_root")
async def admin_root_redirect(request: Request):
    kanban_url = request.url_for('admin_kanban_board', locale='ru')
    return RedirectResponse(url=kanban_url)

router.include_router(dashboard.router)
router.include_router(kanban.router)
router.include_router(profile.router)

router.include_router(staff_crud_router)
router.include_router(admin_only_crud_router)

router.include_router(
    invites.router,
    dependencies=[Depends(get_current_superuser)]
)

unprotected_router.include_router(auth.router)