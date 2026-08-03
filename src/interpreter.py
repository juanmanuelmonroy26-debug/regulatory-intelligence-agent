from __future__ import annotations

import json
import logging
import time
from typing import Any

import openai
import requests
from bs4 import BeautifulSoup

from src.models import ClassifiedChange, InterpretedChange, Priority

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Eres un experto en regulación tributaria colombiana y facturación electrónica DIAN.
Tu única fuente de información es el texto oficial de las normas que recibirás en cada solicitud.

Reglas estrictas:
1. NUNCA inventes resoluciones, decretos, conceptos o cualquier otro acto normativo.
2. NUNCA hagas suposiciones sobre el contenido de una norma si no fue proporcionado.
3. Si el texto recibido es insuficiente para responder alguna sección, escribe exactamente: "Información insuficiente en el texto recibido."
4. Responde SIEMPRE en español.
5. Tu respuesta debe ser un JSON válido con exactamente las claves especificadas. No incluyas texto fuera del JSON.

El equipo que leerá tus respuestas es el equipo de Regulación de Producto de Alegra, una plataforma de facturación electrónica colombiana."""

_USER_TEMPLATE = """Se detectó el siguiente cambio regulatorio en las fuentes oficiales de la DIAN.

## Datos del cambio
- Tipo de cambio: {change_type}
- Categoría funcional: {category}
- Prioridad preliminar: {priority}
- Norma ID: {norm_id}

## Estado ANTERIOR (antes del cambio)
{previous_text}

## Estado ACTUAL (texto completo de la norma)
{current_text}

## Instrucción
Compara el estado anterior con el estado actual y responde ÚNICAMENTE con el siguiente JSON (sin markdown, sin comentarios).
Tu análisis debe explicar concretamente qué impacto tiene este cambio sobre una plataforma de facturación electrónica colombiana como Alegra.

{{
  "que_cambio": "...",
  "implicaciones": "...",
  "modulo_afectado": "...",
  "urgencia": "Alta | Media | Baja",
  "accion_producto": "...",
  "accion_ingenieria": "...",
  "accion_customer_success": "..."
}}"""

_PRIORITY_MAP = {"alta": Priority.HIGH, "media": Priority.MEDIUM, "baja": Priority.LOW}

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}

_MAX_FULL_TEXT_CHARS = 8000


class ClaudeInterpreter:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        self.client = openai.OpenAI(api_key=api_key, base_url=_GROQ_BASE_URL)
        self.model = model
        self._http = requests.Session()
        self._http.headers.update(_FETCH_HEADERS)

    def interpret(self, change: ClassifiedChange) -> InterpretedChange:
        diff = change.diff

        # Previous state
        if diff.previous:
            previous_text = self._resolve_full_text(diff.previous.url, diff.previous.raw_text)
        else:
            previous_text = "Esta norma NO EXISTÍA en el normograma — es una adición nueva."

        # Current state — always fetch full text from URL when available
        if diff.current:
            current_text = self._resolve_full_text(diff.current.url, diff.current.raw_text)
        else:
            current_text = "Esta norma fue ELIMINADA del normograma — ya no está vigente."

        user_message = _USER_TEMPLATE.format(
            change_type=diff.change_type,
            category=change.category,
            priority=change.priority,
            norm_id=diff.norm_id,
            previous_text=previous_text,
            current_text=current_text,
        )

        parsed, prompt_tokens, completion_tokens = self._call_with_retry(user_message)
        urgency = _PRIORITY_MAP.get(parsed.get("urgencia", "").lower().strip(), change.priority)

        _insufficient = "Información insuficiente en el texto recibido."
        return InterpretedChange(
            classified=change,
            what_changed=parsed.get("que_cambio", _insufficient),
            implications=parsed.get("implicaciones", _insufficient),
            affected_module=parsed.get("modulo_afectado", str(change.category)),
            urgency=urgency,
            product_action=parsed.get("accion_producto", _insufficient),
            engineering_action=parsed.get("accion_ingenieria", _insufficient),
            cs_action=parsed.get("accion_customer_success", _insufficient),
            model_used=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def interpret_batch(self, changes: list[ClassifiedChange]) -> list[InterpretedChange]:
        if not changes:
            return []
        return [self.interpret(c) for c in changes]

    def _resolve_full_text(self, url: str | None, fallback_raw_text: str) -> str:
        """Fetch and extract full text from URL; fall back to raw_text on failure."""
        if not url:
            return fallback_raw_text
        try:
            response = self._http.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            container = soup.find("main") or soup.find("article") or soup.body
            if not container:
                return fallback_raw_text
            text = container.get_text(separator="\n", strip=True)
            text = text[:_MAX_FULL_TEXT_CHARS]
            logger.info(f"Full text fetched from {url} ({len(text)} chars)")
            return text
        except Exception as e:
            logger.warning(f"Could not fetch full text from {url}: {e} — using raw_text fallback")
            return fallback_raw_text

    def _call_with_retry(
        self, user_message: str, max_retries: int = 3
    ) -> tuple[dict[str, Any], int, int]:
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=2048,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                )
                raw_text = (response.choices[0].message.content or "").strip()

                if not raw_text:
                    raise json.JSONDecodeError("Empty response from model", "", 0)

                # Strip markdown code fences if model wraps the JSON
                if raw_text.startswith("```"):
                    parts = raw_text.split("```")
                    raw_text = parts[1].lstrip("json").strip() if len(parts) > 1 else raw_text

                parsed = json.loads(raw_text)
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                return parsed, prompt_tokens, completion_tokens

            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error on attempt {attempt}: {e}")
                last_error = e
                if attempt < max_retries:
                    time.sleep(2)
            except openai.RateLimitError as e:
                logger.warning(f"Rate limit — waiting 60s (attempt {attempt}): {e}")
                time.sleep(60)
                last_error = e
            except openai.APIError as e:
                logger.error(f"OpenAI API error on attempt {attempt}: {e}")
                last_error = e
                if attempt < max_retries:
                    time.sleep(5)

        logger.error(f"All retry attempts exhausted: {last_error}")
        return {}, 0, 0
