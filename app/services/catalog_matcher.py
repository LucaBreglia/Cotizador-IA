from rapidfuzz import fuzz, process
from sqlmodel import Session, select

from app.models import Product
from app.schemas import LLMItem


def match_items(session: Session, items: list[LLMItem]) -> list[dict]:
    products = session.exec(select(Product).where(Product.is_active == True)).all()
    if not products:
        return [
            {
                "product_id": None,
                "raw_text": f"{item.quantity:g} {item.unit} {item.name}",
                "description": item.name,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": 0,
                "subtotal": 0,
                "match_confidence": 0,
                "needs_review": True,
            }
            for item in items
        ]

    choices: dict[str, Product] = {}
    for product in products:
        choices[product.name.lower()] = product
        for alias in (product.aliases or "").split(","):
            alias = alias.strip().lower()
            if alias:
                choices[alias] = product

    results = []
    for item in items:
        match = process.extractOne(
            item.name.lower(),
            choices.keys(),
            scorer=fuzz.WRatio,
        )
        confidence = float(match[1] / 100) if match else 0
        product = choices.get(match[0]) if match else None
        needs_review = confidence < 0.75 or (product is not None and product.stock_qty < item.quantity)
        if confidence < 0.55:
            product = None
            unit_price = 0
            needs_review = True
        else:
            unit_price = product.unit_price if product else 0

        quantity = item.quantity
        results.append(
            {
                "product_id": product.id if product else None,
                "raw_text": f"{quantity:g} {item.unit} {item.name}",
                "description": product.name if product else item.name,
                "quantity": quantity,
                "unit": item.unit,
                "unit_price": unit_price,
                "subtotal": quantity * unit_price,
                "match_confidence": confidence,
                "needs_review": needs_review,
            }
        )
    return results
