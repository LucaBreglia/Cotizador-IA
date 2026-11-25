from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProductRead(BaseModel):
    id: int
    sku: str
    name: str
    aliases: str
    unit: str
    unit_price: float
    stock_qty: float
    is_active: bool
    updated_at: datetime


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    aliases: str = Field(default="", max_length=2000)
    unit: str = Field(default="unidad", max_length=50)
    unit_price: float = Field(default=0, ge=0, allow_inf_nan=False)
    stock_qty: float = Field(default=0, ge=0, allow_inf_nan=False)


class ParseMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    customer_name: Optional[str] = Field(default=None, max_length=200)
    customer_phone: Optional[str] = Field(default=None, max_length=50)
    discount_pct: float = Field(default=0, ge=0, le=100, allow_inf_nan=False)


class LLMItem(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    quantity: float = Field(default=1, ge=0.01, allow_inf_nan=False)
    unit: str = Field(default="unidad", max_length=50)


class ExtractionResultLLM(BaseModel):
    customer_name: Optional[str] = Field(default=None, max_length=200)
    items: list[LLMItem] = Field(default_factory=list, max_length=200)


class QuoteItemRead(BaseModel):
    id: int
    quote_id: int
    product_id: Optional[int]
    raw_text: str
    description: str
    quantity: float
    unit: str
    unit_price: float
    subtotal: float
    match_confidence: float
    needs_review: bool


class QuoteRead(BaseModel):
    id: int
    quote_number: str
    customer_name: str
    customer_phone: str
    raw_message: str
    status: str
    subtotal: float
    discount_pct: float
    total: float
    valid_until: datetime
    created_at: datetime
    items: list[QuoteItemRead] = Field(default_factory=list)


class QuoteItemUpdate(BaseModel):
    id: Optional[int] = None
    product_id: Optional[int] = None
    raw_text: Optional[str] = Field(default=None, max_length=1000)
    description: Optional[str] = Field(default=None, max_length=500)
    quantity: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    unit: Optional[str] = Field(default=None, max_length=50)
    unit_price: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    delete: bool = False


class QuoteUpdate(BaseModel):
    customer_name: Optional[str] = Field(default=None, max_length=200)
    customer_phone: Optional[str] = Field(default=None, max_length=50)
    discount_pct: Optional[float] = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    items: Optional[list[QuoteItemUpdate]] = Field(default=None, max_length=200)
