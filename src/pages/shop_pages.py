# src/pages/shop_pages.py

import json
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional, Union

from .jinja_config import templates
from ..core.db import get_db_session
from ..services import shop_service
from ..forms.quote_forms import GeneralQuoteForm, QuoteForm

router = APIRouter(tags=["Public Website"])
root_router = APIRouter(tags=["Public Website Root"])

@root_router.get("/", response_class=HTMLResponse, name="index")
async def get_shop_index(
    request: Request,
    locale: str,
    db: AsyncSession = Depends(get_db_session)
):
    categories = await shop_service.get_categories_with_active_products(db)
    form = GeneralQuoteForm(request)
    context = {
        "request": request,
        "categories_with_products": categories,
        "form": form,
        "current_year": datetime.now().year,
    }
    return templates.TemplateResponse("shop/index.html", context)

# --- Редиректы старых страниц на главную (для SEO) ---
@router.get("/products", response_class=HTMLResponse, name="products")
async def get_products_page(
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
        t_get = templates.env.globals.get('t_get')
        subject_text = t_get(request, product, 'name') if product else "Заявка с сайта"
        
        result = await shop_service.process_quote_request(
            db=db, 
            name=form.name.data, 
            phone=form.phone.data, 
            message=form.message.data or "",
            subject=subject_text, 
            source="website"
        )
        
        if result == "duplicate":
            context = {"request": request, "product": product, "form": form}
            response = templates.TemplateResponse("shop/partials/_quote_form.html", context, status_code=422)
            response.headers["HX-Trigger-After-Swap"] = json.dumps({"show-toast": {"message": "Вы недавно уже отправляли заявку. Мы скоро с вами свяжемся!", "type": "warning"}})
            return response

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
        _ = templates.env.globals.get('_')
        subject_text = _({'request': request}, 'general_request_option')

        result = await shop_service.process_quote_request(
            db=db, 
            name=form.name.data, 
            phone=form.phone.data, 
            message=form.message.data,
            subject=subject_text,
            source="contact_form"
        )
        
        if result == "duplicate":
            context = {"request": request, "form": form}
            response = templates.TemplateResponse("shop/partials/_general_quote_form.html", context, status_code=422)
            response.headers["HX-Trigger-After-Swap"] = json.dumps({"show-toast": {"message": "Вы недавно уже отправляли заявку!", "type": "warning"}})
            return response

        response = templates.TemplateResponse("shop/partials/_quote_success.html", {"request": request, "product": None})
        response.headers["HX-Trigger-After-Swap"] = json.dumps({"new-quote-request": True})
        return response
    else:
        context = {"request": request, "form": form}
        return templates.TemplateResponse("shop/partials/_general_quote_form.html", context, status_code=422)