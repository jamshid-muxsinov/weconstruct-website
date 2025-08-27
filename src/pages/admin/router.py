from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from . import auth, kanban, dashboard, crud, htmx, api, profile, contact, importer

router = APIRouter(prefix="/admin", tags=["Admin Pages"])
unprotected_router = APIRouter(prefix="/admin", tags=["Admin Auth"])

@router.get("/", name="admin_index", include_in_schema=False)
async def admin_root():
    return RedirectResponse(url="/admin/kanban")

unprotected_router.include_router(auth.router) 
router.include_router(kanban.router)
router.include_router(dashboard.router)
router.include_router(crud.router)
router.include_router(htmx.router)
router.include_router(api.router)
router.include_router(profile.router)
router.include_router(contact.router)
router.include_router(importer.router)