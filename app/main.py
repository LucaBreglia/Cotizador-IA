import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.models import Product
from app.routers import products, quotes

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Cotizador Automático IA",
    version="1.0.0",
)
allowed_hosts = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
if not allowed_hosts or "*" in allowed_hosts:
    allowed_hosts = ["localhost", "127.0.0.1"]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.include_router(products.router)
app.include_router(quotes.router)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.on_event("startup")
def startup() -> None:
    create_db_and_tables()
    seed_products = [
        ("CER-001", "Cemento Portland 50 kg", "cemento, bolsa cemento, portland", "bolsa", 18500, 120),
        ("CAL-001", "Cal hidratada 25 kg", "cal, bolsa cal", "bolsa", 6200, 80),
        ("ARE-001", "Arena fina", "arena fina de construccion", "m3", 18500, 35),
        ("PIE-001", "Piedra partida 6-20", "pedregullo, piedra", "m3", 22000, 28),
        ("LAD-001", "Ladrillo común", "ladrillos comunes", "unidad", 450, 1500),
        ("HIE-001", "Hierro 8 mm barra", "hierro 8, varilla 8", "barra", 7800, 200),
        ("HIE-002", "Hierro 10 mm barra", "hierro 10, varilla 10", "barra", 9600, 180),
        ("PIN-001", "Pintura látex interior 10 l", "latex, pintura blanca", "balde", 32000, 45),
        ("TIR-001", "Tirador para puerta cromado", "manija, tirador cromado", "unidad", 8500, 60),
        ("PEG-001", "Pegamento para cerámicos 30 kg", "adhesivo ceramica, pega ceramica", "bolsa", 14500, 75),
    ]
    with Session(engine) as session:
        if session.exec(select(Product)).first() is None:
            for sku, name, aliases, unit, price, stock in seed_products:
                session.add(
                    Product(
                        sku=sku,
                        name=name,
                        aliases=aliases,
                        unit=unit,
                        unit_price=price,
                        stock_qty=stock,
                        is_active=True,
                    )
                )
            session.commit()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})
