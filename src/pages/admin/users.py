# src/pages/admin/users.py

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
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
USER_META.add_url_name = None
USER_META.delete_url_name = None 

@router.get("/users/", response_class=HTMLResponse, name="admin_user_list")
async def user_list(
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    
    class PageMock:
        def __init__(self, items):
            self.items = items
            self.page = 1
            self.pages = 1
            self.total = len(items)
            self.size = len(items)

    context.update({
        "meta": USER_META,
        "page": PageMock(users),
        "list_display": USER_META.list_display,
    })
    
    is_htmx = "HX-Request" in request.headers
    template_name = "admin/partials/_generic_list_content.html" if is_htmx else "admin/generic_list.html"
    return templates.TemplateResponse(template_name, context)



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


@router.get("/users/{pk}/delete/", response_class=HTMLResponse, name="admin_user_delete")
@router.post("/users/{pk}/delete/", response_class=HTMLResponse)
async def user_delete(
    pk: int,
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    user_to_delete = await db.get(User, pk)
    if not user_to_delete:
        raise HTTPException(404)

    if context["user"].id == user_to_delete.id:
        context["error_message"] = "Вы не можете удалить свой собственный профиль."
        return templates.TemplateResponse("admin/500.html", context, status_code=400)

    if request.method == "POST":
        try:
            await db.delete(user_to_delete)
            await db.commit()
            redirect_url = request.url_for(USER_META.list_url_name, locale=request.state.locale)
            response = RedirectResponse(redirect_url, status_code=303)
            return set_hx_trigger_header(response, f"Пользователь '{user_to_delete.username}' удален.", request, type="error")
        except IntegrityError:
            await db.rollback()
            context["error_message"] = "Нельзя удалить пользователя, к которому привязаны заявки, задачи или другие объекты."
            return templates.TemplateResponse("admin/500.html", context, status_code=400)

    _ = templates.env.globals['_']
    title = _({'request': request}, 'delete_confirmation_title', entity=f"пользователя '{user_to_delete.username}'")
    
    context.update({
        "meta": USER_META,
        "original": user_to_delete,
        "title": title,
        "back_url": request.url_for(USER_META.change_url_name, locale=request.state.locale, pk=pk)
    })
    return templates.TemplateResponse("admin/delete_confirmation.html", context)