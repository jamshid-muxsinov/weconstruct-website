import uuid
import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    String, Text, Boolean, DateTime, func, DECIMAL,
    ForeignKey, Integer, UUID, Enum as EnumType
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

class User(Base):
    __tablename__ = "auth_user"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(150))
    last_name: Mapped[Optional[str]] = mapped_column(String(150))
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    
    tasks: Mapped[List["Task"]] = relationship(back_populates="assigned_to")
    assigned_requests: Mapped[List["QuoteRequest"]] = relationship(back_populates="assigned_to")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="user")
    status_logs: Mapped[List["StatusChangeLog"]] = relationship(back_populates="user")
    invites_sent: Mapped[List["RegistrationInvite"]] = relationship(back_populates="created_by")
    contact_notes: Mapped[List["ContactNote"]] = relationship(back_populates="user")

class Contact(Base):
    __tablename__ = 'shop_contact'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), comment="Имя клиента")
    last_name: Mapped[Optional[str]] = mapped_column(String(100), comment="Фамилия клиента")
    
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(100))
    company: Mapped[Optional[str]] = mapped_column(String(150))
    notes: Mapped[Optional[str]] = mapped_column(Text, comment="Старые заметки")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    requests: Mapped[List["QuoteRequest"]] = relationship(back_populates="contact")
    tasks: Mapped[List["Task"]] = relationship(back_populates="contact")
    timeline_notes: Mapped[List["ContactNote"]] = relationship(back_populates="contact", cascade="all, delete-orphan", order_by="desc(ContactNote.created_at)")

    @property
    def full_name(self) -> str:
        return f"{self.name or ''} {self.last_name or ''}".strip()

    @property
    def pinned_note(self) -> Optional["ContactNote"]:
        for note in self.timeline_notes:
            if note.is_pinned:
                return note
        return None

class ContactNote(Base):
    __tablename__ = 'shop_contactnote'
    id: Mapped[int] = mapped_column(primary_key=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    
    contact_id: Mapped[int] = mapped_column(ForeignKey("shop_contact.id", ondelete="CASCADE"))
    contact: Mapped["Contact"] = relationship(back_populates="timeline_notes")
    
    user_id: Mapped[int] = mapped_column(ForeignKey("auth_user.id", ondelete="CASCADE"))
    user: Mapped["User"] = relationship(back_populates="contact_notes")

class Task(Base):
    __tablename__ = 'shop_task'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("auth_user.id", ondelete="SET NULL"))
    assigned_to: Mapped[Optional["User"]] = relationship(back_populates="tasks")

    contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shop_contact.id", ondelete="CASCADE"))
    contact: Mapped[Optional["Contact"]] = relationship(back_populates="tasks")
    
    quote_request_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shop_quoterequest.id", ondelete="SET NULL"))
    quote_request: Mapped[Optional["QuoteRequest"]] = relationship(back_populates="tasks")

class Notification(Base):
    __tablename__ = 'shop_notification'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth_user.id", ondelete="CASCADE"))
    user: Mapped["User"] = relationship(back_populates="notifications")
    message: Mapped[str] = mapped_column(String(255))
    link: Mapped[Optional[str]] = mapped_column(String(200))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class Category(Base):
    __tablename__ = 'shop_category'
    id: Mapped[int] = mapped_column(primary_key=True)
    name_ru: Mapped[str] = mapped_column(String(100), index=True)
    name_uz: Mapped[Optional[str]] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description_ru: Mapped[Optional[str]] = mapped_column(Text)
    description_uz: Mapped[Optional[str]] = mapped_column(Text)
    
    products: Mapped[List["Product"]] = relationship(back_populates="category")
    
    @property
    def name(self):
        return self.name_ru

class Product(Base):
    __tablename__ = 'shop_product'

    class StatusEnum(str, enum.Enum):
        IN_STOCK = 'IN_STOCK'
        PRE_ORDER = 'PRE_ORDER'
        OUT_OF_STOCK = 'OUT_OF_STOCK'
        
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("shop_category.id", ondelete="CASCADE"))
    category: Mapped["Category"] = relationship(back_populates="products")
    
    name_ru: Mapped[str] = mapped_column(String(200))
    name_uz: Mapped[Optional[str]] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    
    short_description_ru: Mapped[Optional[str]] = mapped_column(String(255))
    short_description_uz: Mapped[Optional[str]] = mapped_column(String(255))
    
    full_description_ru: Mapped[Optional[str]] = mapped_column(Text)
    full_description_uz: Mapped[Optional[str]] = mapped_column(Text)
    
    main_image: Mapped[Optional[str]] = mapped_column(String(100))
    
    dimensions_ru: Mapped[Optional[str]] = mapped_column(String(255), comment="Размеры (RU)")
    dimensions_uz: Mapped[Optional[str]] = mapped_column(String(255), comment="O'lchamlari (UZ)")

    materials_ru: Mapped[Optional[str]] = mapped_column(Text, comment="Материалы (RU), через новую строку")
    materials_uz: Mapped[Optional[str]] = mapped_column(Text, comment="Materiallar (UZ), через новую строку")

    price_min: Mapped[Optional[float]] = mapped_column(DECIMAL(12, 2), comment="Цена за м2 от")
    price_max: Mapped[Optional[float]] = mapped_column(DECIMAL(12, 2), comment="Цена за м2 до")

    area: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[StatusEnum] = mapped_column(EnumType(StatusEnum), default=StatusEnum.IN_STOCK)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    images: Mapped[List["ProductImage"]] = relationship(back_populates="product")
    quote_requests: Mapped[List["QuoteRequest"]] = relationship(back_populates="product")

    @property
    def name(self):
        return self.name_ru
    @property
    def materials_ru_list(self):
        return [line.strip() for line in self.materials_ru.split('\n') if line.strip()] if self.materials_ru else []
    
    @property
    def materials_uz_list(self):
        return [line.strip() for line in self.materials_uz.split('\n') if line.strip()] if self.materials_uz else []


