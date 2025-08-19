import json
from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select
from datetime import datetime

from .jinja_config import templates
from ..core.db import get_db_session
from ..services import shop_service
from ..forms.quote_forms import GeneralQuoteForm, QuoteForm
from ..models.shop_models import QuoteRequest, Contact
from ..core.cache import cache_manager

router = APIRouter(tags=["Public Website"])
root_router = APIRouter(tags=["Public Website Root"])

async def publish_kanban_update(db: AsyncSession, quote_id: int, request: Request):
    """
    Находит заявку, рендерит её HTML-карточку и публикует в Redis.
    """
    if not cache_manager.is_redis_available:
        return

    # Загружаем заявку со всеми необходимыми связями для рендеринга
    stmt = (
        select(QuoteRequest).where(QuoteRequest.id == quote_id)
        .options(
            joinedload(QuoteRequest.contact).selectinload(Contact.timeline_notes),
            joinedload(QuoteRequest.product),
            joinedload(QuoteRequest.assigned_to)
        )
    )
    result = await db.execute(stmt)
    quote_to_render = result.scalars().first()
    
    if quote_to_render:
        # Рендерим HTML
        card_html = templates.TemplateResponse(
            "admin/partials/_kanban_card.html",
            {"request": request, "req": quote_to_render}
        ).body.decode("utf-8")
        
        # Публикуем готовый HTML
        await cache_manager.redis_client.publish("kanban_updates", card_html)


@root_router.get("/", response_class=HTMLResponse, name="index")
async def get_shop_index(
    request: Request,
    locale: str,
    db: AsyncSession = Depends(get_db_session)
):
    categories = await shop_service.get_categories_with_active_products(db)
    context = {
        "request": request,
        "categories_with_products": categories,
        "current_year": datetime.now().year,
    }
    return templates.TemplateResponse("shop/index.html", context)

@router.get("/about", response_class=HTMLResponse, name="about")
async def get_about_page(
    request: Request,
    locale: str
):
    context = {
        "request": request,
        "current_year": datetime.now().year,
    }
    return templates.TemplateResponse("shop/about.html", context)

@router.get("/htmx/product-modal/{product_id}", response_class=HTMLResponse, name="htmx_product_modal")
async def htmx_get_product_modal(
    product_id: int,
    request: Request,
    locale: str,
    db: AsyncSession = Depends(get_db_session)
):
    product = await shop_service.get_product_for_modal(db, product_id)
    form = QuoteForm(request)
    context = {"request": request, "product": product, "form": form}
    return templates.TemplateResponse("shop/partials/_product_modal_content.html", context)

@router.post("/htmx/request-quote/{product_id}", response_class=HTMLResponse, name="request_quote")
async def htmx_post_request_quote(
    product_id: int,
    request: Request,
    locale: str,
    db: AsyncSession = Depends(get_db_session)
):
    product = await shop_service.get_product_for_modal(db, product_id)
    form = await QuoteForm.from_formdata(request)

    if await form.validate_on_submit():
        new_quote = await shop_service.process_quote_request(
            db=db, 
            name=form.name.data, 
            phone=form.phone.data, 
            message=form.message.data or "",
            product_id=product_id, 
            source="website"
        )
        await publish_kanban_update(db, new_quote.id, request)
        
        response = templates.TemplateResponse("shop/partials/_quote_success.html", {"request": request, "product": product})
        response.headers["HX-Trigger-After-Swap"] = json.dumps({"new-quote-request": True})
        return response
    else:
        context = {"request": request, "product": product, "form": form}
        return templates.TemplateResponse("shop/partials/_quote_form.html", context, status_code=422)

@router.get("/htmx/general-quote-form", response_class=HTMLResponse, name="htmx_general_quote_form")
async def htmx_get_general_quote_form(
    request: Request,
    locale: str
):
    form = GeneralQuoteForm(request)
    context = {"request": request, "form": form}
    return templates.TemplateResponse("shop/partials/_general_quote_modal_content.html", context)

@router.post("/htmx/request-general-quote", response_class=HTMLResponse, name="request_general_quote")
async def htmx_post_general_quote(
    request: Request,
    locale: str,
    db: AsyncSession = Depends(get_db_session)
):
    form = await GeneralQuoteForm.from_formdata(request)
    
    if await form.validate_on_submit():
        new_quote = await shop_service.process_quote_request(
            db=db, 
            name=form.name.data, 
            phone=form.phone.data, 
            message=form.message.data,
            product_id=None, 
            source="contact_form"
        )
        await publish_kanban_update(db, new_quote.id, request)
        
        response = templates.TemplateResponse("shop/partials/_quote_success.html", {"request": request, "product": None})
        response.headers["HX-Trigger-After-Swap"] = json.dumps({"new-quote-request": True})
        return response
    else:
        context = {"request": request, "form": form}
        return templates.TemplateResponse("shop/partials/_general_quote_form.html", context, status_code=422)