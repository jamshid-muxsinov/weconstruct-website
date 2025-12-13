import logging
import traceback
from pathlib import Path
from typing import Optional
from src.pages.translations import TRANSLATIONS
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import or_, func
import os
import uuid
from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.core.security import get_current_active_user
import shutil
from src.models.shop_models import User, Project, Transaction, ProjectFile, QuoteRequest, Contact
from src.pages.admin.dependencies import get_common_context

router = APIRouter(prefix="/projects", tags=["Projects"])
BASE_DIR = Path("/app")
log = logging.getLogger(__name__)

@router.get("/", response_class=HTMLResponse, name="admin_project_list")
async def project_list(
    request: Request,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    # ИЗМЕНЕНИЕ ЗДЕСЬ: принимаем str, а не int, чтобы не падать от пустой строки
    manager_id: Optional[str] = Query(None), 
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    try:
        user = context['user']
        
        # 1. Базовый запрос
        stmt = select(Project).options(
            selectinload(Project.manager),
            selectinload(Project.quote_request).selectinload(QuoteRequest.contact)
        ).order_by(Project.created_at.desc())
        
        # 2. Поиск
        if q:
            search_like = f"%{q.lower()}%"
            stmt = stmt.outerjoin(QuoteRequest, Project.quote_request_id == QuoteRequest.id)\
                       .outerjoin(Contact, QuoteRequest.contact_id == Contact.id)\
                       .where(
                           or_(
                               func.lower(Project.name).like(search_like),
                               func.lower(Contact.name).like(search_like),
                               func.lower(Contact.last_name).like(search_like),
                               func.lower(Contact.phone).like(search_like)
                           )
                       )

        # 3. Фильтры
        if status:
            stmt = stmt.where(Project.status == status)

        if user.is_superuser:
            # ИЗМЕНЕНИЕ ЗДЕСЬ: Проверяем, что manager_id не пустой и является числом
            if manager_id and manager_id.isdigit():
                stmt = stmt.where(Project.manager_id == int(manager_id))
        else:
            stmt = stmt.where((Project.manager_id == user.id) | 
                              (Project.designer_id == user.id) | 
                              (Project.foreman_id == user.id))
                              
        # Выполнение запроса
        result = await db.execute(stmt)
        projects = result.scalars().all()
        
        # Список менеджеров для фильтра
        staff_users = []
        if user.is_superuser:
            staff_users_result = await db.execute(select(User).where(User.is_staff == True).order_by(User.username))
            staff_users = staff_users_result.scalars().all()

        context.update({
            "projects": projects, 
            "title": "Проекты",
            "staff_users": staff_users,
            "request": request
        })

        # Если запрос от HTMX (поиск/фильтр)
        if "HX-Request" in request.headers:
            return templates.TemplateResponse("admin/partials/_project_list_content.html", context)
            
        return templates.TemplateResponse("admin/projects/list.html", context)

    except Exception as e:
        log.error(f"ERROR IN PROJECT LIST: {e}")
        traceback.print_exc()
        return HTMLResponse(f"<div style='padding:20px; color:red;'>Ошибка сервера: {str(e)}</div>", status_code=500)

@router.get("/create-from-quote/{quote_id}", response_class=RedirectResponse, name="create_project_from_quote")
async def create_project_from_quote(quote_id: int, request: Request, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_current_active_user)):
    quote = await db.get(QuoteRequest, quote_id, options=[selectinload(QuoteRequest.contact)])
    if not quote: raise HTTPException(404, "Заявка не найдена")
    stmt = select(Project).where(Project.quote_request_id == quote_id)
    if (await db.execute(stmt)).scalars().first(): return RedirectResponse(request.url_for('admin_project_detail', pk=(await db.execute(stmt)).scalars().first().id, locale=request.state.locale), 303)
    new_project = Project(name=f"{quote.business_type or 'Проект'} | {quote.contact.full_name if quote.contact else 'Клиент'}", quote_request_id=quote.id, manager_id=user.id, status=Project.StatusEnum.DESIGN)
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)
    return RedirectResponse(request.url_for('admin_project_detail', pk=new_project.id, locale=request.state.locale), 303)

@router.get("/{pk}", response_class=HTMLResponse, name="admin_project_detail")
async def project_detail(pk: int, request: Request, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    stmt = select(Project).where(Project.id == pk).options(selectinload(Project.transactions).selectinload(Transaction.created_by), selectinload(Project.files).joinedload(ProjectFile.uploaded_by), selectinload(Project.manager), selectinload(Project.designer), selectinload(Project.foreman), selectinload(Project.quote_request).selectinload(QuoteRequest.contact))
    project = (await db.execute(stmt)).scalars().first()
    if not project: raise HTTPException(404, "Проект не найден")
    income = sum(t.amount for t in project.transactions if t.type == Transaction.TypeEnum.INCOME)
    expenses = sum(t.amount for t in project.transactions if t.type == Transaction.TypeEnum.EXPENSE)
    staff_users = (await db.execute(select(User).where(User.is_staff == True))).scalars().all()
    context.update({"project": project, "income": income, "expenses": expenses, "profit": income - expenses, "title": project.name, "staff_users": staff_users})
    return templates.TemplateResponse("admin/projects/detail.html", context)

@router.post("/{pk}/upload-report", response_class=RedirectResponse, name="admin_project_upload")
async def upload_report(pk: int, request: Request, file: UploadFile = File(...), comment: str = Form(""), report_type: str = Form("photo_report"), db: AsyncSession = Depends(get_db_session), user: User = Depends(get_current_active_user)):
    project_media_dir = BASE_DIR / "media" / "projects" / str(pk)
    project_media_dir.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{ext}"
    with open(project_media_dir / filename, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    db.add(ProjectFile(project_id=pk, file_path=f"projects/{pk}/{filename}", type=ProjectFile.TypeEnum(report_type), comment=comment, uploaded_by_id=user.id))
    await db.commit()
    return RedirectResponse(request.url_for('admin_project_detail', pk=pk, locale=request.state.locale), 303)

@router.post("/{pk}/add-finance", response_class=RedirectResponse, name="admin_project_finance")
async def add_finance(pk: int, request: Request, amount: float = Form(...), type: str = Form(...), category: str = Form(...), description: str = Form(""), db: AsyncSession = Depends(get_db_session), user: User = Depends(get_current_active_user)):
    db.add(Transaction(project_id=pk, amount=amount, type=Transaction.TypeEnum(type), category=category, description=description, created_by_id=user.id))
    await db.commit()
    return RedirectResponse(request.url_for('admin_project_detail', pk=pk, locale=request.state.locale), 303)

@router.post("/{pk}/update-team", response_class=RedirectResponse, name="admin_project_update_team")
async def update_team(pk: int, request: Request, designer_id: int = Form(0), foreman_id: int = Form(0), status: str = Form(None), db: AsyncSession = Depends(get_db_session)):
    project = await db.get(Project, pk)
    if project:
        project.designer_id = designer_id if designer_id != 0 else None
        project.foreman_id = foreman_id if foreman_id != 0 else None
        if status: project.status = status
        await db.commit()
    return RedirectResponse(request.url_for('admin_project_detail', pk=pk, locale=request.state.locale), 303)