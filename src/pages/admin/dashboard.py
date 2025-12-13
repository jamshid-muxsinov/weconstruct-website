import json
from collections import defaultdict
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, desc

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
    
    # 1. KPI: Общие цифры (Сумма всех времен)
    finance_stmt = select(
        func.sum(case((Transaction.type == Transaction.TypeEnum.INCOME, Transaction.amount), else_=0)),
        func.sum(case((Transaction.type == Transaction.TypeEnum.EXPENSE, Transaction.amount), else_=0))
    )
    finance_result = await db.execute(finance_stmt)
    total_income, total_expense = finance_result.one()
    total_income = float(total_income or 0)
    total_expense = float(total_expense or 0)
    net_profit = total_income - total_expense

    # Активные проекты
    active_projects_count = await db.scalar(
        select(func.count(Project.id)).where(Project.status == Project.StatusEnum.CONSTRUCTION)
    ) or 0

    # 2. ГРАФИК ФИНАНСОВ (По месяцам)
    # Берем все транзакции
    trans_stmt = select(Transaction).order_by(Transaction.created_at)
    transactions = (await db.execute(trans_stmt)).scalars().all()

    # Группируем в Python (проще и надежнее, чем сложный SQL для разных БД)
    monthly_stats = defaultdict(lambda: {'income': 0, 'expense': 0})
    
    for t in transactions:
        # Ключ: "2023-10" (Год-Месяц)
        month_key = t.created_at.strftime('%Y-%m')
        if t.type == Transaction.TypeEnum.INCOME:
            monthly_stats[month_key]['income'] += float(t.amount)
        else:
            monthly_stats[month_key]['expense'] += float(t.amount)

    # Сортируем месяцы и разделяем на списки для графика
    sorted_months = sorted(monthly_stats.keys())
    # Если данных нет, покажем пустой график с текущим месяцем
    if not sorted_months:
        sorted_months = [datetime.now().strftime('%Y-%m')]

    chart_labels = [] # Ось X: ["Oct", "Nov", "Dec"]
    chart_income = [] # Данные: [100, 200, 0]
    chart_expense = [] # Данные: [50, 20, 10]

    for m in sorted_months:
        # Превращаем "2025-12" в "Dec 25" для красоты
        dt = datetime.strptime(m, '%Y-%m')
        chart_labels.append(dt.strftime('%b %y'))
        
        chart_income.append(monthly_stats[m]['income'])
        chart_expense.append(monthly_stats[m]['expense'])

    # 3. ГРАФИК ВОРОНКИ
    dashboard_data = await crm_service.get_dashboard_data(db, user.id)
    funnel_labels = []
    funnel_values = []
    for item in dashboard_data.get("sales_funnel", []):
        funnel_labels.append(item['display_name']) # Используем уже переведенное имя из сервиса
        funnel_values.append(item['count'])

    context.update({
        "title": "Дашборд",
        
        "kpi": {
            "income": total_income,
            "expense": total_expense,
            "profit": net_profit,
            "active_projects": active_projects_count
        },
        
        # Данные для Графика Финансов
        "chart_finance_labels": json.dumps(chart_labels),
        "chart_finance_income": json.dumps(chart_income),
        "chart_finance_expense": json.dumps(chart_expense),

        # Данные для Графика Воронки
        "chart_funnel_labels": json.dumps(funnel_labels),
        "chart_funnel_values": json.dumps(funnel_values),
        
        # Списки
        "sales_funnel": dashboard_data.get("sales_funnel", []),
        "new_unassigned_requests": dashboard_data.get("new_unassigned_requests", []),
        "top_managers": await crm_service.get_top_managers(db),
        "htmx_request": "HX-Request" in request.headers
    })
    
    return templates.TemplateResponse("admin/dashboard.html", context)