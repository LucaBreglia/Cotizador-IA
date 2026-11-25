import os
from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.models import Quote

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def generate_quote_pdf(quote: Quote, items: list) -> bytes:
    try:
        from weasyprint import HTML
    except OSError as exc:
        raise RuntimeError(
            "WeasyPrint no pudo cargar sus librerías nativas. "
            "Ejecutá la aplicación con Docker o instalá las dependencias GTK de WeasyPrint."
        ) from exc

    template = env.get_template("quote_pdf.html")
    html = template.render(
        quote=quote,
        items=items,
        commerce_name=os.getenv("COMMERCE_NAME", "Comercio"),
        commerce_address=os.getenv("COMMERCE_ADDRESS", ""),
        commerce_phone=os.getenv("COMMERCE_PHONE", ""),
    )
    output = BytesIO()
    HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(output)
    return output.getvalue()
