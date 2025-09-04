import os
import uuid
import json
import csv
import io
import re
import logging
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse
from urllib.parse import quote
from pathlib import Path
from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, func, distinct
from sqlalchemy.orm import joinedload, selectinload
from slugify import slugify
import wtforms
from typing import Optional, List
from datetime import datetime
from src.pages.jinja_config import templates
from src.core.db import get_db_session
from src.models.shop_models import User, Product, Category, QuoteRequest, Contact, RegistrationInvite, ProductImage, Task, Notification
from src.core.security import get_current_active_user
from .dependencies import get_common_context
from src.services import user_service, shop_service
from sqlalchemy.exc import IntegrityError
from fastapi_pagination import Params, Page
from fastapi_pagination.api import create_page
from sqlalchemy.dialects import postgresql

router = APIRouter()
log = logging.getLogger(__name__)

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

class ProductForm(wtforms.Form):
    name_ru = wtforms.StringField('Название (RU)', validators=[wtforms.validators.DataRequired()])
    short_description_ru = wtforms.TextAreaField('Краткое описание (RU)', render_kw={"rows": 3})
    full_description_ru = wtforms.TextAreaField('Полное описание (RU)', render_kw={"rows": 10})
    dimensions_ru = wtforms.StringField('Размеры (RU)')
    materials_ru = wtforms.TextAreaField('Материалы (RU)', render_kw={"rows": 6}, description="Каждый материал с новой строки")
    name_uz = wtforms.StringField('Название (UZ)')
    short_description_uz = wtforms.TextAreaField('Краткое описание (UZ)', render_kw={"rows": 3})
    full_description_uz = wtforms.TextAreaField('Полное описание (UZ)', render_kw={"rows": 10})
    dimensions_uz = wtforms.StringField("O'lchamlari (UZ)")
    materials_uz = wtforms.TextAreaField("Materiallar (UZ)", render_kw={"rows": 6}, description="Har bir material yangi qatordan")
    price_min = wtforms.DecimalField('Цена за м² от (сум)', places=0, validators=[wtforms.validators.Optional()])
    price_max = wtforms.DecimalField('Цена за м² до (сум)', places=0, validators=[wtforms.validators.Optional()])
    category_id = wtforms.SelectField('Категория', coerce=int, validators=[wtforms.validators.DataRequired()])
    is_active = wtforms.BooleanField('Активен', default=True, description="Виден на сайте")
    main_image = wtforms.FileField('Основное изображение')
    images = wtforms.MultipleFileField('Дополнительные изображения')

class CategoryForm(wtforms.Form):
    name_ru = wtforms.StringField('Название (RU)', validators=[wtforms.validators.DataRequired()])
    description_ru = wtforms.TextAreaField('Описание (RU)', render_kw={"rows": 4})
    name_uz = wtforms.StringField('Название (UZ)')
    description_uz = wtforms.TextAreaField('Описание (UZ)', render_kw={"rows": 4})

class QuoteRequestForm(wtforms.Form):
    contact_id = wtforms.HiddenField('Контакт', validators=[wtforms.validators.Optional()])
    new_contact_name = wtforms.StringField('Имя и Фамилия нового клиента', validators=[wtforms.validators.Optional()])
    new_contact_phone = wtforms.StringField('Телефон нового клиента', validators=[wtforms.validators.Optional()])
    product_id = wtforms.SelectField('Товар (необязательно)', coerce=int, validators=[wtforms.validators.Optional()])
    message = wtforms.TextAreaField('Сообщение клиента', render_kw={"rows": 4})
    status = wtforms.SelectField('Статус', choices=[(s.value, s.name.replace('_', ' ').capitalize()) for s in QuoteRequest.StatusEnum], default=QuoteRequest.StatusEnum.IMPORTED.value)
    assigned_to_id = wtforms.SelectField('Ответственный', coerce=int, validators=[wtforms.validators.Optional()])
    business_type = wtforms.StringField('Тип бизнеса клиента', validators=[wtforms.validators.Optional()])
    dimensions = wtforms.StringField('Предполагаемые размеры объекта', validators=[wtforms.validators.Optional()])
    investment_details = wtforms.TextAreaField('Бюджет и детали (Sarmoysi)', render_kw={"rows": 4}, validators=[wtforms.validators.Optional()])
    conclusion = wtforms.TextAreaField('Выводы менеджера (Xulosasi)', render_kw={"rows": 4}, validators=[wtforms.validators.Optional()])
    additional_info = wtforms.TextAreaField('Дополнительные сведения', render_kw={"rows": 4}, validators=[wtforms.validators.Optional()])
    
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

