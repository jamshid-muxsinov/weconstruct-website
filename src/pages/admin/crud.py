import os
import uuid
import json
import logging
from fastapi.responses import Response, HTMLResponse, RedirectResponse
from urllib.parse import quote
from pathlib import Path
from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, func, distinct, update
from sqlalchemy.orm import joinedload, selectinload
from slugify import slugify
import wtforms
from typing import Optional, List
from datetime import datetime

from src.pages.jinja_config import templates
from src.core.db import get_db_session
# --- ИСПРАВЛЕНИЕ: Возвращаем импорты ---
from src.models.shop_models import User, Product, Category, GoogleSheetLead, QuoteRequest, Contact, ProductImage
from src.core.security import get_current_active_user
from .dependencies import get_common_context
from sqlalchemy.exc import IntegrityError
from fastapi_pagination import Params, Page
from fastapi_pagination.api import create_page
from src.services import crm_service

# --- ИСПРАВЛЕНИЕ: Возвращаем все роутеры ---
product_router = APIRouter()
category_router = APIRouter()
quoterequest_router = APIRouter()
log = logging.getLogger(__name__)

def set_hx_trigger_header(response: Response, message_key: str, request: Request, type: str = "success"):
    translator = templates.env.globals.get('_')
    message = translator({'request': request}, message_key) if translator else message_key
    payload = json.dumps({"show-toast": {"message": message, "type": type}})
    response.headers["HX-Trigger"] = quote(payload)
    return response

class Meta:
    def __init__(self, model, list_display, form_class=None, verbose_name=None, verbose_name_plural=None):
        self.model = model
        self.verbose_name = verbose_name or model.__name__
        self.verbose_name_plural = verbose_name_plural or f"{model.__name__}s"
        self.list_display = list_display
        self.form_class = form_class
        model_name_lower = model.__name__.lower()
        self.model_name = model_name_lower
        self.list_url_name = f"admin_{model_name_lower}_list"
        self.add_url_name = f"admin_{model_name_lower}_add" if form_class else None
        self.change_url_name = f"admin_{model_name_lower}_change"
        self.delete_url_name = f"admin_{model_name_lower}_delete" if form_class else None
    def __str__(self): return self.verbose_name_plural

# --- ИСПРАВЛЕНИЕ: Возвращаем формы для Продуктов и Категорий ---
class ProductForm(wtforms.Form):
    name_ru = wtforms.StringField('form_field_name_ru', validators=[wtforms.validators.DataRequired()])
    short_description_ru = wtforms.TextAreaField('form_field_short_desc_ru', render_kw={"rows": 3})
    full_description_ru = wtforms.TextAreaField('form_field_full_desc_ru', render_kw={"rows": 10})
    dimensions_ru = wtforms.StringField('form_field_dimensions_ru')
    materials_ru = wtforms.TextAreaField('form_field_materials_ru', render_kw={"rows": 6}, description="form_materials_desc_ru")
    name_uz = wtforms.StringField('form_field_name_uz')
    short_description_uz = wtforms.TextAreaField('form_field_short_desc_uz', render_kw={"rows": 3})
    full_description_uz = wtforms.TextAreaField('form_field_full_desc_uz', render_kw={"rows": 10})
    dimensions_uz = wtforms.StringField("form_field_dimensions_uz")
    materials_uz = wtforms.TextAreaField("form_field_materials_uz", render_kw={"rows": 6}, description="form_materials_desc_uz")
    price_min = wtforms.DecimalField('form_field_price_min', places=0, validators=[wtforms.validators.Optional()])
    price_max = wtforms.DecimalField('form_field_price_max', places=0, validators=[wtforms.validators.Optional()])
    category_id = wtforms.SelectField('form_field_category', coerce=int, validators=[wtforms.validators.DataRequired()])
    is_active = wtforms.BooleanField('form_field_is_active', default=True, description="form_is_active_desc")
    main_image = wtforms.FileField('form_field_main_image')
    images = wtforms.MultipleFileField('form_field_extra_images')

class CategoryForm(wtforms.Form):
    name_ru = wtforms.StringField('form_field_name_ru', validators=[wtforms.validators.DataRequired()])
    description_ru = wtforms.TextAreaField('form_field_desc_ru', render_kw={"rows": 4})
    name_uz = wtforms.StringField('form_field_name_uz')
    description_uz = wtforms.TextAreaField('form_field_desc_uz', render_kw={"rows": 4})

