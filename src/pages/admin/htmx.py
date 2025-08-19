import asyncio
import json
from urllib.parse import quote
from fastapi import APIRouter, Request, Depends, Form, HTTPException, Response, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, func, desc
from sqlalchemy.orm import selectinload, joinedload
from slugify import slugify
import wtforms
from wtforms.fields import StringField, SelectField
import os
from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.core.security import get_current_active_user
from src.models.shop_models import User, QuoteRequest, Task, StatusChangeLog, Category, Contact, Notification, ProductImage
from src.services import crm_service
from src.schemas.crm_schemas import TaskCreate
from .dependencies import get_common_context
from pathlib import Path
from sse_starlette.sse import EventSourceResponse
from src.core.cache import cache_manager

MEDIA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "media"
router = APIRouter(prefix="/htmx", tags=["Admin HTMX"])

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}

class TaskForm(wtforms.Form):
    title = StringField('Title')
    assigned_to_id = SelectField('Assigned To', coerce=int)

@router.get("/kanban/stream", name="admin_htmx_kanban_stream")
async def stream_new_kanban_cards(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Создает поток Server-Sent Events, который слушает Redis Pub/Sub 
    для мгновенной отправки новых заявок на канбан-доску.
    """
    if not cache_manager.is_redis_available:
        print("SSE stream stopped: Redis is not available.")
        return Response(status_code=204)

    async def event_generator():
        redis_client = cache_manager.redis_client
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("kanban_updates")
        
        try:
            while True:
                if await request.is_disconnected():
                    print("Client disconnected from SSE stream.")
                    break
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30)
                
                if message and message.get("type") == "message":
                    try:
                        quote_id = int(message["data"])
                    except (ValueError, TypeError):
                        continue

                    stmt = (
                        select(QuoteRequest).where(QuoteRequest.id == quote_id)
                        .options(
                            joinedload(QuoteRequest.contact).selectinload(Contact.timeline_notes),
                            joinedload(QuoteRequest.product),
                            joinedload(QuoteRequest.assigned_to)
                        )
                    )
                    result = await db.execute(stmt)
                    new_quote = result.scalars().first()

                    if new_quote:
                        card_html = templates.TemplateResponse(
                            "admin/partials/_kanban_card.html",
                            {"request": request, "req": new_quote}
                        ).body.decode("utf-8")
                        
                        yield {
                            "event": "new_quote",
                            "data": card_html
                        }
        except asyncio.CancelledError:
            print("SSE stream cancelled.")
        finally:
            await pubsub.unsubscribe("kanban_updates")
            print("Unsubscribed from Redis channel.")

    return EventSourceResponse(event_generator())

@router.get("/quoterequest-modal/{pk}", response_class=HTMLResponse, name="admin_htmx_quoterequest_modal")
async def get_quote_request_modal(
    pk: int,
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    stmt = (
        select(QuoteRequest)
        .where(QuoteRequest.id == pk)
        .options(
            selectinload(QuoteRequest.tasks).joinedload(Task.assigned_to),
            selectinload(QuoteRequest.contact),
            selectinload(QuoteRequest.product),
            selectinload(QuoteRequest.assigned_to)
        )
    )
    quote_request = (await db.execute(stmt)).scalars().first()
    if not quote_request:
        return HTMLResponse("Заявка не найдена", status_code=404)

    staff_users = (await db.execute(select(User).where(User.is_staff == True))).scalars().all()
    form = TaskForm()
    form.assigned_to_id.choices = [(user.id, user.username) for user in staff_users]

    context = {
        "request": request,
        "req": quote_request,
        "tasks": sorted(quote_request.tasks, key=lambda t: (t.completed, -t.id)),
        "task_form": form,
    }
    return templates.TemplateResponse("admin/partials/quoterequest_modal_content.html", context, headers=NO_CACHE_HEADERS)

@router.post("/quoterequest/{pk}/add-task", response_class=HTMLResponse, name="admin_htmx_add_task_to_quote")
async def add_task_to_quote(
    pk: int,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    title: str = Form(...),
    assigned_to_id: int = Form(...),
):
    task_data = TaskCreate(title=title, assigned_to_id=assigned_to_id, quote_request_id=pk)
    updated_tasks = await crm_service.create_task_for_quote(db, task_data)

    if updated_tasks is None: return HTMLResponse("Ошибка: заявка не найдена.", status_code=404)
    
    context = {"request": request, "tasks": sorted(updated_tasks, key=lambda t: (t.completed, -t.id))}
    return templates.TemplateResponse("admin/partials/_task_list_partial.html", context)

@router.post("/task/{pk}/toggle", response_class=HTMLResponse, name="admin_htmx_toggle_task")
async def toggle_task(
    pk: int, request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    task = await crm_service.toggle_task_completion(db, pk, current_user.id)
    if not task: 
        raise HTTPException(status_code=404, detail="Task not found or permission denied")

    contact_data = await crm_service.get_contact_360_view(db, task.contact_id)
    if not contact_data:
        return HTMLResponse("Контакт не найден.", status_code=404)

    context = {
        "request": request, 
        "timeline": contact_data["timeline"]
    }
    
    response = templates.TemplateResponse("admin/partials/_contact_timeline.html", context)
    trigger_payload = json.dumps({"show-toast": {"message": "Статус задачи изменен"}})
    response.headers["HX-Trigger"] = quote(trigger_payload)
    return response

@router.get("/category-add-modal/", response_class=HTMLResponse, name="admin_htmx_category_add_modal")
async def get_category_add_modal(request: Request):
    return templates.TemplateResponse("admin/partials/_category_add_modal.html", {"request": request})

@router.post("/category-add/", response_class=HTMLResponse, name="admin_htmx_add_category")
async def add_category_htmx(request: Request, name: str = Form(...), db: AsyncSession = Depends(get_db_session)):
    new_category = Category(name_ru=name, slug=slugify(name))
    db.add(new_category)
    await db.commit()
    await db.refresh(new_category)

    all_categories = (await db.execute(select(Category).order_by(Category.name_ru))).scalars().all()
    context = {
        "request": request,
        "categories": all_categories,
        "selected_id": new_category.id
    }
    return templates.TemplateResponse("admin/partials/_category_options.html", context)

@router.get("/kanban-content/", response_class=HTMLResponse, name="admin_htmx_kanban_content")
async def get_kanban_content(
    request: Request,
    show_archived: bool = False,
    db: AsyncSession = Depends(get_db_session)
):
    if not request.headers.get("hx-request"):
        kanban_url = request.url_for('admin_kanban_board')
        return RedirectResponse(f"{kanban_url}?show_archived={show_archived}")

    kanban_data = await crm_service.get_kanban_data(db, show_archived)
    context = {
        "request": request,
        "requests_by_status": kanban_data,
        "show_archived": show_archived,
    }
    return templates.TemplateResponse("admin/partials/_kanban_content.html", context, headers=NO_CACHE_HEADERS)

@router.get("/quote-slide-over/{pk}", response_class=HTMLResponse, name="admin_htmx_quote_slide_over")
async def get_quote_slide_over(
    pk: int,
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    stmt = (
        select(QuoteRequest).where(QuoteRequest.id == pk)
        .options(
            joinedload(QuoteRequest.contact),
            joinedload(QuoteRequest.product),
            joinedload(QuoteRequest.assigned_to),
            selectinload(QuoteRequest.tasks).joinedload(Task.assigned_to)
        )
    )
    quote_request = (await db.execute(stmt)).scalars().first()
    if not quote_request:
        return HTMLResponse("Заявка не найдена", status_code=404)

    staff_users = (await db.execute(select(User).where(User.is_staff == True))).scalars().all()
    
    task_form = TaskForm()
    task_form.assigned_to_id.choices = [(user.id, user.username) for user in staff_users]
    
    context = {
        "request": request,
        "req": quote_request,
        "staff_users": staff_users,
        "tasks": sorted(quote_request.tasks, key=lambda t: (t.completed, -t.id)),
        "task_form": task_form,
    }
    return templates.TemplateResponse("admin/partials/_quote_slide_over.html", context, headers=NO_CACHE_HEADERS)

@router.get("/dashboard-new-requests/", response_class=HTMLResponse, name="admin_htmx_dashboard_new_requests")
async def htmx_get_dashboard_new_requests(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    dashboard_data = await crm_service.get_dashboard_data(db, 0)
    context = {
        "request": request,
        "new_unassigned_requests": dashboard_data.get("new_unassigned_requests", [])
    }
    return templates.TemplateResponse("admin/partials/_dashboard_new_requests.html", context, headers=NO_CACHE_HEADERS)
    
@router.get("/contact-search/", response_class=HTMLResponse, name="admin_htmx_contact_search")
async def htmx_contact_search(q: str, request: Request, db: AsyncSession = Depends(get_db_session)):
    if not q:
        return HTMLResponse("")

    search_query = f"%{q}%"
    stmt = (
        select(Contact)
        .where(
            or_(
                func.concat(Contact.name, ' ', Contact.last_name).ilike(search_query),
                Contact.phone.ilike(search_query)
            )
        )
        .limit(10)
    )
    result = await db.execute(stmt)
    contacts = result.scalars().all()
    
    context = {"request": request, "contacts": contacts}
    return templates.TemplateResponse("admin/partials/_contact_search_results.html", context, headers=NO_CACHE_HEADERS)

@router.get("/notifications/", response_class=HTMLResponse, name="admin_htmx_notifications")
async def htmx_get_notifications(
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    stmt = (
        select(Notification)
        .where(Notification.user_id == context["user"].id, Notification.is_read == False)
        .order_by(Notification.created_at.desc())
        .limit(5)
    )
    result = await db.execute(stmt)
    notifications = result.scalars().all()
    context["notifications"] = notifications
    
    return templates.TemplateResponse("admin/partials/_notifications_dropdown.html", context, headers=NO_CACHE_HEADERS)

@router.get("/notification-indicator/", response_class=HTMLResponse, name="admin_htmx_notification_indicator")
async def htmx_get_notification_indicator(
    context: dict = Depends(get_common_context)
):
    """Возвращает только HTML для иконки и счетчика уведомлений."""
    return templates.TemplateResponse("admin/partials/_notification_indicator.html", context, headers=NO_CACHE_HEADERS)

@router.delete("/product-image/{pk}/delete/", response_class=Response, name="admin_htmx_delete_product_image")
async def htmx_delete_product_image(pk: int, db: AsyncSession = Depends(get_db_session)):
    image = await db.get(ProductImage, pk)
    if image:
        try:
            file_to_delete = Path("media") / image.image
            if os.path.exists(file_to_delete):
                os.remove(file_to_delete)
        except OSError as e:
            print(f"Error deleting file {image.image}: {e}")
            
        await db.delete(image)
        await db.commit()
    return Response(status_code=200)