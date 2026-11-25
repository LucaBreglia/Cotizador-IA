from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from app.database import get_session
from app.models import Product, Quote, QuoteItem
from app.schemas import ParseMessageRequest, QuoteRead, QuoteUpdate
from app.services.ai_extractor import AIExtractionError, extract_message
from app.services.catalog_matcher import match_items
from app.services.pdf_generator import generate_quote_pdf

router = APIRouter(prefix="/api/quotes", tags=["quotes"])


def quote_read(session: Session, quote: Quote) -> QuoteRead:
    items = session.exec(
        select(QuoteItem).where(QuoteItem.quote_id == quote.id).order_by(QuoteItem.id)
    ).all()
    return QuoteRead(
        id=quote.id,
        quote_number=quote.quote_number,
        customer_name=quote.customer_name,
        customer_phone=quote.customer_phone,
        raw_message=quote.raw_message,
        status=quote.status,
        subtotal=quote.subtotal,
        discount_pct=quote.discount_pct,
        total=quote.total,
        valid_until=quote.valid_until,
        created_at=quote.created_at,
        items=[
            {
                "id": item.id,
                "quote_id": item.quote_id,
                "product_id": item.product_id,
                "raw_text": item.raw_text,
                "description": item.description,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": item.unit_price,
                "subtotal": item.subtotal,
                "match_confidence": item.match_confidence,
                "needs_review": item.needs_review,
            }
            for item in items
        ],
    )


def recalculate(session: Session, quote: Quote) -> None:
    items = session.exec(select(QuoteItem).where(QuoteItem.quote_id == quote.id)).all()
    subtotal = 0.0
    for item in items:
        item.subtotal = round(item.quantity * item.unit_price, 2)
        subtotal += item.subtotal
    quote.subtotal = round(subtotal, 2)
    quote.total = round(subtotal * (1 - quote.discount_pct / 100), 2)


def new_quote_number() -> str:
    now = datetime.now(timezone.utc)
    return f"P-{now:%Y%m%d}-{uuid4().hex[:6].upper()}"


@router.post("/parse-message", response_model=QuoteRead)
async def parse_message(
    request: ParseMessageRequest,
    session: Session = Depends(get_session),
) -> QuoteRead:
    try:
        extracted = await extract_message(request.message)
    except AIExtractionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    customer_name = request.customer_name or extracted.customer_name or ""

    quote = Quote(
        quote_number=new_quote_number(),
        customer_name=customer_name,
        customer_phone=request.customer_phone or "",
        raw_message=request.message,
        status="draft",
        discount_pct=request.discount_pct,
    )
    session.add(quote)
    session.commit()
    session.refresh(quote)

    for matched in match_items(session, extracted.items):
        session.add(
            QuoteItem(
                quote_id=quote.id,
                product_id=matched["product_id"],
                raw_text=matched["raw_text"],
                description=matched["description"],
                quantity=matched["quantity"],
                unit=matched["unit"],
                unit_price=matched["unit_price"],
                subtotal=matched["subtotal"],
                match_confidence=matched["match_confidence"],
                needs_review=matched["needs_review"],
            )
        )
    session.commit()
    recalculate(session, quote)
    session.add(quote)
    session.commit()
    session.refresh(quote)
    return quote_read(session, quote)


@router.patch("/{quote_id}", response_model=QuoteRead)
def update_quote(
    quote_id: int,
    update: QuoteUpdate,
    session: Session = Depends(get_session),
) -> QuoteRead:
    quote = session.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")

    if update.customer_name is not None:
        quote.customer_name = update.customer_name
    if update.customer_phone is not None:
        quote.customer_phone = update.customer_phone
    if update.discount_pct is not None:
        quote.discount_pct = update.discount_pct

    if update.items is not None:
        for item_update in update.items:
            if item_update.delete:
                if item_update.id is not None:
                    item = session.get(QuoteItem, item_update.id)
                    if item is None or item.quote_id != quote.id:
                        raise HTTPException(status_code=404, detail="Ítem de presupuesto no encontrado")
                    session.delete(item)
                continue

            item = session.get(QuoteItem, item_update.id) if item_update.id is not None else None
            if item is None:
                if item_update.id is not None:
                    raise HTTPException(status_code=404, detail="Ítem de presupuesto no encontrado")
                item = QuoteItem(
                    quote_id=quote.id,
                    description=item_update.description or "",
                    quantity=item_update.quantity or 1,
                    unit=item_update.unit or "unidad",
                    unit_price=item_update.unit_price or 0,
                    raw_text=item_update.raw_text or "",
                )
            elif item.quote_id != quote.id:
                raise HTTPException(status_code=404, detail="Ítem de presupuesto no encontrado")

            if item_update.product_id is not None:
                product = session.get(Product, item_update.product_id)
                if product and product.is_active:
                    item.product_id = product.id
                    item.description = product.name
                    item.unit = product.unit
                    if item_update.unit_price is None:
                        item.unit_price = product.unit_price
                    item.needs_review = product.stock_qty < item.quantity
                    item.match_confidence = 1.0
                else:
                    raise HTTPException(status_code=404, detail="Producto no encontrado")
            elif item_update.product_id is None and item_update.description is not None:
                item.description = item_update.description

            if item_update.quantity is not None:
                item.quantity = item_update.quantity
            if item_update.unit is not None:
                item.unit = item_update.unit
            if item_update.unit_price is not None:
                item.unit_price = item_update.unit_price
            if item_update.raw_text is not None:
                item.raw_text = item_update.raw_text

            if item.product_id is not None:
                product = session.get(Product, item.product_id)
                if product:
                    item.needs_review = item.quantity > product.stock_qty
            elif item_update.description is not None:
                item.needs_review = True
            session.add(item)

    session.commit()
    session.refresh(quote)
    recalculate(session, quote)
    session.add(quote)
    session.commit()
    session.refresh(quote)
    return quote_read(session, quote)


@router.get("/{quote_id}/pdf")
def download_quote_pdf(
    quote_id: int,
    session: Session = Depends(get_session),
) -> Response:
    quote = session.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    items = session.exec(
        select(QuoteItem).where(QuoteItem.quote_id == quote.id).order_by(QuoteItem.id)
    ).all()
    pdf_bytes = generate_quote_pdf(quote, items)
    quote.status = "confirmed"
    session.add(quote)
    session.commit()
    filename = f"{quote.quote_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("", response_model=list[QuoteRead])
def list_quotes(session: Session = Depends(get_session)) -> list[QuoteRead]:
    quotes = session.exec(select(Quote).order_by(Quote.created_at.desc())).all()
    return [quote_read(session, quote) for quote in quotes]