# --- Форма Заявки остается упрощенной ---
class QuoteRequestForm(wtforms.Form):
    contact_id = wtforms.HiddenField('form_field_contact', validators=[wtforms.validators.Optional()])
    new_contact_name = wtforms.StringField('form_field_new_contact_name', validators=[wtforms.validators.Optional()])
    new_contact_phone = wtforms.StringField('form_field_new_contact_phone', validators=[wtforms.validators.Optional()])
    
    subject = wtforms.StringField(
        'Тема обращения', 
        validators=[wtforms.validators.DataRequired(message="Укажите тему обращения.")],
        render_kw={"placeholder": "Например, 'Холодный звонок по базе X'"}
    )
    
    message = wtforms.TextAreaField('form_field_message', render_kw={"rows": 4})
    status = wtforms.SelectField('form_field_status', choices=[(s.value, s.name.replace('_', ' ').capitalize()) for s in QuoteRequest.StatusEnum], default=QuoteRequest.StatusEnum.IMPORTED.value)
    assigned_to_id = wtforms.SelectField('form_field_assignee', coerce=int, validators=[wtforms.validators.Optional()])
    business_type = wtforms.StringField('form_field_business_type', validators=[wtforms.validators.Optional()])
    dimensions = wtforms.StringField('form_field_dimensions', validators=[wtforms.validators.Optional()])
    investment_details = wtforms.TextAreaField('form_field_investment', render_kw={"rows": 4}, validators=[wtforms.validators.Optional()])
    conclusion = wtforms.TextAreaField('form_field_conclusion', render_kw={"rows": 4}, validators=[wtforms.validators.Optional()])
    additional_info = wtforms.TextAreaField('form_field_additional_info', render_kw={"rows": 4}, validators=[wtforms.validators.Optional()])
    
    def validate(self, extra_validators=None):
        rv = super().validate(extra_validators)
        if not rv: return False
        contact_id_data = int(self.contact_id.data) if self.contact_id.data else None
        
        if not contact_id_data and not (self.new_contact_name.data and self.new_contact_phone.data):
            self.contact_id.errors.append('Необходимо выбрать существующего клиента или создать нового.')
            return False
        if contact_id_data and (self.new_contact_name.data or self.new_contact_phone.data):
            self.contact_id.errors.append('Нельзя одновременно выбирать существующего клиента и создавать нового.')
            return False
        return True

# --- ИСПРАВЛЕНИЕ: Возвращаем все META ---
Product.__str__ = lambda self: self.name_ru
Category.__str__ = lambda self: self.name_ru
QuoteRequest.__str__ = lambda self: f"Заявка #{self.id}"
Contact.__str__ = lambda self: self.full_name

PRODUCT_META = Meta(Product, ['name_ru', 'category', 'price_min', 'is_active'], ProductForm, "product_single", "list_products")
CATEGORY_META = Meta(Category, ['name_ru', 'description_ru'], CategoryForm, "category_single", "list_categories")
QUOTEREQUEST_META = Meta(QuoteRequest, ['name', 'phone', 'subject', 'created_at', 'status', 'assigned_to'], QuoteRequestForm, "request_single", "list_requests")
CONTACT_META = Meta(Contact, ['full_name', 'phone', 'email'], None, "client_single", "list_contacts")
CONTACT_META.add_url_name = None 
CONTACT_META.delete_url_name = "admin_contact_delete"
CONTACT_META.change_url_name = "admin_contact_detail"

