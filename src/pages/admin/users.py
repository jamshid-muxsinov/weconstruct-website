# src/pages/admin/users.py

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
import wtforms
from wtforms import validators

from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.models.shop_models import User, UserRole
from src.services import user_service
from .dependencies import get_common_context
from .crud import set_hx_trigger_header, Meta

router = APIRouter()

# --- ФОРМЫ ---

# 1. Форма СОЗДАНИЯ (с паролем)
class UserCreateForm(wtforms.Form):
    username = wtforms.StringField('Логин (обязательно) *', validators=[validators.DataRequired(), validators.Length(min=4)])
    password = wtforms.PasswordField('Пароль *', validators=[validators.DataRequired(), validators.Length(min=6)])
    
    first_name = wtforms.StringField('Имя')
    last_name = wtforms.StringField('Фамилия')
    
    role = wtforms.SelectField('Должность', choices=[
        ('manager', 'Менеджер'),
        ('admin', 'Администратор')
    ], default='manager')
    
    # Настройки доступа
    is_active = wtforms.BooleanField('Активен', default=True, description="Разрешить вход в систему")
    is_staff = wtforms.BooleanField('Доступ в CRM', default=True, description="Видит заявки и канбан")
    is_superuser = wtforms.BooleanField('Суперпользователь', default=False, description="Полный доступ (удаление, настройки)")

# 2. Форма РЕДАКТИРОВАНИЯ (без пароля, логин нельзя менять)
class UserEditForm(wtforms.Form):
    username = wtforms.StringField('Логин', render_kw={'readonly': True})
    
    first_name = wtforms.StringField('Имя')
    last_name = wtforms.StringField('Фамилия')
    
    role = wtforms.SelectField('Должность', choices=[
        ('manager', 'Менеджер'),
        ('admin', 'Администратор')
    ])
    
    is_active = wtforms.BooleanField('Активен', description="Разрешить вход в систему")
    is_staff = wtforms.BooleanField('Доступ в CRM', description="Видит заявки и канбан")
    is_superuser = wtforms.BooleanField('Суперпользователь', description="Полный доступ")

User.__str__ = lambda self: self.username

# --- НАСТРОЙКИ СПИСКА ---
USER_META = Meta(User, ['username', 'role', 'is_staff', 'is_active'], UserEditForm, "Сотрудник", "Сотрудники")
USER_META.add_url_name = "admin_user_add"      # Включаем кнопку "Добавить"
USER_META.delete_url_name = "admin_user_delete" # Включаем кнопку "Удалить"

# --- СПИСОК ПОЛЬЗОВАТЕЛЕЙ ---
@router.get("/users/", response_class=HTMLResponse, name="admin_user_list")
async def user_list(
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    
    # Имитация пагинации (показываем всех одной страницей)
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
    
    # Поддержка HTMX обновлений
    is_htmx = "HX-Request" in request.headers
    template_name = "admin/partials/_generic_list_content.html" if is_htmx else "admin/generic_list.html"
    return templates.TemplateResponse(template_name, context)


# --- ДОБАВЛЕНИЕ (РУЧНОЕ) ---
@router.get("/users/add/", response_class=HTMLResponse, name="admin_user_add")
async def user_add_get(
    request: Request,
    context: dict = Depends(get_common_context)
):
    form = UserCreateForm()
    
    context.update({
        "meta": USER_META,
        "original": None,
        "form": form,
        "title": "Новый сотрудник"
    })
    return templates.TemplateResponse("admin/generic_form.html", context)

@router.post("/users/add/", response_class=HTMLResponse)
async def user_add_post(
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    form_data = await request.form()
    form = UserCreateForm(form_data)
    
    if form.validate():
        # Проверяем, не занят ли логин
        existing = await user_service.get_user_by_username(db, form.username.data)
        if existing:
            form.username.errors.append("Этот логин уже занят")
        else:
            # Создаем пользователя через сервис
            await user_service.create_user_direct(
                db, 
                username=form.username.data, 
                password=form.password.data,
                role=form.role.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                is_staff=form.is_staff.data,
                is_superuser=form.is_superuser.data
            )
            
            response = RedirectResponse(request.url_for("admin_user_list", locale=request.state.locale), status_code=303)
            return set_hx_trigger_header(response, "Сотрудник успешно создан!", request)

    context.update({
        "meta": USER_META,
        "original": None,
        "form": form,
        "title": "Новый сотрудник"
    })
    return templates.TemplateResponse("admin/generic_form.html", context, status_code=422)


# --- РЕДАКТИРОВАНИЕ ---
@router.get("/users/{pk}/change/", response_class=HTMLResponse, name="admin_user_change")
async def user_change_get(
    pk: int,
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    user = await db.get(User, pk)
    if not user: raise HTTPException(404)
    
    form = UserEditForm(obj=user)
    # Предзаполняем поле роли
    if hasattr(user.role, 'value'):
        form.role.data = user.role.value
        
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
    if not user: raise HTTPException(404)

    form_data = await request.form()
    form = UserEditForm(form_data, obj=user)

    if form.validate():
        form.populate_obj(user)
        # Если нужно, можно добавить явное обновление роли:
        # user.role = UserRole(form.role.data)
        
        db.add(user)
        await db.commit()
        
        response = RedirectResponse(request.url_for("admin_user_change", locale=request.state.locale, pk=user.id), status_code=303)
        return set_hx_trigger_header(response, "Данные сохранены", request)

    context.update({
        "meta": USER_META,
        "original": user,
        "form": form,
        "title": f"Редактирование: {user.username}"
    })
    return templates.TemplateResponse("admin/generic_form.html", context, status_code=422)


# --- УДАЛЕНИЕ ---
@router.get("/users/{pk}/delete/", response_class=HTMLResponse, name="admin_user_delete")
@router.post("/users/{pk}/delete/", response_class=HTMLResponse)
async def user_delete(
    pk: int,
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    user_to_delete = await db.get(User, pk)
    if not user_to_delete: raise HTTPException(404)

    # Нельзя удалить самого себя
    if context["user"].id == user_to_delete.id:
        context["error_message"] = "Вы не можете удалить свой собственный профиль."
        return templates.TemplateResponse("admin/500.html", context, status_code=400)

    if request.method == "POST":
        try:
            await db.delete(user_to_delete)
            await db.commit()
            response = RedirectResponse(request.url_for("admin_user_list", locale=request.state.locale), status_code=303)
            return set_hx_trigger_header(response, f"Пользователь удален", request, type="warning")
        except IntegrityError:
            await db.rollback()
            context["error_message"] = "Нельзя удалить пользователя, у которого есть задачи или заявки."
            return templates.TemplateResponse("admin/500.html", context, status_code=400)

    _ = templates.env.globals['_']
    title = _({'request': request}, 'delete_confirmation_title', entity=f"пользователя {user_to_delete.username}")
    
    context.update({
        "meta": USER_META,
        "original": user_to_delete,
        "title": title,
        "back_url": request.url_for("admin_user_list", locale=request.state.locale)
    })
    return templates.TemplateResponse("admin/delete_confirmation.html", context)