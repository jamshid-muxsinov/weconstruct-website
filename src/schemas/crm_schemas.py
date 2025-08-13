from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

from src.models.shop_models import QuoteRequest

class _UserInCrm(BaseModel):
    id: int; username: str; first_name: Optional[str] = None; model_config = ConfigDict(from_attributes=True)
class _ContactInCrm(BaseModel):
    id: int; name: str; phone: str; model_config = ConfigDict(from_attributes=True)
class _ProductInCrm(BaseModel):
    id: int; name: str; model_config = ConfigDict(from_attributes=True)

class QuoteRequestRead(BaseModel):
    id: int; contact: _ContactInCrm; product: Optional[_ProductInCrm] = None; message: Optional[str] = None; status: QuoteRequest.StatusEnum; source: QuoteRequest.SourceEnum; assigned_to: Optional[_UserInCrm] = None; created_at: datetime; updated_at: datetime; model_config = ConfigDict(from_attributes=True)
    
class QuoteRequestStatusUpdate(BaseModel):
    id: int
    status: QuoteRequest.StatusEnum

class QuoteRequestAssignUpdate(BaseModel):
    assigned_to_id: int

class TaskBase(BaseModel):
    title: str; description: Optional[str] = None; due_date: Optional[datetime] = None; completed: bool = False; assigned_to_id: Optional[int] = None; contact_id: Optional[int] = None
class TaskCreate(TaskBase):
    quote_request_id: Optional[int] = None
class TaskRead(TaskBase):
    id: int; created_at: datetime; quote_request_id: Optional[int] = None; assigned_to: Optional[_UserInCrm] = None; contact: Optional[_ContactInCrm] = None; model_config = ConfigDict(from_attributes=True)