class ProductImage(Base):
    __tablename__ = 'shop_productimage'
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("shop_product.id", ondelete="CASCADE"))
    product: Mapped["Product"] = relationship(back_populates="images")
    image: Mapped[str] = mapped_column(String(100))
    alt_text: Mapped[Optional[str]] = mapped_column(String(150))

class QuoteRequest(Base):
    __tablename__ = 'shop_quoterequest'

    class StatusEnum(str, enum.Enum):
        NEW = 'new'
        IN_PROGRESS = 'in_progress'
        COMPLETED = 'completed'
        CANCELLED = 'cancelled'
    
    class SourceEnum(str, enum.Enum):
        WEBSITE = 'website'
        CONTACT_FORM = 'contact_form'

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("shop_contact.id", ondelete="RESTRICT"))
    contact: Mapped["Contact"] = relationship(back_populates="requests", lazy="joined")
    
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shop_product.id", ondelete="SET NULL"))
    product: Mapped[Optional["Product"]] = relationship(back_populates="quote_requests", lazy="joined")

    message: Mapped[Optional[str]] = mapped_column(Text)
    
    status: Mapped[StatusEnum] = mapped_column(
        EnumType(
            StatusEnum,
            native_enum=False, 
            values_callable=lambda obj: [e.value for e in obj]
        ),
        default=StatusEnum.NEW,
        index=True
    )
    source: Mapped[SourceEnum] = mapped_column(
        EnumType(
            SourceEnum,
            native_enum=False, 
            values_callable=lambda obj: [e.value for e in obj]
        ),
        default=SourceEnum.WEBSITE
    )

    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("auth_user.id", ondelete="SET NULL"))
    assigned_to: Mapped[Optional["User"]] = relationship(back_populates="assigned_requests", lazy="joined")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    internal_notes: Mapped[Optional[str]] = mapped_column(Text)

    tasks: Mapped[List["Task"]] = relationship(back_populates="quote_request")
    status_logs: Mapped[List["StatusChangeLog"]] = relationship(back_populates="quote_request")

    @property
    def name(self):
        return self.contact.full_name

    @property
    def phone(self):
        return self.contact.phone
    
    def get_source_display(self):
        if self.source == self.SourceEnum.WEBSITE:
            return "Сайт"
        if self.source == self.SourceEnum.CONTACT_FORM:
            return "Форма (вручную)"
        return self.source.value.capitalize()
        
    def get_status_display(self):
        return self.status.value.replace('_', ' ').capitalize()

class RegistrationInvite(Base):
    __tablename__ = 'shop_registrationinvite'
    code: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    note: Mapped[Optional[str]] = mapped_column(String, comment="Заметка для кого это приглашение, например, email или имя")
    created_by_id: Mapped[int] = mapped_column(ForeignKey("auth_user.id", ondelete="CASCADE"))
    created_by: Mapped["User"] = relationship(back_populates="invites_sent")
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class StatusChangeLog(Base):
    __tablename__ = 'shop_statuschangelog'
    id: Mapped[int] = mapped_column(primary_key=True)
    quote_request_id: Mapped[int] = mapped_column(ForeignKey("shop_quoterequest.id", ondelete="CASCADE"))
    quote_request: Mapped["QuoteRequest"] = relationship(back_populates="status_logs")

    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("auth_user.id", ondelete="SET NULL"))
    user: Mapped[Optional["User"]] = relationship(back_populates="status_logs")

    old_status: Mapped[QuoteRequest.StatusEnum] = mapped_column(EnumType(QuoteRequest.StatusEnum, native_enum=False, name="statusenum", values_callable=lambda obj: [e.value for e in obj]))
    new_status: Mapped[QuoteRequest.StatusEnum] = mapped_column(EnumType(QuoteRequest.StatusEnum, native_enum=False, name="statusenum", values_callable=lambda obj: [e.value for e in obj]))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    note: Mapped[Optional[str]] = mapped_column(String(255))

    def get_old_status_display(self):
        return self.old_status.value.replace('_', ' ').capitalize()

    def get_new_status_display(self):
        return self.new_status.value.replace('_', ' ').capitalize()