async def handle_list_view(
    db: AsyncSession,
    meta: Meta,
    page: int,
    size: int,
    search_query: Optional[str] = None,
    sort: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> Page:
    items_query = select(meta.model)
    count_query = select(func.count(distinct(meta.model.id))).select_from(meta.model)

    if search_query:
        search_like = f"%{search_query}%"
        if meta.model == QuoteRequest:
            items_query = items_query.join(Contact).where(or_(
                func.concat(Contact.name, ' ', Contact.last_name).ilike(search_like), 
                Contact.phone.ilike(search_like),
                QuoteRequest.subject.ilike(search_like)
            ))
            count_query = count_query.join(Contact).where(or_(
                func.concat(Contact.name, ' ', Contact.last_name).ilike(search_like), 
                Contact.phone.ilike(search_like),
                QuoteRequest.subject.ilike(search_like)
            ))
        elif meta.model == Contact:
            items_query = items_query.where(or_(func.concat(Contact.name, ' ', Contact.last_name).ilike(search_like), Contact.phone.ilike(search_like), Contact.name.ilike(search_like)))
            count_query = count_query.where(or_(func.concat(Contact.name, ' ', Contact.last_name).ilike(search_like), Contact.phone.ilike(search_like), Contact.name.ilike(search_like)))
        else:
            searchable_field = getattr(meta.model, meta.list_display[0], None)
            if searchable_field:
                items_query = items_query.where(searchable_field.ilike(search_like))
                count_query = count_query.where(searchable_field.ilike(search_like))

    if meta.model == QuoteRequest:
        try:
            if date_from:
                items_query = items_query.where(QuoteRequest.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
                count_query = count_query.where(QuoteRequest.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
            if date_to:
                items_query = items_query.where(QuoteRequest.created_at <= datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59))
                count_query = count_query.where(QuoteRequest.created_at <= datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59))
        except ValueError:
            pass

    total = (await db.execute(count_query)).scalar_one_or_none() or 0
    
    if meta.model == Product: items_query = items_query.options(selectinload(Product.category))
    elif meta.model == QuoteRequest: items_query = items_query.options(selectinload(QuoteRequest.contact), selectinload(QuoteRequest.assigned_to))

    order_field = getattr(meta.model, 'id')
    items_query = items_query.order_by(order_field.asc() if sort == 'asc' else order_field.desc())
    
    items_result = await db.execute(items_query.offset((page - 1) * size).limit(size))
    items = items_result.scalars().unique().all()
    
    return create_page(items, total, Params(page=page, size=size))

async def populate_request_form_choices(db: AsyncSession, request: Request, form: QuoteRequestForm):
    _ = templates.env.globals['_']
    staff_users = (await db.execute(select(User).where(User.is_staff == True).order_by(User.username))).scalars().all()
    form.assigned_to_id.choices = [(0, _({'request': request}, 'unassigned_option'))] + [(u.id, u.username) for u in staff_users]

# --- VIEWS (LIST, ADD/CHANGE, DELETE) ---

# --- QuoteRequest Routes ---
# (Код для quoterequest_router остается таким же, как я присылал ранее)
@quoterequest_router.get("/", response_class=HTMLResponse, name="admin_quoterequest_list")
async def quoterequest_list(request: Request, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), q: Optional[str] = Query(None), sort: Optional[str] = Query(None), date_from: Optional[str] = Query(None), date_to: Optional[str] = Query(None), context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    page_obj = await handle_list_view(db, QUOTEREQUEST_META, page=page, size=size, search_query=q, sort=sort, date_from=date_from, date_to=date_to)
    context.update({"meta": QUOTEREQUEST_META, "page": page_obj, "list_display": QUOTEREQUEST_META.list_display})
    is_htmx = "HX-Request" in request.headers
    template_name = "admin/partials/_generic_list_content.html" if is_htmx else "admin/generic_list.html"
    return templates.TemplateResponse(template_name, context)

@quoterequest_router.get("/add/", response_class=HTMLResponse, name="admin_quoterequest_add")
async def quoterequest_form_get_add(request: Request, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    form = QUOTEREQUEST_META.form_class()
    await populate_request_form_choices(db, request, form)
    _ = templates.env.globals['_']
    title = f"{_({'request': request}, 'adding')}: {_({'request': request}, 'request_single')}"
    context.update({"meta": QUOTEREQUEST_META, "original": None, "form": form, "title": title, "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/quoterequest_form.html", context)

@quoterequest_router.post("/add/", response_class=HTMLResponse)
async def quoterequest_form_post_add(request: Request, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    form_data = await request.form()
    form = QUOTEREQUEST_META.form_class(form_data)
    await populate_request_form_choices(db, request, form)
    if form.validate():
        from src.services.shop_service import _get_or_create_contact
        contact_id = int(form.contact_id.data) if form.contact_id.data else None
        if not contact_id:
            contact = await _get_or_create_contact(db, form.new_contact_name.data, form.new_contact_phone.data)
            contact_id = contact.id
        quote = QuoteRequest(contact_id=contact_id)
        form.populate_obj(quote)
        
        if quote.assigned_to_id == 0:
            quote.assigned_to_id = None
            
        db.add(quote)
        await db.commit()
        response = RedirectResponse(request.url_for(QUOTEREQUEST_META.list_url_name, locale=request.state.locale), status_code=303)
        return set_hx_trigger_header(response, "request_created_success", request)
    _ = templates.env.globals['_']
    title = f"{_({'request': request}, 'adding')}: {_({'request': request}, 'request_single')}"
    context.update({"meta": QUOTEREQUEST_META, "original": None, "form": form, "title": title, "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/quoterequest_form.html", context, status_code=422)

@quoterequest_router.get("/{pk}/change/", response_class=HTMLResponse, name="admin_quoterequest_change")
async def quoterequest_change_form_get(request: Request, pk: int, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    quote = await db.get(QuoteRequest, pk, options=[joinedload(QuoteRequest.contact)])
    if not quote: raise HTTPException(404)
    form = QUOTEREQUEST_META.form_class(obj=quote)
    form.contact_id.data = quote.contact_id
    await populate_request_form_choices(db, request, form)
    _ = templates.env.globals['_']
    title = f"{_({'request': request}, 'editing')}: {_({'request': request}, 'request_single')} #{pk}"
    context.update({"meta": QUOTEREQUEST_META, "original": quote, "form": form, "title": title, "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/quoterequest_form.html", context)

@quoterequest_router.post("/{pk}/change/", response_class=HTMLResponse)
async def quoterequest_change_form_post(request: Request, pk: int, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    quote = await db.get(QuoteRequest, pk, options=[joinedload(QuoteRequest.contact)])
    if not quote: raise HTTPException(404)
    form_data = await request.form()
    form = QUOTEREQUEST_META.form_class(form_data, obj=quote)
    await populate_request_form_choices(db, request, form)
    if form.validate():
        form.populate_obj(quote)

        if quote.assigned_to_id == 0:
            quote.assigned_to_id = None
            
        db.add(quote)
        await db.commit()
        response = RedirectResponse(request.url_for(QUOTEREQUEST_META.change_url_name, locale=request.state.locale, pk=pk), status_code=303)
        return set_hx_trigger_header(response, "request_saved_success", request)
    _ = templates.env.globals['_']
    title = f"{_({'request': request}, 'editing')}: {_({'request': request}, 'request_single')} #{pk}"
    context.update({"meta": QUOTEREQUEST_META, "original": quote, "form": form, "title": title, "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/quoterequest_form.html", context, status_code=422)

@quoterequest_router.get("/{pk}/delete/", response_class=HTMLResponse, name="admin_quoterequest_delete")
@quoterequest_router.post("/{pk}/delete/", response_class=Response)
async def quoterequest_delete(request: Request, pk: int, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    quote_req = await db.get(QuoteRequest, pk, options=[selectinload(QuoteRequest.tasks)])
    if not quote_req: raise HTTPException(404, detail="QuoteRequest not found")
    
    _ = templates.env.globals['_']

    if request.method == "POST":
        try:
            await db.execute(update(GoogleSheetLead).where(GoogleSheetLead.quote_request_id == pk).values(status=GoogleSheetLead.StatusEnum.ARCHIVED))
            await db.delete(quote_req)
            await db.commit()
            
            response = Response(status_code=200)
            redirect_url = request.url_for(QUOTEREQUEST_META.list_url_name, locale=request.state.locale)
            message = _({'request': request}, "request_deleted_success")
            trigger_payload = {"show-toast": {"message": message, "type": "error"}, "updateKanban": True}
            response.headers["HX-Redirect"] = str(redirect_url)
            response.headers["HX-Trigger"] = json.dumps(trigger_payload)
            return response
        except IntegrityError:
            await db.rollback()
            context.update({"error_message": "Не удалось удалить заявку."})
            return templates.TemplateResponse("admin/500.html", context, status_code=500)
            
    back_url = request.headers.get("referer", request.url_for(QUOTEREQUEST_META.list_url_name, locale=request.state.locale))
    
    translated_entity_name = _({'request': request}, QUOTEREQUEST_META.verbose_name)
    title = _({'request': request}, 'delete_confirmation_title', entity=translated_entity_name)

    context.update({"meta": QUOTEREQUEST_META, "original": quote_req, "title": title, "back_url": back_url, "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/delete_confirmation.html", context)

@quoterequest_router.get("/export", name="admin_quoterequest_export")
async def export_requests(
    card_ids: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    ids = []
    if card_ids:
        try:
            ids = [int(id_str) for id_str in card_ids.split(',')]
        except (ValueError, TypeError):
            pass
    
    csv_content = await crm_service.export_requests_csv(db, ids)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=quote_requests.csv"}
    )

# --- ИСПРАВЛЕНИЕ: Возвращаем все роуты для Product и Category ---
# --- Product Routes ---
@product_router.get("/", response_class=HTMLResponse, name="admin_product_list")
async def product_list(request: Request, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), q: Optional[str] = Query(None), context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    page_obj = await handle_list_view(db, PRODUCT_META, page=page, size=size, search_query=q)
    context.update({"meta": PRODUCT_META, "page": page_obj, "list_display": PRODUCT_META.list_display})
    is_htmx = "HX-Request" in request.headers
    template_name = "admin/partials/_generic_list_content.html" if is_htmx else "admin/generic_list.html"
    return templates.TemplateResponse(template_name, context)

@product_router.get("/add/", response_class=HTMLResponse, name="admin_product_add")
@product_router.get("/{pk}/change/", response_class=HTMLResponse, name="admin_product_change")
async def product_form_get(request: Request, pk: Optional[int] = None, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    instance = await db.get(Product, pk, options=[selectinload(Product.images)]) if pk else None
    if pk and not instance: raise HTTPException(404)
    form = PRODUCT_META.form_class(obj=instance)
    cats = (await db.execute(select(Category).order_by(Category.name_ru))).scalars().all()
    form.category_id.choices = [(c.id, c.name_ru) for c in cats]
    context.update({"meta": PRODUCT_META, "original": instance, "form": form, "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/generic_form.html", context)



@product_router.post("/add/", response_class=HTMLResponse)
@product_router.post("/{pk}/change/", response_class=HTMLResponse)
async def product_form_post(
    request: Request,
    pk: Optional[int] = None,
    main_image: UploadFile = File(None),
    images: List[UploadFile] = File([]),
    context: dict = Depends(get_common_context),
    db: AsyncSession = Depends(get_db_session)
):
    BASE_DIR = Path("/app")

    instance = await db.get(Product, pk, options=[selectinload(Product.images)]) if pk else None
    if pk and not instance:
        raise HTTPException(404)

    form_data = await request.form()
    form = PRODUCT_META.form_class(form_data, obj=instance)

    cats = (await db.execute(select(Category).order_by(Category.name_ru))).scalars().all()
    form.category_id.choices = [(c.id, c.name_ru) for c in cats]

    del form.main_image
    del form.images

    if form.validate():
        instance = instance or Product()
        form.populate_obj(instance)
        instance.slug = slugify(instance.name_ru)

        products_media_dir = BASE_DIR / "media" / "products"
        products_media_dir.mkdir(parents=True, exist_ok=True)

        if main_image and main_image.filename:
            if instance.main_image and (BASE_DIR / "media" / instance.main_image).exists():
                try:
                    os.remove(BASE_DIR / "media" / instance.main_image)
                except OSError as e:
                    log.error(f"Не удалось удалить старый файл: {e}")

            safe_filename = slugify(os.path.splitext(main_image.filename)[0]) + os.path.splitext(main_image.filename)[1]
            
            file_path_relative = f"products/{uuid.uuid4()}_{safe_filename}"
            full_save_path = products_media_dir / file_path_relative.split('/')[-1]
            
            with open(full_save_path, "wb") as buffer:
                buffer.write(await main_image.read())
            instance.main_image = file_path_relative

        db.add(instance)
        await db.flush()

        for image_file in images:
            if image_file and image_file.filename:
                safe_filename = slugify(os.path.splitext(image_file.filename)[0]) + os.path.splitext(image_file.filename)[1]
                
                file_path_relative = f"products/{uuid.uuid4()}_{safe_filename}"
                full_save_path = products_media_dir / file_path_relative.split('/')[-1]

                with open(full_save_path, "wb") as buffer:
                    buffer.write(await image_file.read())
                db.add(ProductImage(product_id=instance.id, image=file_path_relative))

        await db.commit()
        response = RedirectResponse(request.url_for(PRODUCT_META.change_url_name, locale=request.state.locale, pk=instance.id), status_code=303)
        return set_hx_trigger_header(response, "product_saved_success", request)

    form.main_image = wtforms.FileField('form_field_main_image')
    form.images = wtforms.MultipleFileField('form_field_extra_images')

    context.update({"meta": PRODUCT_META, "original": instance, "form": form, "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/generic_form.html", context, status_code=422)

@product_router.get("/{pk}/delete/", response_class=HTMLResponse, name="admin_product_delete")
@product_router.post("/{pk}/delete/", response_class=HTMLResponse)
async def product_delete(request: Request, pk: int, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    product = await db.get(Product, pk)
    if not product: raise HTTPException(404)
    _ = templates.env.globals['_']
    if request.method == "POST":
        await db.delete(product)
        await db.commit()
        response = RedirectResponse(url=request.url_for(PRODUCT_META.list_url_name, locale=request.state.locale), status_code=303)
        return set_hx_trigger_header(response, "product_deleted_success", request, "error")
    
    translated_entity_name = _({'request': request}, PRODUCT_META.verbose_name)
    title = _({'request': request}, 'delete_confirmation_title', entity=translated_entity_name)
    
    context.update({"meta": PRODUCT_META, "original": product, "title": title, "back_url": request.url_for(PRODUCT_META.change_url_name, locale=request.state.locale, pk=pk), "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/delete_confirmation.html", context)

# --- Category Routes ---
@category_router.get("/", response_class=HTMLResponse, name="admin_category_list")
async def category_list(request: Request, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), q: Optional[str] = Query(None), context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    page_obj = await handle_list_view(db, CATEGORY_META, page=page, size=size, search_query=q)
    context.update({"meta": CATEGORY_META, "page": page_obj, "list_display": ['name_ru', 'description_ru'], "search_query": q})
    is_htmx = "HX-Request" in request.headers
    template_name = "admin/partials/_generic_list_content.html" if is_htmx else "admin/generic_list.html"
    return templates.TemplateResponse(template_name, context)

@category_router.get("/add/", response_class=HTMLResponse, name="admin_category_add")
@category_router.get("/{pk}/change/", response_class=HTMLResponse, name="admin_category_change")
async def category_form_get(request: Request, pk: Optional[int] = None, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    instance = await db.get(Category, pk) if pk else None
    if pk and not instance: raise HTTPException(404)
    form = CATEGORY_META.form_class(obj=instance)
    context.update({"meta": CATEGORY_META, "original": instance, "form": form, "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/generic_form.html", context)

@category_router.post("/add/", response_class=HTMLResponse)
@category_router.post("/{pk}/change/", response_class=HTMLResponse)
async def category_form_post(request: Request, pk: Optional[int] = None, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    instance = await db.get(Category, pk) if pk else None
    if pk and not instance: raise HTTPException(404)
    form_data = await request.form()
    form = CATEGORY_META.form_class(form_data, obj=instance)
    
    if form.validate():
        try:
            instance = instance or Category()
            form.populate_obj(instance)
            instance.slug = slugify(instance.name_ru)
            db.add(instance)
            await db.commit()
            
            response = RedirectResponse(request.url_for(CATEGORY_META.change_url_name, locale=request.state.locale, pk=instance.id), status_code=303)
            return set_hx_trigger_header(response, "category_saved_success", request)
        except IntegrityError:
            await db.rollback()
            form.name_ru.errors.append("Категория с таким названием уже существует.")

    context.update({"meta": CATEGORY_META, "original": instance, "form": form, "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/generic_form.html", context, status_code=422)

@category_router.get("/{pk}/delete/", response_class=HTMLResponse, name="admin_category_delete")
@category_router.post("/{pk}/delete/", response_class=HTMLResponse)
async def category_delete(request: Request, pk: int, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    category = await db.get(Category, pk)
    if not category: raise HTTPException(404)
    _ = templates.env.globals['_']
    if request.method == "POST":
        try:
            await db.delete(category)
            await db.commit()
            response = RedirectResponse(url=request.url_for(CATEGORY_META.list_url_name, locale=request.state.locale), status_code=303)
            return set_hx_trigger_header(response, "category_deleted_success", request, "error")
        except IntegrityError:
            await db.rollback()
            redirect_url = request.url_for(CATEGORY_META.change_url_name, locale=request.state.locale, pk=pk)
            response = RedirectResponse(url=redirect_url, status_code=303)
            message = "Нельзя удалить категорию, к которой привязаны товары."
            payload = json.dumps({"show-toast": {"message": message, "type": "error"}})
            response.headers["HX-Trigger"] = quote(payload)
            return response
    
    translated_entity_name = _({'request': request}, CATEGORY_META.verbose_name)
    title = _({'request': request}, 'delete_confirmation_title', entity=translated_entity_name)
    
    context.update({"meta": CATEGORY_META, "original": category, "title": title, "back_url": request.url_for(CATEGORY_META.change_url_name, locale=request.state.locale, pk=pk), "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/delete_confirmation.html", context)