# src/pages/admin/users.py

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import wtforms

from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.models.shop_models import User, UserRole
from .dependencies import get_common_context
from .crud import set_hx_trigger_header, Meta

router = APIRouter()

class UserForm(wtforms.Form):
    username = wtforms.StringField('Имя пользователя', render_kw={'readonly': True})
    first_name = wtforms.StringField('Имя')
    last_name = wtforms.StringField('Фамилия')
    role = wtforms.SelectField('Роль', choices=[(role.value, role.name.capitalize()) for role in UserRole])
    is_active = wtforms.BooleanField('Активен', default=True)
    is_staff = wtforms.BooleanField('Сотрудник (Доступ в CRM)')
    is_superuser = wtforms.BooleanField('Суперпользователь (Администратор)')

User.__str__ = lambda self: self.username
USER_META = Meta(User, ['username', 'role', 'is_staff', 'is_active'], UserForm, "Пользователь", "Пользователи")

@router.get("/users/", response_class=HTMLResponse, name="admin_user_list")
async def user_list(
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    context.update({
        "meta": USER_META,
        "page": {"items": users}, # Упрощенная пагинация для пользователей
        "list_display": USER_META.list_display,
        "htmx_request": "HX-Request" in request.headers
    })
    return templates.TemplateResponse("admin/generic_list.html", context)


@router.get("/users/{pk}/change/", response_class=HTMLResponse, name="admin_user_change")
async def user_change_get(
    pk: int,
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    user = await db.get(User, pk)
    if not user:
        raise HTTPException(404)
    
    form = UserForm(obj=user)
    context.update({
        "meta": USER_META,
        "original": user,
        "form": form,
        "title": f"Редактирование: {user.username}"
    })
    return templates.TemplateResponse("admin/generic_form.html", context)


@router.post("/users/{pk}/change/", response_class=HTMLResponse)
async def user_change_post(
    pk: int,
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    user = await db.get(User, pk)
    if not user:
        raise HTTPException(404)

    form_data = await request.form()
    form = UserForm(form_data, obj=user)

    if form.validate():
        form.populate_obj(user)
        db.add(user)
        await db.commit()
        
        redirect_url = request.url_for(USER_META.change_url_name, locale=request.state.locale, pk=user.id)
        response = RedirectResponse(redirect_url, status_code=303)
        return set_hx_trigger_header(response, "Данные пользователя сохранены!", request)

    context.update({
        "meta": USER_META,
        "original": user,
        "form": form,
        "title": f"Редактирование: {user.username}"
    })
    return templates.TemplateResponse("admin/generic_form.html", context, status_code=422)