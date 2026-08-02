from __future__ import annotations

import json
import logging
import time
from typing import Any

import openai

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

## Texto anterior (si aplica)
{previous_text}

## Texto actual (si aplica)
{current_text}

## Instrucción
Analiza el cambio y responde ÚNICAMENTE con el siguiente JSON (sin markdown, sin comentarios):

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


class ClaudeInterpreter:
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-20b") -> None:
        self.client = openai.OpenAI(api_key=api_key, base_url=_GROQ_BASE_URL)
        self.model = model

    def interpret(self, change: ClassifiedChange) -> InterpretedChange:
        diff = change.diff
        previous_text = diff.previous.raw_text if diff.previous else "No aplica — norma nueva"
        current_text = diff.current.raw_text if diff.current else "No aplica — norma eliminada"

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

    def _call_with_retry(
        self, user_message: str, max_retries: int = 2
    ) -> tuple[dict[str, Any], int, int]:
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                )
                raw_text = response.choices[0].message.content or ""
                raw_text = raw_text.strip()

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
