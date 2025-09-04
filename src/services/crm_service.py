from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import selectinload, joinedload
import wtforms
from sqlalchemy import func, desc, update, and_, delete
from sqlalchemy.future import select
from src.models.shop_models import QuoteRequest, Task, StatusChangeLog, Contact, ContactNote, User
from src.schemas.crm_schemas import QuoteRequestStatusUpdate, TaskCreate

import logging
log = logging.getLogger(__name__)

def to_naive_datetime(dt: datetime) -> datetime:
    """Convert timezone-aware datetime to naive datetime for database compatibility."""
    return dt.replace(tzinfo=None) if dt.tzinfo else dt

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

async def get_dashboard_data(db: AsyncSession, user_id: int):
    # Optimized query for tasks with better indexing
    my_tasks_stmt = (
        select(Task)
        .where(Task.assigned_to_id == user_id, Task.completed == False)
        .options(joinedload(Task.contact))
        .order_by(Task.due_date.nulls_last(), Task.created_at.desc())
        .limit(5)
    )
    my_tasks_result = await db.execute(my_tasks_stmt)
    my_tasks = my_tasks_result.scalars().all()
    
    # Optimized funnel query with better grouping
    funnel_stmt = (
        select(QuoteRequest.status, func.count(QuoteRequest.id))
        .group_by(QuoteRequest.status)
    )
    funnel_result = await db.execute(funnel_stmt)
    # Here we get a dictionary like {'new': 5, 'in_progress': 10}
    funnel_counts = {status_enum.value: count for status_enum, count in funnel_result.all()}
    
    # --- FIXING HERE ---
    sales_funnel = []
    for status_enum in QuoteRequest.StatusEnum:
        sales_funnel.append({
            "display_name": status_enum.value.replace('_', ' ').capitalize(), # Using .value for name
            "count": funnel_counts.get(status_enum.value, 0),
            "status": status_enum # <-- Now we pass the FULL ENUM OBJECT
        })

    # Optimized query for new requests with better joins
    new_req_stmt = (
        select(QuoteRequest)
        .where(
            QuoteRequest.status == QuoteRequest.StatusEnum.IMPORTED, 
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
    
    # Optimized activity log query
    activity_log_stmt = (
        select(StatusChangeLog)
        .order_by(StatusChangeLog.timestamp.desc())
        .limit(10)
    )
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
        QuoteRequest.StatusEnum.CLOSED,
        QuoteRequest.StatusEnum.ARCHIVED,
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
            "display_name": status_enum.value.replace('_', ' ').capitalize(),
            "requests": requests_by_status.get(status_enum.value, [])
        })
        
    return kanban_data


async def update_quote_request_status(db: AsyncSession, update_data: QuoteRequestStatusUpdate, user_id: int):
    try:
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
    except Exception as e:
        await db.rollback()
        print(f"Error updating quote request status: {e}")
        raise

async def assign_quote_request_to_user(db: AsyncSession, quote_id: int, user_id: int):
    req = await db.get(QuoteRequest, quote_id)
    if not req:
        return None
    new_assigned_id = user_id if user_id != 0 else None
    if req.assigned_to_id != new_assigned_id:
        old_status = req.status
        req.assigned_to_id = new_assigned_id
        if new_assigned_id is not None and old_status == QuoteRequest.StatusEnum.IMPORTED:
            req.status = QuoteRequest.StatusEnum.QUALIFICATION
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
    try:
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
        
        # Return all tasks for the quote request
        tasks_stmt = (
            select(Task)
            .where(Task.quote_request_id == task_data.quote_request_id)
            .order_by(Task.completed, Task.created_at.desc())
        )
        tasks_result = await db.execute(tasks_stmt)
        return tasks_result.scalars().all()
    except Exception as e:
        await db.rollback()
        print(f"Error creating task for quote: {e}")
        raise

