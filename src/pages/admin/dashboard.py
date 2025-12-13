import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case

from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.services import crm_service
from src.models.shop_models import Transaction, Project, QuoteRequest
from .dependencies import get_common_context

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse, name="admin_dashboard")
async def get_dashboard(
    request: Request,
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session),
):
    user = context["user"]
    
    # 1. Получаем данные по финансам (Всего приход / расход)
    # (В реальном проекте тут лучше фильтровать по датам, но пока берем всё)
    finance_stmt = select(
        func.sum(case((Transaction.type == Transaction.TypeEnum.INCOME, Transaction.amount), else_=0)),
        func.sum(case((Transaction.type == Transaction.TypeEnum.EXPENSE, Transaction.amount), else_=0))
    )
    finance_result = await db.execute(finance_stmt)
    total_income, total_expense = finance_result.one()
    total_income = total_income or 0
    total_expense = total_expense or 0
    net_profit = total_income - total_expense

    # 2. Активные проекты
    active_projects_count = await db.scalar(
        select(func.count(Project.id)).where(Project.status == Project.StatusEnum.CONSTRUCTION)
    ) or 0

    # 3. Данные дашборда от сервиса (Воронка, Задачи)
    dashboard_data = await crm_service.get_dashboard_data(db, user.id)
    
    # 4. Подготовка данных для Графика Воронки (JS требует массивы)
    funnel_labels = []
    funnel_values = []
    for item in dashboard_data.get("sales_funnel", []):
        # Переводим статус сразу (если есть функция перевода в сервисе) или передаем ключ
        funnel_labels.append(item['status'].value) 
        funnel_values.append(item['count'])

    context.update({
        "title": "Дашборд",
        
        # KPI
        "kpi": {
            "income": total_income,
            "expense": total_expense,
            "profit": net_profit,
            "active_projects": active_projects_count
        },
        
        # Данные для JS графиков (сериализуем в JSON)
        "chart_funnel_labels": json.dumps(funnel_labels),
        "chart_funnel_values": json.dumps(funnel_values),
        
        # Стандартные данные
        "sales_funnel": dashboard_data.get("sales_funnel", []),
        "my_tasks": dashboard_data.get("my_tasks", []),
        "new_unassigned_requests": dashboard_data.get("new_unassigned_requests", []),
        "top_managers": await crm_service.get_top_managers(db),
        "htmx_request": "HX-Request" in request.headers
    })
    
    return templates.TemplateResponse("admin/dashboard.html", context)