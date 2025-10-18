
import json
from urllib.parse import quote
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import wtforms

from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.services import crm_service, user_service
from .dependencies import get_common_context
from src.pages.admin.crud import set_hx_trigger_header
from src.models.shop_models import User

router = APIRouter()

class ChangePasswordForm(wtforms.Form):
    old_password = wtforms.PasswordField('Текущий пароль', validators=[wtforms.validators.DataRequired()])
    new_password = wtforms.PasswordField('Новый пароль', validators=[wtforms.validators.DataRequired(), wtforms.validators.Length(min=8)])
    confirm_password = wtforms.PasswordField('Повторите новый пароль', validators=[
        wtforms.validators.DataRequired(),
        wtforms.validators.EqualTo('new_password', message='Пароли должны совпадать')
    ])


@router.get("/profile", response_class=HTMLResponse, name="admin_profile")
async def get_my_profile_page(
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    user_id = context["user"].id
    
    performance_stats = await crm_service.get_user_performance_stats(db, user_id)
    activity_feed = await crm_service.get_user_activity_feed(db, user_id)
    
    context.update({
        "title": "Мой профиль",
        "stats": performance_stats,
        "feed": activity_feed,
        "form": ChangePasswordForm(),
        "profile_user": context["user"]
    })
    
    return templates.TemplateResponse("admin/profile.html", context)


@router.post("/profile", response_class=HTMLResponse, name="admin_profile_post")
async def post_my_profile_page(
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    form_data = await request.form()
    form = ChangePasswordForm(form_data)
    user = context["user"]
    
    if form.validate():
        success = await user_service.change_user_password(
            db, 
            user=user, 
            old_password=form.old_password.data, 
            new_password=form.new_password.data
        )
        if success:
            redirect_url = request.url_for("admin_profile", locale=request.state.locale)
            response = RedirectResponse(redirect_url, status_code=303)
            return set_hx_trigger_header(response, "password_changed_success", request)
        else:
            form.old_password.errors.append("Неверный текущий пароль.")
    
    performance_stats = await crm_service.get_user_performance_stats(db, user.id)
    activity_feed = await crm_service.get_user_activity_feed(db, user.id)
    
    context.update({
        "title": "Мой профиль",
        "stats": performance_stats,
        "feed": activity_feed,
        "form": form,
        "profile_user": user
    })
    
    return templates.TemplateResponse("admin/profile.html", context, status_code=422)

@router.get("/users/{pk}/profile", response_class=HTMLResponse, name="admin_user_profile")
async def get_user_profile_page(
    pk: int,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    profile_user = await db.get(User, pk)
    if not profile_user or not profile_user.is_staff:
        raise HTTPException(status_code=404, detail="User not found")

    if profile_user.id == context["user"].id:
        return RedirectResponse(url=context["request"].url_for("admin_profile"))

    performance_stats = await crm_service.get_user_performance_stats(db, pk)
    activity_feed = await crm_service.get_user_activity_feed(db, pk)
    
    context.update({
        "title": f"Профиль: {profile_user.username}",
        "profile_user": profile_user,
        "stats": performance_stats,
        "feed": activity_feed,
    })
    
    return templates.TemplateResponse("admin/user_profile_public.html", context)