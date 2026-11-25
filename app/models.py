from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sku: str = Field(index=True, unique=True)
    name: str = Field(index=True)
    aliases: str = ""
    unit: str = "unidad"
    unit_price: float = 0
    stock_qty: float = 0
    is_active: bool = True
    updated_at: datetime = Field(default_factory=utc_now)


class Quote(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    quote_number: str = Field(index=True, unique=True)
    customer_name: str = ""
    customer_phone: str = ""
    raw_message: str = ""
    status: str = "draft"
    subtotal: float = 0
    discount_pct: float = 0
    total: float = 0
    valid_until: datetime = Field(default_factory=lambda: utc_now() + timedelta(days=7))
    created_at: datetime = Field(default_factory=utc_now)


class QuoteItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    quote_id: int = Field(foreign_key="quote.id", index=True)
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    raw_text: str = ""
    description: str = ""
    quantity: float = 1
    unit: str = "unidad"
    unit_price: float = 0
    subtotal: float = 0
    match_confidence: float = 0
    needs_review: bool = True
