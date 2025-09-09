import uuid
from datetime import timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import wtforms

from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.core.config import get_settings
from src.core.security import create_access_token
from src.services import user_service
from src.schemas.user_schemas import UserCreate

router = APIRouter()
settings = get_settings()

# --- ФОРМА РЕГИСТРАЦИИ ---
class RegistrationForm(wtforms.Form):
    username = wtforms.StringField('Имя пользователя', validators=[wtforms.validators.DataRequired(), wtforms.validators.Length(min=4, max=25)])
    password = wtforms.PasswordField('Пароль', validators=[wtforms.validators.DataRequired(), wtforms.validators.Length(min=8)])
    confirm_password = wtforms.PasswordField('Повторите пароль', validators=[
        wtforms.validators.DataRequired(),
        wtforms.validators.EqualTo('password', message='Пароли должны совпадать')
    ])

# --- РОУТЫ ЛОГИНА/ЛОГАУТА ---
@router.get("/login", response_class=HTMLResponse, name="admin_login")
async def login_page(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request})

@router.post("/login/token", name="admin_login_token")
async def login_for_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    form = await request.form()
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    if not username or not password:
        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "error": "Заполните имя пользователя и пароль"
        }, status_code=400)

    user = await user_service.authenticate_user(db, username, password)
    
    if not user or not user.is_staff:
        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "error": "Неверное имя пользователя или пароль."
        }, status_code=401)

    expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(data={"sub": user.username}, expires_delta=expires)
    
    redirect_url = request.url_for('admin_dashboard', locale='ru')
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    
    response.set_cookie(
        key="access_token", 
        value=token, 
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  
    )
    
    return response

@router.get("/logout", name="admin_logout")
async def logout_page(request: Request):
    response = RedirectResponse(url="/admin/login")
    response.delete_cookie("access_token")
    return response

# --- НОВЫЕ РОУТЫ РЕГИСТРАЦИИ ---

@router.get("/register", response_class=HTMLResponse, name="admin_register")
async def register_page_get(request: Request, invite: Optional[uuid.UUID] = Query(None), db: AsyncSession = Depends(get_db_session)):
    if not invite:
        return templates.TemplateResponse("admin/register_no_code.html", {"request": request})

    valid_invite = await user_service.get_valid_invite(db, invite)
    if not valid_invite:
        return templates.TemplateResponse("admin/register_invalid_code.html", {"request": request})

    form = RegistrationForm()
    context = {
        "request": request,
        "form": form,
        "invite_code": invite,
        "note": valid_invite.note
    }
    return templates.TemplateResponse("admin/register_form.html", context)

@router.post("/register", response_class=HTMLResponse)
async def register_page_post(request: Request, invite: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db_session)):
    valid_invite = await user_service.get_valid_invite(db, invite)
    if not valid_invite:
        return templates.TemplateResponse("admin/register_invalid_code.html", {"request": request})

    form_data = await request.form()
    form = RegistrationForm(form_data)
    
    existing_user = await user_service.get_user_by_username(db, form.username.data)
    if existing_user:
        form.username.errors.append("Пользователь с таким именем уже существует")

    if form.validate() and not existing_user:
        user_create = UserCreate(
            username=form.username.data,
            password=form.password.data
        )
        new_user = await user_service.create_user_from_invite(db, user_create, invite)
        if new_user:
            return RedirectResponse(url=request.url_for("admin_register_done"), status_code=303)
    
    context = {
        "request": request,
        "form": form,
        "invite_code": invite,
        "note": valid_invite.note
    }
    return templates.TemplateResponse("admin/register_form.html", context)

@router.get("/register/done", response_class=HTMLResponse, name="admin_register_done")
async def register_done_page(request: Request):
    return templates.TemplateResponse("admin/register_done.html", {"request": request})

@router.post("/test-form-receiver", include_in_schema=False)
async def test_form_receiver(request: Request):
    """
    Этот эндпоинт просто принимает любой POST-запрос,
    печатает его содержимое в лог и возвращает успешный ответ.
    """
    print("="*20 + " TEST FORM RECEIVED " + "="*20)
    print("HEADERS:")
    for name, value in request.headers.items():
        print(f"  {name}: {value}")
    
    body = await request.body()
    print("\nRAW BODY:")
    print(body.decode('utf-8', errors='ignore'))
    print("="*58)

    # Важно вернуть успешный ответ, чтобы не было ошибок в браузере
    return {"status": "ok", "message": "Test data received successfully"}