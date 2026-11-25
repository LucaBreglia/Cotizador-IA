from datetime import datetime, timezone
from io import BytesIO
import logging
import math
from typing import Optional
from zipfile import BadZipFile, ZipFile

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import update
from sqlmodel import Session, select

from app.database import get_session
from app.models import Product
from app.schemas import ProductCreate, ProductRead

router = APIRouter(prefix="/api/products", tags=["products"])
logger = logging.getLogger(__name__)
MAX_CATALOG_FILE_BYTES = 10 * 1024 * 1024
MAX_XLSX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_XLSX_ARCHIVE_ENTRIES = 1000
MAX_CATALOG_ROWS = 20000
MAX_CATALOG_COLUMNS = 30


def _column(frame: pd.DataFrame, *names: str) -> Optional[pd.Series]:
    normalized = {str(column).strip().lower(): column for column in frame.columns}
    for name in names:
        key = name.lower()
        if key in normalized:
            return frame[normalized[key]]
    return None


def _number(value, default: float = 0) -> float:
    if pd.isna(value):
        return default
    text = str(value).strip().replace(",", ".")
    if not text or text.lower() == "nan":
        return default
    try:
        number = float(text)
    except ValueError as exc:
        raise ValueError("El valor debe ser numérico") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError("El valor debe ser finito y no negativo")
    return number


def _text(value, default: str = "") -> str:
    if pd.isna(value):
        return default
    text = str(value).strip()
    return default if text.lower() == "nan" else text


@router.get("", response_model=list[ProductRead])
def list_products(session: Session = Depends(get_session)) -> list[Product]:
    products = session.exec(
        select(Product).where(Product.is_active == True).order_by(Product.name)
    ).all()
    return list(products)


@router.post("", response_model=ProductRead, status_code=201)
def create_product(
    request: ProductCreate,
    response: Response,
    session: Session = Depends(get_session),
) -> Product:
    sku = request.sku.strip()
    product_name = request.name.strip()
    if not sku or not product_name:
        raise HTTPException(status_code=422, detail="SKU y nombre son obligatorios")

    product = session.exec(select(Product).where(Product.sku == sku)).first()
    if product:
        response.status_code = 200
        product.name = product_name
        product.aliases = request.aliases.strip()
        product.unit = request.unit.strip() or "unidad"
        product.unit_price = request.unit_price
        product.stock_qty = request.stock_qty
        product.is_active = True
        product.updated_at = datetime.now(timezone.utc)
    else:
        product = Product(
            sku=sku,
            name=product_name,
            aliases=request.aliases.strip(),
            unit=request.unit.strip() or "unidad",
            unit_price=request.unit_price,
            stock_qty=request.stock_qty,
            is_active=True,
        )
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    request: ProductCreate,
    session: Session = Depends(get_session),
) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    sku = request.sku.strip()
    product_name = request.name.strip()
    if not sku or not product_name:
        raise HTTPException(status_code=422, detail="SKU y nombre son obligatorios")

    duplicate = session.exec(
        select(Product).where(Product.sku == sku, Product.id != product_id)
    ).first()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Ya existe un producto con ese SKU")

    product.sku = sku
    product.name = product_name
    product.aliases = request.aliases.strip()
    product.unit = request.unit.strip() or "unidad"
    product.unit_price = request.unit_price
    product.stock_qty = request.stock_qty
    product.is_active = True
    product.updated_at = datetime.now(timezone.utc)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.delete("/{product_id}", response_model=ProductRead)
def deactivate_product(
    product_id: int,
    session: Session = Depends(get_session),
) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    product.is_active = False
    product.updated_at = datetime.now(timezone.utc)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.post("/import")
