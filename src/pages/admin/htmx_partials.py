from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from slugify import slugify
from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.core.security import get_current_active_user
from src.models.shop_models import User, QuoteRequest, Task, StatusChangeLog, Category
from src.services import crm_service
from src.schemas.crm_schemas import TaskCreate

router = APIRouter(prefix="/htmx", tags=["Admin HTMX Partials"])

class MockTaskForm:
    def __init__(self, staff_users, current_user):
        self.title = "<input type='text' name='title' class='task-title-input' placeholder='Название новой задачи...' required>"
        options = "".join([f"<option value='{user.id}'>{user.username}</option>" for user in staff_users])
        self.assigned_to = f"<select name='assigned_to_id' class='task-user-select'>{options}</select>"

@router.get("/quoterequest-modal/{pk}", response_class=HTMLResponse, name="shop_quoterequest_modal")
async def get_quote_request_modal(
    pk: int,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    stmt = (
        select(QuoteRequest)
        .where(QuoteRequest.id == pk)
        .options(
            selectinload(QuoteRequest.tasks).joinedload(Task.assigned_to),
            selectinload(QuoteRequest.status_logs).joinedload(StatusChangeLog.user),
        )
    )
    quote_request = (await db.execute(stmt)).scalars().first()

    if not quote_request:
        return HTMLResponse("Заявка не найдена", status_code=404)

    staff_users = (await db.execute(select(User).where(User.is_staff == True))).scalars().all()

    context = {
        "request": request,
        "req": quote_request,
        "tasks": sorted(quote_request.tasks, key=lambda t: (t.completed, -t.id)),
        "history": sorted(quote_request.status_logs, key=lambda h: h.timestamp, reverse=True),
        "task_form": MockTaskForm(staff_users, current_user),
    }
    return templates.TemplateResponse("admin/partials/quoterequest_modal_content.html", context)


@router.post("/quoterequest/{pk}/add-task", response_class=HTMLResponse, name="shop_quoterequest_add_task")
async def add_task_from_modal(
    pk: int,
    request: Request,
    title: str = Form(...),
    assigned_to_id: int = Form(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    task_data = TaskCreate(
        title=title,
        assigned_to_id=assigned_to_id,
        quote_request_id=pk
    )
    updated_tasks = await crm_service.create_task_for_quote(db, task_data)

    if updated_tasks is None:
        return HTMLResponse("Ошибка: заявка не найдена.", status_code=404)

    context = {
        "request": request,
        "tasks": sorted(updated_tasks, key=lambda t: (t.completed, -t.id)),
    }
    return templates.TemplateResponse("admin/partials/_task_list_partial.html", context)

@router.post("/task/{pk}/toggle", response_class=HTMLResponse, name="api_toggle_task_htmx")
async def toggle_task_htmx(
    pk: int,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    task = await crm_service.toggle_task_completion(db, pk, current_user)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or permission denied")
    
    tasks_stmt = (
        select(Task)
        .where(Task.quote_request_id == task.quote_request_id)
        .options(selectinload(Task.assigned_to))
    )
    tasks_result = await db.execute(tasks_stmt)
    all_tasks_for_quote = tasks_result.scalars().all()
    
    context = {
        "request": request,
        "tasks": sorted(all_tasks_for_quote, key=lambda t: (t.completed, -t.id)),
    }
    return templates.TemplateResponse("admin/partials/_task_list_partial.html", context)
@router.get("/category-add-modal/", response_class=HTMLResponse, name="htmx_category_add_modal")
async def get_category_add_modal(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Возвращает HTML-содержимое для модального окна добавления категории."""
    return templates.TemplateResponse("admin/partials/_category_add_modal.html", {"request": request})

@router.post("/category-add/", response_class=HTMLResponse, name="htmx_add_category")
async def add_category_htmx(
    request: Request,
    name: str = Form(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """Создает новую категорию и возвращает обновленный список <option> для <select>."""
    new_category = Category(name=name, slug=slugify(name))
    db.add(new_category)
    await db.commit()
    await db.refresh(new_category)

    all_categories = (await db.execute(select(Category).order_by(Category.name))).scalars().all()

    context = {
        "request": request,
        "categories": all_categories,
        "selected_id": new_category.id 
    }
    return templates.TemplateResponse("admin/partials/_category_options.html", context)