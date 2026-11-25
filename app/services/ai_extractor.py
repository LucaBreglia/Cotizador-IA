import os
import logging
from typing import Optional

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.schemas import ExtractionResultLLM

load_dotenv()
logger = logging.getLogger(__name__)


class AIExtractionError(RuntimeError):
    pass


async def extract_message(message: str) -> ExtractionResultLLM:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise AIExtractionError("La extracción con IA no está configurada.")

    try:
        client = genai.Client(api_key=api_key)
    except (TypeError, ValueError) as exc:
        logger.error("No se pudo inicializar el cliente de Gemini (%s)", type(exc).__name__)
        raise AIExtractionError("No se pudo inicializar el servicio de IA.") from exc
    prompt = (
        "Extrae de este mensaje informal de WhatsApp únicamente el nombre del cliente "
        "y una lista de productos solicitados con cantidad y unidad. "
        "No calcules precios ni inventes productos. Si no aparece una unidad, usa \"unidad\". "
        "Si no aparece cantidad, usa 1.\n\nMensaje:\n"
        + message
    )
    models = [
        os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash-lite"),
    ]

    for model in dict.fromkeys(models):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=ExtractionResultLLM,
                ),
            )
            parsed: Optional[ExtractionResultLLM] = response.parsed
            if parsed is not None:
                return parsed
            logger.warning("Gemini model %s returned no structured result", model)
        except (APIError, httpx.HTTPError) as exc:
            logger.warning(
                "Gemini model %s failed during extraction (%s)",
                model,
                type(exc).__name__,
            )
            continue
    raise AIExtractionError("La extracción con IA no está disponible.")
