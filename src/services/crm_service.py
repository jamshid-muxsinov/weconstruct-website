from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, update, and_
from datetime import datetime, timedelta
from sqlalchemy.orm import selectinload, joinedload
import wtforms

from src.models.shop_models import QuoteRequest, Task, StatusChangeLog, Contact, ContactNote, User
from src.schemas.crm_schemas import QuoteRequestStatusUpdate, TaskCreate

# --- НОВАЯ ФУНКЦИЯ ---
async def get_latest_quote_request(db: AsyncSession) -> QuoteRequest | None:
    """Возвращает самую последнюю созданную заявку со всеми необходимыми связями для рендеринга карточки."""
    stmt = (
        select(QuoteRequest)
        .options(
            joinedload(QuoteRequest.contact).selectinload(Contact.timeline_notes),
            joinedload(QuoteRequest.product),
            joinedload(QuoteRequest.assigned_to)
        )
        .order_by(QuoteRequest.id.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalars().first()
# --- КОНЕЦ НОВОЙ ФУНКЦИИ ---

async def get_dashboard_data(db: AsyncSession, user_id: int):
    my_tasks_stmt = (
        select(Task)
        .where(Task.assigned_to_id == user_id, Task.completed == False)
        .options(joinedload(Task.contact))
        .order_by(Task.due_date)
        .limit(5)
    )
    my_tasks_result = await db.execute(my_tasks_stmt)
    my_tasks = my_tasks_result.scalars().all()
    
    funnel_stmt = select(QuoteRequest.status, func.count(QuoteRequest.id)).group_by(QuoteRequest.status)
    funnel_result = await db.execute(funnel_stmt)
    funnel_counts = {status.value: count for status, count in funnel_result.all()}
    
    sales_funnel = []
    for status_enum in QuoteRequest.StatusEnum:
        sales_funnel.append({
            "name": status_enum.name.replace('_', ' ').capitalize(),
            "count": funnel_counts.get(status_enum.value, 0),
            "status": status_enum.value
        })

    new_req_stmt = (
        select(QuoteRequest)
        .where(
            QuoteRequest.status == QuoteRequest.StatusEnum.NEW, 
            QuoteRequest.assigned_to_id.is_(None)
        )
        .options(
            joinedload(QuoteRequest.product),
            joinedload(QuoteRequest.contact).selectinload(Contact.timeline_notes)
        )
        .order_by(QuoteRequest.created_at.desc())
        .limit(3)
    )
    new_req_result = await db.execute(new_req_stmt)
    new_unassigned_requests = new_req_result.scalars().unique().all()
    
    activity_log_stmt = select(StatusChangeLog).order_by(StatusChangeLog.timestamp.desc()).limit(10)
    activity_log_result = await db.execute(activity_log_stmt)
    activity_log = activity_log_result.scalars().all()

    return {
        "my_tasks": my_tasks,
        "sales_funnel": sales_funnel,
        "new_unassigned_requests": new_unassigned_requests,
        "activity_log": activity_log,
    }

async def get_kanban_data(db: AsyncSession, show_archived: bool = False):
    """
    Получает данные для канбан-доски.
    """
    archived_statuses = [
        QuoteRequest.StatusEnum.COMPLETED,
        QuoteRequest.StatusEnum.CANCELLED,
    ]
    
    stmt = (
        select(QuoteRequest)
        .options(
            joinedload(QuoteRequest.contact).selectinload(Contact.timeline_notes),
            joinedload(QuoteRequest.product),
            joinedload(QuoteRequest.assigned_to)
        )
        .order_by(QuoteRequest.created_at.desc())
    )
    
    if not show_archived:
        stmt = stmt.where(QuoteRequest.status.notin_(archived_statuses))
        
    requests_result = await db.execute(stmt)
    all_requests = requests_result.scalars().unique().all()
    
    requests_by_status = {status.value: [] for status in QuoteRequest.StatusEnum}
    for req in all_requests:
        requests_by_status[req.status.value].append(req)
        
    kanban_data = []
    for status_enum in QuoteRequest.StatusEnum:
        if not show_archived and status_enum in archived_statuses and not requests_by_status.get(status_enum.value):
            continue
            
        kanban_data.append({
            "status_code": status_enum.value,
            "display_name": status_enum.name.replace('_', ' ').capitalize(),
            "requests": requests_by_status.get(status_enum.value, [])
        })
        
    return kanban_data

async def get_latest_quote_request(db: AsyncSession) -> QuoteRequest | None:
    """Возвращает самую последнюю созданную заявку со всеми необходимыми связями для рендеринга карточки."""
    stmt = (
        select(QuoteRequest)
        .options(
            joinedload(QuoteRequest.contact).selectinload(Contact.timeline_notes),
            joinedload(QuoteRequest.product),
            joinedload(QuoteRequest.assigned_to)
        )
        .order_by(QuoteRequest.id.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def update_quote_request_status(db: AsyncSession, update_data: QuoteRequestStatusUpdate, user_id: int):
    req = await db.get(QuoteRequest, update_data.id)
    if not req:
        return None
        
    old_status = req.status
    
    if old_status == update_data.status:
        return req
    
    req.status = update_data.status
    
    log = StatusChangeLog(
        quote_request_id=req.id,
        user_id=user_id,
        old_status=old_status,
        new_status=req.status,
        note="Статус изменен на Kanban-доске"
    )
    db.add(req)
    db.add(log)
    await db.commit()
    await db.refresh(req)
    return req

async def assign_quote_request_to_user(db: AsyncSession, quote_id: int, user_id: int):
    req = await db.get(QuoteRequest, quote_id)
    if not req:
        return None
    new_assigned_id = user_id if user_id != 0 else None
    if req.assigned_to_id != new_assigned_id:
        old_status = req.status
        req.assigned_to_id = new_assigned_id
        if new_assigned_id is not None and old_status == QuoteRequest.StatusEnum.NEW:
            req.status = QuoteRequest.StatusEnum.IN_PROGRESS
            log = StatusChangeLog(
                quote_request_id=req.id,
                user_id=new_assigned_id,
                old_status=old_status,
                new_status=req.status,
                note='Взято в работу'
            )
            db.add(log)
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req

async def toggle_task_completion(db: AsyncSession, task_id: int, user_id: int):
    task = await db.get(Task, task_id)
    if not task or task.assigned_to_id != user_id:
        return None
    task.completed = not task.completed
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task

async def create_task_for_quote(db: AsyncSession, task_data: TaskCreate):
    quote_req = await db.get(QuoteRequest, task_data.quote_request_id)
    if not quote_req:
        return None
    new_task = Task(
        title=task_data.title,
        assigned_to_id=task_data.assigned_to_id,
        quote_request_id=task_data.quote_request_id,
        contact_id=quote_req.contact_id
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    tasks_stmt = select(Task).where(Task.quote_request_id == task_data.quote_request_id).order_by(Task.completed, Task.created_at.desc())
    tasks_result = await db.execute(tasks_stmt)
    return tasks_result.scalars().all()

async def get_user_performance_stats(db: AsyncSession, user_id: int):
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    completed_stmt = select(func.count(func.distinct(StatusChangeLog.quote_request_id))).where(
        StatusChangeLog.user_id == user_id,
        StatusChangeLog.new_status == QuoteRequest.StatusEnum.COMPLETED,
        StatusChangeLog.timestamp >= thirty_days_ago
    )
    completed_count = (await db.execute(completed_stmt)).scalar_one_or_none() or 0
    
    in_progress_stmt = select(func.count(func.distinct(StatusChangeLog.quote_request_id))).where(
        StatusChangeLog.user_id == user_id,
        StatusChangeLog.new_status == QuoteRequest.StatusEnum.IN_PROGRESS,
        StatusChangeLog.timestamp >= thirty_days_ago
    )
    in_progress_count = (await db.execute(in_progress_stmt)).scalar_one_or_none() or 0

    conversion_rate = (completed_count / in_progress_count * 100) if in_progress_count > 0 else 0
    
    tasks_stmt = select(func.count(Task.id)).where(
        Task.assigned_to_id == user_id,
        Task.completed == True
    )
    tasks_completed_count = (await db.execute(tasks_stmt)).scalar_one_or_none() or 0

    return {
        "requests_completed": completed_count,
        "requests_in_progress": in_progress_count,
        "conversion_rate": round(conversion_rate, 1),
        "tasks_completed": tasks_completed_count
    }

async def get_user_activity_feed(db: AsyncSession, user_id: int, limit: int = 10):
    stmt = select(StatusChangeLog).where(
        StatusChangeLog.user_id == user_id
    ).order_by(
        desc(StatusChangeLog.timestamp)
    ).limit(limit)
    
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_contact_360_view(db: AsyncSession, contact_id: int):
    contact = await db.get(
        Contact, 
        contact_id, 
        options=[
            selectinload(Contact.requests).joinedload(QuoteRequest.product),
            selectinload(Contact.requests).joinedload(QuoteRequest.assigned_to),
            selectinload(Contact.tasks).joinedload(Task.assigned_to),
            selectinload(Contact.timeline_notes).joinedload(ContactNote.user)
        ]
    )
    if not contact:
        return None
        
    timeline = []
    for req in contact.requests:
        timeline.append({
            "type": "request",
            "timestamp": req.created_at,
            "obj": req
        })
    for task in contact.tasks:
        timeline.append({
            "type": "task",
            "timestamp": task.created_at,
            "obj": task
        })
    for note in contact.timeline_notes:
        timeline.append({
            "type": "note",
            "timestamp": note.created_at,
            "obj": note
        })
        
    timeline.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "contact": contact,
        "timeline": timeline
    }

async def update_contact(db: AsyncSession, contact_id: int, form: wtforms.Form) -> Contact:
    contact = await db.get(Contact, contact_id)
    if not contact:
        return None
    form_data = form.data.copy()
    form_data.pop('notes', None)
    
    for key, value in form_data.items():
        setattr(contact, key, value)
        
    await db.commit()
    await db.refresh(contact)
    return contact

async def add_note_to_contact(db: AsyncSession, contact_id: int, user_id: int, note_text: str) -> ContactNote:
    contact = await db.get(Contact, contact_id)
    user = await db.get(User, user_id)
    if not contact or not user:
        return None
    new_note = ContactNote(note=note_text, contact_id=contact_id, user_id=user_id)
    db.add(new_note)
    await db.commit()
    return new_note

async def toggle_pin_contact_note(db: AsyncSession, note_id: int, contact_id: int):
    note_to_pin = await db.get(ContactNote, note_id)
    if not note_to_pin or note_to_pin.contact_id != contact_id:
        return None
    
    new_pin_state = not note_to_pin.is_pinned
    
    await db.execute(
        update(ContactNote)
        .where(ContactNote.contact_id == contact_id)
        .values(is_pinned=False)
    )
    
    note_to_pin.is_pinned = new_pin_state
    
    await db.commit()
    return note_to_pin

async def get_top_managers(db: AsyncSession, days: int = 30):
    start_date = datetime.utcnow() - timedelta(days=days)
    completed_subq = (
        select(
            StatusChangeLog.user_id,
            func.count(func.distinct(StatusChangeLog.quote_request_id)).label("completed_count")
        )
        .where(
            and_(
                StatusChangeLog.new_status == QuoteRequest.StatusEnum.COMPLETED,
                StatusChangeLog.timestamp >= start_date,
                StatusChangeLog.user_id.isnot(None)
            )
        )
        .group_by(StatusChangeLog.user_id)
        .subquery()
    )
    stmt = (
        select(
            User,
            func.coalesce(completed_subq.c.completed_count, 0).label("completed_total")
        )
        .outerjoin(completed_subq, User.id == completed_subq.c.user_id)
        .where(User.is_staff == True)
        .order_by(desc("completed_total"))
        .limit(5)
    )
    
    result = await db.execute(stmt)
    top_managers = result.all() 
    return top_managers