async def import_catalog(
    file: UploadFile = File(...),
    replace_all: bool = Form(False),
    session: Session = Depends(get_session),
) -> dict:
    name = (file.filename or "").lower()
    if not name.endswith(".xlsx") and not name.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos .xlsx o .csv")

    content = await file.read(MAX_CATALOG_FILE_BYTES + 1)
    await file.close()
    if len(content) > MAX_CATALOG_FILE_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 10 MB")

    try:
        if name.endswith(".xlsx"):
            with ZipFile(BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_XLSX_ARCHIVE_ENTRIES:
                    raise HTTPException(status_code=413, detail="El archivo Excel contiene demasiados elementos")
                if sum(entry.file_size for entry in entries) > MAX_XLSX_UNCOMPRESSED_BYTES:
                    raise HTTPException(status_code=413, detail="El contenido descomprimido del Excel es demasiado grande")
            frame = pd.read_excel(BytesIO(content), engine="openpyxl")
        else:
            frame = pd.read_csv(BytesIO(content))
    except HTTPException:
        raise
    except (BadZipFile, ValueError, OSError, pd.errors.ParserError) as exc:
        logger.warning("Catalog import rejected due to invalid file (%s)", type(exc).__name__)
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo. Verificá su formato.") from exc

    if frame.empty:
        raise HTTPException(status_code=400, detail="El archivo no contiene productos")
    if len(frame.index) > MAX_CATALOG_ROWS:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 20.000 filas")
    if len(frame.columns) > MAX_CATALOG_COLUMNS:
        raise HTTPException(status_code=400, detail="El archivo contiene demasiadas columnas")

    sku_col = _column(frame, "sku", "codigo", "código", "code")
    name_col = _column(frame, "name", "nombre", "producto", "descripcion", "descripción")
    if sku_col is None or name_col is None:
        raise HTTPException(
            status_code=400,
            detail="El archivo debe incluir columnas SKU y Nombre",
        )

    aliases_col = _column(frame, "aliases", "alias", "sinonimos", "sinónimos")
    unit_col = _column(frame, "unit", "unidad", "umed")
    price_col = _column(frame, "unit_price", "precio", "precio_unitario", "price")
    stock_col = _column(frame, "stock_qty", "stock", "cantidad", "existencia")

    created = 0
    updated = 0
    imported_skus: set[str] = set()
    for index, row in frame.iterrows():
        sku = str(sku_col.iloc[index]).strip()
        if not sku or sku.lower() == "nan":
            continue

        product_name = str(name_col.iloc[index]).strip()
        if not product_name or product_name.lower() == "nan":
            continue
        imported_skus.add(sku)

        aliases = _text(aliases_col.iloc[index]) if aliases_col is not None else ""
        unit = _text(unit_col.iloc[index], "unidad") if unit_col is not None else "unidad"
        try:
            product_data = ProductCreate(
                sku=sku,
                name=product_name,
                aliases=aliases,
                unit=unit or "unidad",
                unit_price=_number(price_col.iloc[index] if price_col is not None else 0),
                stock_qty=_number(stock_col.iloc[index] if stock_col is not None else 0),
            )
        except (ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"La fila {index + 2} contiene datos inválidos",
            ) from exc

        sku = product_data.sku.strip()
        product_name = product_data.name.strip()
        product = session.exec(select(Product).where(Product.sku == sku)).first()
        if product:
            product.name = product_name
            product.aliases = product_data.aliases.strip()
            product.unit = product_data.unit.strip() or "unidad"
            product.unit_price = product_data.unit_price
            product.stock_qty = product_data.stock_qty
            product.is_active = True
            product.updated_at = datetime.now(timezone.utc)
            updated += 1
        else:
            session.add(
                Product(
                    sku=sku,
                    name=product_name,
                    aliases=product_data.aliases.strip(),
                    unit=product_data.unit.strip() or "unidad",
                    unit_price=product_data.unit_price,
                    stock_qty=product_data.stock_qty,
                    is_active=True,
                )
            )
            created += 1

    if not imported_skus:
        raise HTTPException(status_code=400, detail="El archivo no contiene productos válidos")

    if replace_all:
        session.exec(
            update(Product)
            .where(Product.sku.notin_(imported_skus))
            .values(is_active=False)
        )

    session.commit()
    return {"created": created, "updated": updated}
