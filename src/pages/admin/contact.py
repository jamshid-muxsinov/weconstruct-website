import json
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import wtforms

from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.services import crm_service
from .dependencies import get_common_context

router = APIRouter()

class ContactForm(wtforms.Form):
    name = wtforms.StringField('Имя', validators=[wtforms.validators.DataRequired()])
    last_name = wtforms.StringField('Фамилия')
    phone = wtforms.StringField('Телефон')

def set_hx_trigger_header(response: RedirectResponse, message: str, type: str = "success"):
    payload = json.dumps({"show-toast": {"message": message, "type": type}})
    response.headers["HX-Trigger"] = quote(payload)
    return response

@router.get("/contact/{pk}/", response_class=HTMLResponse, name="admin_contact_detail")
async def get_contact_detail_page(
    pk: int,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    contact_data = await crm_service.get_contact_360_view(db, pk)
    if not contact_data:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    form = ContactForm(obj=contact_data["contact"])
    
    context.update({
        "title": f"Клиент: {contact_data['contact'].full_name}",
        "contact": contact_data["contact"],
        "timeline": contact_data["timeline"],
        "form": form
    })
    
    return templates.TemplateResponse("admin/contact_detail.html", context)

@router.post("/contact/{pk}/", response_class=HTMLResponse)
async def post_contact_detail_page(
    pk: int,
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    form_data = await request.form()
    form = ContactForm(form_data)

    if form.validate():
        updated_contact = await crm_service.update_contact(db, pk, form)
        if not updated_contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        redirect_url = request.url_for("admin_contact_detail", pk=pk)
        response = RedirectResponse(redirect_url, status_code=303)
        return set_hx_trigger_header(response, "Данные клиента успешно обновлены!")
    
    contact_data = await crm_service.get_contact_360_view(db, pk)
    context.update({
        "title": f"Клиент: {contact_data['contact'].full_name}",
        "contact": contact_data["contact"],
        "timeline": contact_data["timeline"],
        "form": form
    })
    return templates.TemplateResponse("admin/contact_detail.html", context, status_code=422)

@router.post("/contact/{pk}/add-note", response_class=HTMLResponse, name="admin_contact_add_note")
async def htmx_add_note(
    pk: int,
    request: Request,
    note: str = Form(...),
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session),
):
    if not note.strip():
        return HTMLResponse("", status_code=204)

    await crm_service.add_note_to_contact(db, pk, context["user"].id, note)
    
    contact_data = await crm_service.get_contact_360_view(db, pk)
    context.update({"timeline": contact_data["timeline"]})

    response = templates.TemplateResponse("admin/partials/_contact_timeline.html", context)
    trigger_payload = json.dumps({
        "show-toast": {"message": "Заметка добавлена"},
        "updateKanban": True
    })
    response.headers["HX-Trigger"] = quote(trigger_payload)
    return response

@router.post("/contact/{pk}/note/{note_id}/pin", response_class=HTMLResponse, name="admin_contact_pin_note")
async def htmx_pin_note(
    pk: int,
    note_id: int,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session),
):
    await crm_service.toggle_pin_contact_note(db, note_id, pk)
    
    contact_data = await crm_service.get_contact_360_view(db, pk)
    context.update({"timeline": contact_data["timeline"]})
    
    response = templates.TemplateResponse("admin/partials/_contact_timeline.html", context)
    
    trigger_payload = json.dumps({
        "show-toast": {"message": "Статус заметки изменен"},
        "updateKanban": True
    })
    response.headers["HX-Trigger"] = quote(trigger_payload)
    return response