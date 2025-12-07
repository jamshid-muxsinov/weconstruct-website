import os
import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.core.security import get_current_active_user
from src.models.shop_models import User, Project, Transaction, ProjectFile, QuoteRequest
from src.pages.admin.dependencies import get_common_context

router = APIRouter(prefix="/projects", tags=["Projects"])
BASE_DIR = Path("/app")

@router.get("/", response_class=HTMLResponse, name="admin_project_list")
async def project_list(
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    user = context['user']
    
    # Загружаем проекты
    stmt = select(Project).options(
        selectinload(Project.manager),
        selectinload(Project.quote_request).selectinload(QuoteRequest.contact)
    )
    
    # Если не суперюзер, показываем только проекты, где пользователь участвует
    if not user.is_superuser:
        stmt = stmt.where((Project.manager_id == user.id) | 
                          (Project.designer_id == user.id) | 
                          (Project.foreman_id == user.id))
                          
    stmt = stmt.order_by(Project.created_at.desc())
    projects = (await db.execute(stmt)).scalars().all()
    
    context.update({
        "projects": projects, 
        "title": "Управление проектами"
    })
    return templates.TemplateResponse("admin/projects/list.html", context)

@router.get("/create-from-quote/{quote_id}", response_class=RedirectResponse, name="create_project_from_quote")
async def create_project_from_quote(
    quote_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user)
):
    """Создает проект на основе закрытой заявки"""
    quote = await db.get(QuoteRequest, quote_id, options=[selectinload(QuoteRequest.contact)])
    if not quote:
        raise HTTPException(404, "Заявка не найдена")
    
    # Проверка на дубликат
    stmt = select(Project).where(Project.quote_request_id == quote_id)
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        return RedirectResponse(request.url_for('admin_project_detail', pk=existing.id, locale=request.state.locale), status_code=303)

    # Формируем имя проекта
    client_name = quote.contact.full_name if quote.contact else "Клиент"
    proj_name = f"{quote.business_type or 'Проект'} | {client_name}"
    
    new_project = Project(
        name=proj_name,
        quote_request_id=quote.id,
        manager_id=user.id, # Текущий юзер становится менеджером
        status=Project.StatusEnum.DESIGN
    )
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)
    
    return RedirectResponse(request.url_for('admin_project_detail', pk=new_project.id, locale=request.state.locale), status_code=303)

@router.get("/{pk}", response_class=HTMLResponse, name="admin_project_detail")
async def project_detail(
    pk: int,
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(Project).where(Project.id == pk).options(
        selectinload(Project.transactions).selectinload(Transaction.created_by),
        selectinload(Project.files).joinedload(ProjectFile.uploaded_by),
        selectinload(Project.manager),
        selectinload(Project.designer),
        selectinload(Project.foreman),
        selectinload(Project.quote_request).selectinload(QuoteRequest.contact)
    )
    project = (await db.execute(stmt)).scalars().first()
    if not project:
        raise HTTPException(404, "Проект не найден")
    
    # Считаем деньги
    income = sum(t.amount for t in project.transactions if t.type == Transaction.TypeEnum.INCOME)
    expenses = sum(t.amount for t in project.transactions if t.type == Transaction.TypeEnum.EXPENSE)
    profit = income - expenses

    # Список сотрудников для выпадающего списка
    staff_users = []
    if context['user'].is_superuser or context['user'].id == project.manager_id:
        staff_users = (await db.execute(select(User).where(User.is_staff == True))).scalars().all()

    context.update({
        "project": project, 
        "income": income, 
        "expenses": expenses, 
        "profit": profit,
        "title": f"Проект: {project.name}",
        "staff_users": staff_users
    })
    return templates.TemplateResponse("admin/projects/detail.html", context)

@router.post("/{pk}/upload-report", response_class=RedirectResponse, name="admin_project_upload")
async def upload_report(
    pk: int,
    request: Request,
    file: UploadFile = File(...),
    comment: str = Form(""),
    report_type: str = Form("photo_report"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user)
):
    # Папка для сохранения: /app/media/projects/ID_ПРОЕКТА
    project_media_dir = BASE_DIR / "media" / "projects" / str(pk)
    project_media_dir.mkdir(parents=True, exist_ok=True)
    
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{ext}"
    file_path_relative = f"projects/{pk}/{filename}"
    
    file_path = project_media_dir / filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    new_file = ProjectFile(
        project_id=pk,
        file_path=file_path_relative,
        type=ProjectFile.TypeEnum(report_type),
        comment=comment,
        uploaded_by_id=user.id
    )
    db.add(new_file)
    await db.commit()
    
    return RedirectResponse(request.url_for('admin_project_detail', pk=pk, locale=request.state.locale), status_code=303)

@router.post("/{pk}/add-finance", response_class=RedirectResponse, name="admin_project_finance")
async def add_finance(
    pk: int,
    request: Request,
    amount: float = Form(...),
    type: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user)
):
    trans = Transaction(
        project_id=pk,
        amount=amount,
        type=Transaction.TypeEnum(type),
        category=category,
        description=description,
        created_by_id=user.id
    )
    db.add(trans)
    await db.commit()
    return RedirectResponse(request.url_for('admin_project_detail', pk=pk, locale=request.state.locale), status_code=303)

@router.post("/{pk}/update-team", response_class=RedirectResponse, name="admin_project_update_team")
async def update_team(
    pk: int,
    request: Request,
    designer_id: int = Form(0),
    foreman_id: int = Form(0),
    status: str = Form(None),
    db: AsyncSession = Depends(get_db_session)
):
    project = await db.get(Project, pk)
    if not project: raise HTTPException(404)
    
    project.designer_id = designer_id if designer_id != 0 else None
    project.foreman_id = foreman_id if foreman_id != 0 else None
    
    if status:
        project.status = status
    
    await db.commit()
    return RedirectResponse(request.url_for('admin_project_detail', pk=pk, locale=request.state.locale), status_code=303)