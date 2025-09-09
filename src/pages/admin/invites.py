# src/pages/admin/invites.py

import wtforms
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.pages.admin.crud import set_hx_trigger_header 
from src.core.db import get_db_session
from src.models.shop_models import RegistrationInvite
from src.services import user_service
from .dependencies import get_common_context
from src.pages.jinja_config import templates

router = APIRouter()

class InviteForm(wtforms.Form):
    note = wtforms.StringField('Заметка (для кого это приглашение)', validators=[wtforms.validators.DataRequired()])

@router.get("/invites/", response_class=HTMLResponse, name="admin_invites")
async def invites_page_get(request: Request, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    invites = (await db.execute(select(RegistrationInvite).order_by(RegistrationInvite.created_at.desc()))).scalars().all()
    form = InviteForm()
    context.update({"title": "Управление приглашениями", "invites": invites, "form": form, "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/invites.html", context)

@router.post("/invites/", response_class=HTMLResponse)
async def invites_page_post(request: Request, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    form_data = await request.form()
    form = InviteForm(form_data)
    if form.validate():
        await user_service.create_invite(db, form.note.data, context["user"].id)
        response = RedirectResponse(request.url_for("admin_invites", locale=request.state.locale), status_code=303)
        return set_hx_trigger_header(response, "invite_created_success", request)
    invites = (await db.execute(select(RegistrationInvite).order_by(RegistrationInvite.created_at.desc()))).scalars().all()
    context.update({"title": "Управление приглашениями", "invites": invites, "form": form, "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/invites.html", context)