async def get_user_performance_stats(db: AsyncSession, user_id: int):
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    # Convert to naive datetime for database compatibility
    thirty_days_ago_naive = to_naive_datetime(thirty_days_ago)
    
    completed_stmt = select(func.count(func.distinct(StatusChangeLog.quote_request_id))).where(
        StatusChangeLog.user_id == user_id,
        StatusChangeLog.new_status == QuoteRequest.StatusEnum.CLOSED,
        StatusChangeLog.timestamp >= thirty_days_ago_naive
    )
    completed_count = (await db.execute(completed_stmt)).scalar_one_or_none() or 0
    
    in_progress_stmt = select(func.count(func.distinct(StatusChangeLog.quote_request_id))).where(
        StatusChangeLog.user_id == user_id,
        StatusChangeLog.new_status == QuoteRequest.StatusEnum.QUALIFICATION,
        StatusChangeLog.timestamp >= thirty_days_ago_naive
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
    # Optimized query with better eager loading to prevent N+1 issues
    contact_stmt = (
        select(Contact)
        .where(Contact.id == contact_id)
        .options(
            selectinload(Contact.requests).joinedload(QuoteRequest.product),
            selectinload(Contact.requests).joinedload(QuoteRequest.assigned_to),
            selectinload(Contact.tasks).joinedload(Task.assigned_to),
            selectinload(Contact.timeline_notes).joinedload(ContactNote.user)
        )
    )
    result = await db.execute(contact_stmt)
    contact = result.scalars().first()
    
    if not contact:
        return None
        
    # Build timeline more efficiently
    timeline = []
    
    # Add requests to timeline
    for req in contact.requests:
        timeline.append({
            "type": "request",
            "timestamp": req.created_at,
            "obj": req
        })
    
    # Add tasks to timeline
    for task in contact.tasks:
        timeline.append({
            "type": "task",
            "timestamp": task.created_at,
            "obj": task
        })
    
    # Add notes to timeline
    for note in contact.timeline_notes:
        timeline.append({
            "type": "note",
            "timestamp": note.created_at,
            "obj": note
        })
        
    # Sort timeline once by timestamp
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
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    # Convert to naive datetime for database compatibility
    start_date_naive = to_naive_datetime(start_date)
    
    completed_subq = (
        select(
            StatusChangeLog.user_id,
            func.count(func.distinct(StatusChangeLog.quote_request_id)).label("completed_count")
        )
        .where(
            and_(
                StatusChangeLog.new_status == QuoteRequest.StatusEnum.CLOSED,
                StatusChangeLog.timestamp >= start_date_naive,
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

async def bulk_assign_requests(db: AsyncSession, card_ids: list[int], user_id: int, current_user_id: int) -> int:
    """Bulk assign multiple quote requests to a user"""
    try:
        stmt = (
            update(QuoteRequest)
            .where(QuoteRequest.id.in_(card_ids))
            .values(assigned_to_id=user_id)
        )
        result = await db.execute(stmt)
        
        # Create status change logs for assigned requests
        if user_id and result.rowcount > 0:
            # Update status to IN_PROGRESS for NEW requests
            update_status_stmt = (
                update(QuoteRequest)
                .where(
                    QuoteRequest.id.in_(card_ids),
                    QuoteRequest.status == QuoteRequest.StatusEnum.IMPORTED
                )
                .values(status=QuoteRequest.StatusEnum.QUALIFICATION)
            )
            await db.execute(update_status_stmt)
            
            # Create logs for the assignments
            for card_id in card_ids:
                log = StatusChangeLog(
                    quote_request_id=card_id,
                    user_id=current_user_id,
                    old_status=QuoteRequest.StatusEnum.IMPORTED,
                    new_status=QuoteRequest.StatusEnum.QUALIFICATION,
                    note=f"Bulk assigned to user {user_id}"
                )
                db.add(log)
        
        await db.commit()
        return result.rowcount
    except Exception as e:
        await db.rollback()
        print(f"Error in bulk assign: {e}")
        raise

async def bulk_update_status(db: AsyncSession, card_ids: list[int], status: str, current_user_id: int) -> int:
    """Bulk update status of multiple quote requests"""
    try:
        # Convert string status to enum
        status_enum = None
        for enum_status in QuoteRequest.StatusEnum:
            if enum_status.value == status:
                status_enum = enum_status
                break
        
        if not status_enum:
            raise ValueError(f"Invalid status: {status}")
        
        # Get current statuses for logging
        current_requests_stmt = select(QuoteRequest.id, QuoteRequest.status).where(
            QuoteRequest.id.in_(card_ids)
        )
        current_requests_result = await db.execute(current_requests_stmt)
        current_requests = {req_id: old_status for req_id, old_status in current_requests_result.all()}
        
        # Update statuses
        stmt = (
            update(QuoteRequest)
            .where(QuoteRequest.id.in_(card_ids))
            .values(status=status_enum)
        )
        result = await db.execute(stmt)
        
        # Create status change logs
        for card_id in card_ids:
            if card_id in current_requests:
                old_status = current_requests[card_id]
                if old_status != status_enum:
                    log = StatusChangeLog(
                        quote_request_id=card_id,
                        user_id=current_user_id,
                        old_status=old_status,
                        new_status=status_enum,
                        note=f"Bulk status update to {status}"
                    )
                    db.add(log)
        
        await db.commit()
        return result.rowcount
    except Exception as e:
        await db.rollback()
        print(f"Error in bulk status update: {e}")
        raise

async def update_single_card_status(db: AsyncSession, card_id: int, status: str, current_user_id: int):
    """Update status of a single card (for drag & drop and swipe gestures)"""
    try:
        # Convert string status to enum
        status_enum = None
        for enum_status in QuoteRequest.StatusEnum:
            if enum_status.value == status:
                status_enum = enum_status
                break
        
        if not status_enum:
            raise ValueError(f"Invalid status: {status}")
        
        req = await db.get(QuoteRequest, card_id)
        if not req:
            return None
            
        old_status = req.status
        
        if old_status == status_enum:
            return req
        
        req.status = status_enum
        
        log = StatusChangeLog(
            quote_request_id=req.id,
            user_id=current_user_id,
            old_status=old_status,
            new_status=req.status,
            note="Status updated via drag & drop or swipe"
        )
        db.add(req)
        db.add(log)
        await db.commit()
        await db.refresh(req)
        return req
    except Exception as e:
        await db.rollback()
        print(f"Error updating single card status: {e}")
        raise

async def export_requests_csv(db: AsyncSession, card_ids: list[int] = None) -> str:
    """Export quote requests to CSV format"""
    try:
        import csv
        import io
        
        # Base query
        stmt = (
            select(QuoteRequest)
            .options(
                joinedload(QuoteRequest.contact),
                joinedload(QuoteRequest.product),
                joinedload(QuoteRequest.assigned_to)
            )
            .order_by(QuoteRequest.created_at.desc())
        )
        
        # Filter by specific IDs if provided
        if card_ids:
            stmt = stmt.where(QuoteRequest.id.in_(card_ids))
        
        result = await db.execute(stmt)
        requests = result.scalars().unique().all()
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Client Name', 'Phone', 'Email', 'Product', 'Status', 
            'Assigned To', 'Business Type', 'Message', 'Created At'
        ])
        
        # Write data
        for req in requests:
            writer.writerow([
                req.id,
                req.contact.full_name if req.contact else '',
                req.contact.phone if req.contact else '',
                req.contact.email if req.contact else '',
                req.product.name_ru if req.product else 'General Request',
                req.status.value,
                req.assigned_to.username if req.assigned_to else 'Unassigned',
                req.business_type or '',
                req.message or '',
                req.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return output.getvalue()
    except Exception as e:
        print(f"Error exporting requests to CSV: {e}")
        raise

async def merge_duplicate_contacts(db: AsyncSession) -> dict:
    """
    Находит и объединяет дубликаты контактов по номеру телефона.
    Возвращает статистику по выполненной работе.
    """
    log.info("Запуск процесса поиска и слияния дубликатов контактов.")

    # Создаем нормализованное поле телефона (только цифры, последние 9)
    # для надежного сравнения
    normalized_phone = func.substr(func.regexp_replace(Contact.phone, r'\D', '', 'g'), -9)

    # Находим группы телефонных номеров, у которых больше одного контакта
    subquery = (
        select(normalized_phone.label("phone_normalized"))
        .group_by("phone_normalized")
        .having(func.count(Contact.id) > 1)
        .subquery()
    )

    # Выбираем все контакты, которые являются дубликатами
    stmt = (
        select(Contact)
        .where(normalized_phone.in_(select(subquery)))
        .order_by(normalized_phone, Contact.id) # Сортируем, чтобы самый старый был первым
    )

    result = await db.execute(stmt)
    all_duplicates = result.scalars().all()

    if not all_duplicates:
        log.info("Дубликаты контактов не найдены.")
        return {"merged_groups": 0, "deleted_contacts": 0, "message": "Дубликаты контактов не найдены."}

    # Группируем контакты по нормализованному номеру
    contacts_by_phone = {}
    for contact in all_duplicates:
        phone_key = ''.join(filter(str.isdigit, contact.phone))[-9:]
        if phone_key not in contacts_by_phone:
            contacts_by_phone[phone_key] = []
        contacts_by_phone[phone_key].append(contact)

    merged_groups_count = 0
    deleted_contacts_count = 0

    for phone, contacts in contacts_by_phone.items():
        if len(contacts) < 2:
            continue
        
        # Первый контакт в группе (самый старый по id) - наш главный
        master_contact = contacts[0]
        duplicate_contacts = contacts[1:]
        duplicate_ids = [c.id for c in duplicate_contacts]

        log.info(f"Обнаружена группа дубликатов для номера *****{phone[-4:]}. "
                 f"Главный ID: {master_contact.id}, дубликаты: {duplicate_ids}")

        # 1. Переназначаем QuoteRequests
        await db.execute(
            update(QuoteRequest)
            .where(QuoteRequest.contact_id.in_(duplicate_ids))
            .values(contact_id=master_contact.id)
        )
        # 2. Переназначаем Tasks
        await db.execute(
            update(Task)
            .where(Task.contact_id.in_(duplicate_ids))
            .values(contact_id=master_contact.id)
        )
        # 3. Переназначаем ContactNotes
        await db.execute(
            update(ContactNote)
            .where(ContactNote.contact_id.in_(duplicate_ids))
            .values(contact_id=master_contact.id)
        )
        
        # 4. Удаляем "пустые" дубликаты контактов
        await db.execute(
            delete(Contact)
            .where(Contact.id.in_(duplicate_ids))
        )
        
        merged_groups_count += 1
        deleted_contacts_count += len(duplicate_ids)
        log.info(f"Успешно объединены. {len(duplicate_ids)} контактов удалено.")

    await db.commit()
    
    message = (f"Операция завершена. "
               f"Обработано групп дубликатов: {merged_groups_count}. "
               f"Объединено и удалено контактов: {deleted_contacts_count}.")
    log.info(message)
    return {"merged_groups": merged_groups_count, "deleted_contacts": deleted_contacts_count, "message": message}

async def find_potential_duplicates(db: AsyncSession) -> list:
    """
    Только находит группы потенциальных дубликатов без их слияния.
    Нужно для диагностики.
    """
    log.info("Запуск диагностики дубликатов контактов.")

    normalized_phone = func.substr(func.regexp_replace(Contact.phone, r'\D', '', 'g'), -9)

    subquery = (
        select(normalized_phone.label("phone_normalized"))
        .group_by("phone_normalized")
        .having(func.count(Contact.id) > 1)
        .subquery()
    )

    stmt = (
        select(Contact)
        .where(normalized_phone.in_(select(subquery)))
        .order_by(normalized_phone, Contact.id)
    )

    result = await db.execute(stmt)
    all_duplicates = result.scalars().all()

    if not all_duplicates:
        return []

    # Группируем контакты для удобного отображения
    contacts_by_phone = {}
    for contact in all_duplicates:
        phone_key = ''.join(filter(str.isdigit, contact.phone))[-9:]
        if phone_key not in contacts_by_phone:
            contacts_by_phone[phone_key] = {
                "normalized_phone": phone_key,
                "contacts": []
            }
        contacts_by_phone[phone_key]["contacts"].append(contact)

    return list(contacts_by_phone.values())