Product.__str__ = lambda self: self.name_ru
Category.__str__ = lambda self: self.name_ru
QuoteRequest.__str__ = lambda self: f"Заявка #{self.id}"

PRODUCT_META = Meta(Product, ['name_ru', 'category', 'price_min', 'is_active'], ProductForm, "Товар", "Товары")
CATEGORY_META = Meta(Category, ['name_ru', 'description_ru'], CategoryForm, "Категория", "Категории")
QUOTEREQUEST_META = Meta(QuoteRequest, ['name', 'phone', 'product', 'status', 'source'], QuoteRequestForm, "Заявка", "Заявки")

def sanitize_for_csv(value):
    if value is None:
        return ""
    text = str(value).replace('\n', ' ').replace('\r', ' ').strip()
    if re.match(r'^\d{1,2}[./-]\d{1,2}$', text):
        return f'="{text}"'
    return text

@router.get("/quoterequest/export/", name="admin_quoterequest_export")
async def quoterequest_export(request: Request, ids: Optional[str] = None, db: AsyncSession = Depends(get_db_session)):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
    headers = ["ID", "Дата", "Статус", "Клиент", "Телефон", "Сообщение", "Тип бизнеса", "Размеры", "Бюджет/Детали", "Выводы", "Доп. сведения"]
    writer.writerow(headers)
    query = select(QuoteRequest).options(joinedload(QuoteRequest.contact), joinedload(QuoteRequest.product), joinedload(QuoteRequest.assigned_to)).order_by(QuoteRequest.id.desc())
    if ids:
        try:
            selected_ids = [int(id_str) for id_str in ids.split(',')]
            query = query.where(QuoteRequest.id.in_(selected_ids))
        except (ValueError, TypeError): pass
    result = await db.execute(query)
    requests_to_export = result.scalars().all()
    for req in requests_to_export:
        writer.writerow([sanitize_for_csv(v) for v in [req.id, req.created_at.strftime('%d.%m.%Y %H:%M'), req.get_status_display(), req.contact.full_name if req.contact else "", req.contact.phone if req.contact else "", req.message, req.business_type, req.dimensions, req.investment_details, req.conclusion, req.additional_info]])
    output.seek(0)
    BOM = b'\xef\xbb\xbf'
    content_bytes = BOM + output.getvalue().encode('utf-8')
    return StreamingResponse(iter([content_bytes]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=weconstruct_requests_{datetime.now().strftime('%Y-%m-%d')}.csv"})

def set_hx_trigger_header(response: Response, message: str, type: str = "success"):
    payload = json.dumps({"show-toast": {"message": message, "type": type}})
    response.headers["HX-Trigger"] = quote(payload)
    return response

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
    count_query = select(func.count(distinct(meta.model.id)))

    if meta.model == Product:
        items_query = items_query.options(selectinload(Product.category))

    if meta.model == QuoteRequest:
        if search_query:
            search_like = f"%{search_query}%"
            filter_condition = or_(func.concat(Contact.name, ' ', Contact.last_name).ilike(search_like), Contact.phone.ilike(search_like))
            items_query = items_query.join(Contact).where(filter_condition)
            count_query = count_query.join(Contact).where(filter_condition)
        try:
            if date_from:
                start_date = datetime.strptime(date_from, "%Y-%m-%d")
                items_query = items_query.where(QuoteRequest.created_at >= start_date)
                count_query = count_query.where(QuoteRequest.created_at >= start_date)
            if date_to:
                end_date = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                items_query = items_query.where(QuoteRequest.created_at <= end_date)
                count_query = count_query.where(QuoteRequest.created_at <= end_date)
        except ValueError: pass
    elif meta.model == Product:
        if search_query:
            search_like = f"%{search_query}%"
            items_query = items_query.where(Product.name_ru.ilike(search_like))
            count_query = count_query.where(Product.name_ru.ilike(search_like))
    elif meta.model == Category:
        if search_query:
            search_like = f"%{search_query}%"
            items_query = items_query.where(Category.name_ru.ilike(search_like))
            count_query = count_query.where(Category.name_ru.ilike(search_like))
    total_result = await db.execute(count_query)
    total = total_result.scalar_one_or_none() or 0
    
    log.info(f"Manual count for {meta.model_name} found {total} items.")
    
    if meta.model == QuoteRequest:
        items_query = items_query.options(
            selectinload(QuoteRequest.contact), 
            selectinload(QuoteRequest.product),
            selectinload(QuoteRequest.assigned_to)
        )
        if sort == 'asc':
            items_query = items_query.order_by(QuoteRequest.created_at.asc())
        else:
            items_query = items_query.order_by(QuoteRequest.created_at.desc())
    else:
        items_query = items_query.order_by(getattr(meta.model, 'id').desc())

    paginated_items_query = items_query.offset((page - 1) * size).limit(size)
    
    items_result = await db.execute(paginated_items_query)
    items = items_result.scalars().unique().all()
    
    params = Params(page=page, size=size)
    return create_page(items, total, params)

@router.get("/quoterequest/", response_class=HTMLResponse, name="admin_quoterequest_list")
async def quoterequest_list(request: Request, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), q: Optional[str] = Query(None), sort: Optional[str] = Query(None), date_from: Optional[str] = Query(None), date_to: Optional[str] = Query(None), context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    page_obj = await handle_list_view(db, QUOTEREQUEST_META, page=page, size=size, search_query=q, sort=sort, date_from=date_from, date_to=date_to)
    context.update({"meta": QUOTEREQUEST_META, "page": page_obj, "list_display": QUOTEREQUEST_META.list_display, "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/generic_list.html", context)

async def populate_request_form_choices(db: AsyncSession, form: QuoteRequestForm):
    products = (await db.execute(select(Product).order_by(Product.name_ru))).scalars().all()
    form.product_id.choices = [(0, '--- Общая заявка ---')] + [(p.id, p.name_ru) for p in products]
    staff_users = (await db.execute(select(User).where(User.is_staff == True).order_by(User.username))).scalars().all()
    form.assigned_to_id.choices = [(0, '--- Не назначен ---')] + [(u.id, u.username) for u in staff_users]

@router.get("/product/", response_class=HTMLResponse, name="admin_product_list")
async def product_list(request: Request, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), q: Optional[str] = Query(None), context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    page_obj = await handle_list_view(db, PRODUCT_META, page=page, size=size, search_query=q)
    context.update({"meta": PRODUCT_META, "page": page_obj, "list_display": PRODUCT_META.list_display, "htmx_request": "HX-Request" in request.headers})
    return templates.TemplateResponse("admin/generic_list.html", context)
    
@router.get("/product/add/", response_class=HTMLResponse, name="admin_product_add")
@router.get("/product/{pk}/change/", response_class=HTMLResponse, name="admin_product_change")
async def product_form_get(request: Request, pk: Optional[int] = None, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    if pk:
        stmt = select(Product).where(Product.id == pk).options(selectinload(Product.images)); instance = (await db.execute(stmt)).scalars().first()
        if not instance: raise HTTPException(404)
    else: instance = None
    form = PRODUCT_META.form_class(obj=instance); cats = (await db.execute(select(Category).order_by(Category.name_ru))).scalars().all(); form.category_id.choices = [(c.id, c.name_ru) for c in cats]; context.update({"meta": PRODUCT_META, "original": instance, "form": form, "htmx_request": "HX-Request" in request.headers}); return templates.TemplateResponse("admin/generic_form.html", context)
@router.post("/product/add/", response_class=HTMLResponse)
@router.post("/product/{pk}/change/", response_class=HTMLResponse)
async def product_form_post(request: Request, pk: Optional[int] = None, main_image: UploadFile = File(None), images: List[UploadFile] = File([]), context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    if pk:
        stmt = select(Product).where(Product.id == pk).options(selectinload(Product.images)); instance = (await db.execute(stmt)).scalars().first()
        if not instance: raise HTTPException(404)
    else: instance = None
    form_data = await request.form(); form = PRODUCT_META.form_class(form_data, obj=instance); cats = (await db.execute(select(Category).order_by(Category.name_ru))).scalars().all(); form.category_id.choices = [(c.id, c.name_ru) for c in cats]
    if form.validate():
        instance = instance or Product(); form_field_names = list(form._fields.keys()); form_field_names.remove('main_image'); form_field_names.remove('images');
        for name in form_field_names: setattr(instance, name, form[name].data)
        instance.slug = slugify(instance.name_ru); products_media_dir = Path("media/products"); os.makedirs(products_media_dir, exist_ok=True)
        if main_image and main_image.filename:
            if instance.main_image:
                old_file_path = Path("media") / instance.main_image
                if old_file_path.exists(): os.remove(old_file_path)
            file_path_relative = f"products/{uuid.uuid4()}_{main_image.filename}"; full_file_path = products_media_dir / file_path_relative.split('/')[-1]
            with open(full_file_path, "wb") as buffer: buffer.write(await main_image.read())
            instance.main_image = file_path_relative
        db.add(instance); await db.flush()
        for image_file in images:
            if image_file and image_file.filename:
                file_path_relative = f"products/{uuid.uuid4()}_{image_file.filename}"; full_file_path = products_media_dir / file_path_relative.split('/')[-1]
                with open(full_file_path, "wb") as buffer: buffer.write(await image_file.read())
                new_image = ProductImage(product_id=instance.id, image=file_path_relative); db.add(new_image)
        await db.commit(); await db.refresh(instance); response = RedirectResponse(request.url_for(PRODUCT_META.change_url_name, pk=instance.id), status_code=303); return set_hx_trigger_header(response, "Товар успешно сохранен!")
    context.update({"meta": PRODUCT_META, "original": instance, "form": form, "htmx_request": "HX-Request" in request.headers}); return templates.TemplateResponse("admin/generic_form.html", context, status_code=422)
@router.get("/product/{pk}/delete/", response_class=HTMLResponse, name="admin_product_delete")
@router.post("/product/{pk}/delete/", response_class=HTMLResponse)
async def product_delete(request: Request, pk: int, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    product = await db.get(Product, pk);
    if not product: raise HTTPException(404)
    if request.method == "POST":
        await db.delete(product); await db.commit(); response = RedirectResponse(url=request.url_for(PRODUCT_META.list_url_name), status_code=303); return set_hx_trigger_header(response, "Товар удален", "error")
    context.update({"meta": PRODUCT_META, "original": product, "back_url": request.url_for(PRODUCT_META.change_url_name, pk=pk), "htmx_request": "HX-Request" in request.headers}); return templates.TemplateResponse("admin/delete_confirmation.html", context)
@router.get("/category/", response_class=HTMLResponse, name="admin_category_list")
async def category_list(request: Request, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), q: Optional[str] = Query(None), context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    page_obj = await handle_list_view(db, CATEGORY_META, page=page, size=size, search_query=q); context.update({"meta": CATEGORY_META, "page": page_obj, "list_display": ['name_ru', 'description_ru'], "search_query": q, "htmx_request": "HX-Request" in request.headers});
    return templates.TemplateResponse("admin/generic_list.html", context)
@router.get("/category/add/", response_class=HTMLResponse, name="admin_category_add")
@router.get("/category/{pk}/change/", response_class=HTMLResponse, name="admin_category_change")
async def category_form_get(request: Request, pk: Optional[int] = None, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    instance = await db.get(Category, pk) if pk else None;
    if pk and not instance: raise HTTPException(404)
    form = CATEGORY_META.form_class(obj=instance); context.update({"meta": CATEGORY_META, "original": instance, "form": form, "htmx_request": "HX-Request" in request.headers}); return templates.TemplateResponse("admin/generic_form.html", context)
@router.post("/category/add/", response_class=HTMLResponse)
@router.post("/category/{pk}/change/", response_class=HTMLResponse)
async def category_form_post(request: Request, pk: Optional[int] = None, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    instance = await db.get(Category, pk) if pk else None;
    if pk and not instance: raise HTTPException(404)
    form_data = await request.form(); form = CATEGORY_META.form_class(form_data, obj=instance)
    if form.validate():
        instance = instance or Category(); form.populate_obj(instance); instance.slug = slugify(instance.name_ru); db.add(instance); await db.commit(); await db.refresh(instance); response = RedirectResponse(request.url_for(CATEGORY_META.change_url_name, pk=instance.id), status_code=303); return set_hx_trigger_header(response, "Категория сохранена!")
    context.update({"meta": CATEGORY_META, "original": instance, "form": form, "htmx_request": "HX-Request" in request.headers}); return templates.TemplateResponse("admin/generic_form.html", context)
@router.get("/category/{pk}/delete/", response_class=HTMLResponse, name="admin_category_delete")
@router.post("/category/{pk}/delete/", response_class=HTMLResponse)
async def category_delete(request: Request, pk: int, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    category = await db.get(Category, pk);
    if not category: raise HTTPException(404)
    if request.method == "POST":
        try:
            await db.delete(category); await db.commit(); response = RedirectResponse(url=request.url_for(CATEGORY_META.list_url_name), status_code=303); return set_hx_trigger_header(response, "Категория удалена", "error")
        except IntegrityError:
            await db.rollback(); context.update({"error_message": "Нельзя удалить категорию, к которой привязаны товары. Сначала измените категорию у этих товаров или удалите их."}); return templates.TemplateResponse("admin/500.html", context, status_code=500)
    context.update({"meta": CATEGORY_META, "original": category, "back_url": request.url_for(CATEGORY_META.change_url_name, pk=pk), "htmx_request": "HX-Request" in request.headers}); return templates.TemplateResponse("admin/delete_confirmation.html", context)
@router.get("/quoterequest/add/", response_class=HTMLResponse, name="admin_quoterequest_add")
async def quoterequest_form_get_add(request: Request, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    form = QUOTEREQUEST_META.form_class(); await populate_request_form_choices(db, form); context.update({"meta": QUOTEREQUEST_META, "original": None, "form": form, "title": "Добавить заявку", "htmx_request": "HX-Request" in request.headers}); return templates.TemplateResponse("admin/quoterequest_form.html", context)
@router.post("/quoterequest/add/", response_class=HTMLResponse)
async def quoterequest_form_post_add(request: Request, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    form_data = await request.form(); form = QUOTEREQUEST_META.form_class(form_data); await populate_request_form_choices(db, form)
    if form.validate():
        contact_id = int(form.contact_id.data) if form.contact_id.data else None; new_quote_request = None
        if not contact_id:
            contact = await shop_service._get_or_create_contact(db, form.new_contact_name.data, form.new_contact_phone.data); await db.flush(); new_quote_request = await shop_service._create_quote_request(db, contact.id, form.message.data, form.product_id.data if form.product_id.data else None, "contact_form")
        else: new_quote_request = QuoteRequest(contact_id=contact_id, product_id=form.product_id.data if form.product_id.data else None, message=form.message.data, status=form.status.data, source=QuoteRequest.SourceEnum.CONTACT_FORM)
        if new_quote_request:
            new_quote_request.assigned_to_id = form.assigned_to_id.data if form.assigned_to_id.data else None; new_quote_request.business_type = form.business_type.data; new_quote_request.dimensions = form.dimensions.data; new_quote_request.investment_details = form.investment_details.data; new_quote_request.conclusion = form.conclusion.data; new_quote_request.additional_info = form.additional_info.data; db.add(new_quote_request); await db.flush()
            if not contact_id: await shop_service._notify_managers(db, new_quote_request, contact.full_name)
        await db.commit(); response = RedirectResponse(request.url_for(QUOTEREQUEST_META.list_url_name), status_code=303); return set_hx_trigger_header(response, "Заявка успешно создана!")
    context.update({"meta": QUOTEREQUEST_META, "original": None, "form": form, "title": "Добавить заявку", "htmx_request": "HX-Request" in request.headers}); return templates.TemplateResponse("admin/quoterequest_form.html", context, status_code=422)
@router.get("/quoterequest/{pk}/change/", response_class=HTMLResponse, name="admin_quoterequest_change")
async def quoterequest_change_form_get(request: Request, pk: int, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    quote = await db.get(QuoteRequest, pk, options=[joinedload(QuoteRequest.contact)]);
    if not quote: raise HTTPException(404)
    form = QUOTEREQUEST_META.form_class(obj=quote); form.contact_id.data = quote.contact_id; await populate_request_form_choices(db, form); context.update({"meta": QUOTEREQUEST_META, "original": quote, "form": form, "title": f"Редактирование заявки #{pk}", "htmx_request": "HX-Request" in request.headers}); return templates.TemplateResponse("admin/quoterequest_form.html", context)
@router.post("/quoterequest/{pk}/change/", response_class=HTMLResponse)
async def quoterequest_change_form_post(request: Request, pk: int, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    quote = await db.get(QuoteRequest, pk, options=[joinedload(QuoteRequest.contact)]);
    if not quote: raise HTTPException(404)
    form_data = await request.form(); form = QUOTEREQUEST_META.form_class(form_data, obj=quote); await populate_request_form_choices(db, form)
    if form.validate():
        quote.product_id = form.product_id.data if form.product_id.data else None; quote.message = form.message.data; quote.status = form.status.data; quote.assigned_to_id = form.assigned_to_id.data if form.assigned_to_id.data else None; quote.business_type = form.business_type.data; quote.dimensions = form.dimensions.data; quote.investment_details = form.investment_details.data; quote.conclusion = form.conclusion.data; quote.additional_info = form.additional_info.data; db.add(quote); await db.commit(); response = RedirectResponse(request.url_for(QUOTEREQUEST_META.change_url_name, pk=pk), status_code=303); return set_hx_trigger_header(response, "Заявка успешно сохранена!")
    context.update({"meta": QUOTEREQUEST_META, "original": quote, "form": form, "title": f"Редактирование заявки #{pk}", "htmx_request": "HX-Request" in request.headers}); return templates.TemplateResponse("admin/quoterequest_form.html", context, status_code=422)
@router.get("/quoterequest/{pk}/delete/", response_class=HTMLResponse, name="admin_quoterequest_delete")
@router.post("/quoterequest/{pk}/delete/", response_class=Response)
async def quoterequest_delete(request: Request, pk: int, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    quote_req = await db.get(QuoteRequest, pk, options=[selectinload(QuoteRequest.tasks)]);
    if not quote_req: raise HTTPException(404, detail="QuoteRequest not found")
    if request.method == "POST":
        try:
            await db.delete(quote_req); await db.commit(); response = Response(status_code=200, content="Заявка удалена"); redirect_url = request.url_for(QUOTEREQUEST_META.list_url_name); trigger_payload = {"show-toast": {"message": "Заявка удалена", "type": "error"}, "updateKanban": True, "new-quote-request": True}; response.headers["HX-Redirect"] = str(redirect_url); response.headers["HX-Trigger"] = json.dumps(trigger_payload); return response
        except IntegrityError:
            await db.rollback(); context.update({"error_message": "Не удалось удалить заявку из-за связанных записей."}); return templates.TemplateResponse("admin/500.html", context, status_code=500)
    back_url = request.headers.get("referer", request.url_for(QUOTEREQUEST_META.list_url_name)); context.update({"meta": QUOTEREQUEST_META, "original": quote_req, "title": f"Удалить {QUOTEREQUEST_META.verbose_name}", "back_url": back_url, "htmx_request": "HX-Request" in request.headers}); return templates.TemplateResponse("admin/delete_confirmation.html", context)
class InviteForm(wtforms.Form):
    note = wtforms.StringField('Заметка (для кого это приглашение)', validators=[wtforms.validators.DataRequired()])
@router.get("/invites/", response_class=HTMLResponse, name="admin_invites")
async def invites_page_get(request: Request, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    invites = (await db.execute(select(RegistrationInvite).order_by(RegistrationInvite.created_at.desc()))).scalars().all(); form = InviteForm(); context.update({"title": "Управление приглашениями", "invites": invites, "form": form, "htmx_request": "HX-Request" in request.headers}); return templates.TemplateResponse("admin/invites.html", context)
@router.post("/invites/", response_class=HTMLResponse)
async def invites_page_post(request: Request, context: dict = Depends(get_common_context), db: AsyncSession = Depends(get_db_session)):
    form_data = await request.form(); form = InviteForm(form_data)
    if form.validate():
        await user_service.create_invite(db, form.note.data, context["user"].id); response = RedirectResponse(request.url_for("admin_invites"), status_code=303); return set_hx_trigger_header(response, "Приглашение успешно создано!")
    invites = (await db.execute(select(RegistrationInvite).order_by(RegistrationInvite.created_at.desc()))).scalars().all(); context.update({"title": "Управление приглашениями", "invites": invites, "form": form, "htmx_request": "HX-Request" in request.headers}); return templates.TemplateResponse("admin/invites.html", context)