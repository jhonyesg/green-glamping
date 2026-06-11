"""Parser del JSON que devuelve el LLM en el modo llm-first.

El LLM responde a un mensaje con un JSON estructurado:
{
  "intent": "info_servicios",
  "response": "Texto para enviar al cliente",
  "use_media_keys": ["carta_bebidas", "spa_pareja"],
  "requires_human": false,
  "handoff_rule": null,
  "confidence": 0.85,
  "reasoning": "..."
}

Este módulo:
1. Intenta parsear el JSON. Si falla, retorna None (la
   pipeline cae al regex match).
2. Valida campos requeridos: intent, response.
3. Aplica safety check contra leaks de prompt.
4. Convierte confidence baja a requires_human.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# Frases que el LLM podría usar para "salir del personaje".
# Si matchean en el campo response, el response se marca como
# prompt_leak_detected y la pipeline lo reemplaza.
_PROMPT_LEAK_PATTERNS = [
    re.compile(r"\bsoy\s+(?:un\s+|una\s+)?(?:bot|ia|inteligencia\s+artificial|modelo\s+de\s+lenguaje|asistente\s+virtual)\b", re.IGNORECASE),
    re.compile(r"\bcomo\s+(?:modelo\s+de\s+lenguaje|ia|assistant|chatbot)\b", re.IGNORECASE),
    re.compile(r"\bmi\s+(?:system\s+)?prompt\b", re.IGNORECASE),
    re.compile(r"\binstrucciones?\s+del\s+sistema\b", re.IGNORECASE),
    re.compile(r"\bno\s+tengo\s+cuerpo\s+f[ií]sico\b", re.IGNORECASE),
    re.compile(r"\bsistema\s+de\s+instrucciones\b", re.IGNORECASE),
]

# FALLBACK genérico cuando hay prompt leak
_PROMPT_LEAK_FALLBACK = (
    "¡Hola! 👋 Soy el asistente virtual del equipo. "
    "¿En qué te puedo ayudar?"
)

# Confidence mínima para que la respuesta se considere "buena"
CONFIDENCE_FLOOR = 0.4


@dataclass
class LLMResponse:
    intent: str
    response: str
    use_media_keys: list[str] = field(default_factory=list)
    requires_human: bool = False
    handoff_rule: str | None = None
    confidence: float = 0.5
    reasoning: str = ""
    prompt_leak_detected: bool = False
    raw_dict: dict = field(default_factory=dict)


def _detect_prompt_leak(text: str) -> bool:
    return any(p.search(text) for p in _PROMPT_LEAK_PATTERNS)


def parse_llm_response(raw: str) -> LLMResponse | None:
    """
    Intenta parsear la respuesta cruda del LLM como JSON estructurado.

    Returns:
        LLMResponse con todos los campos validados, o None si:
        - El JSON no se puede parsear
        - Faltan campos requeridos (intent, response)
        - El campo response está vacío

    Si el response contiene un prompt leak, lo marca
    `prompt_leak_detected=True` y se usa la respuesta original
    (la pipeline decide si la reemplaza con el fallback genérico).
    """
    if not raw or not raw.strip():
        return None

    # 1. JSON parse
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    # 2. Schema check
    intent = data.get("intent")
    response = data.get("response")
    if not isinstance(intent, str) or not intent.strip():
        return None
    if not isinstance(response, str) or not response.strip():
        return None

    # 3. Extraer opcionales con defaults
    use_media_keys = data.get("use_media_keys") or []
    if not isinstance(use_media_keys, list):
        use_media_keys = []
    use_media_keys = [str(k) for k in use_media_keys if k]

    requires_human = bool(data.get("requires_human", False))
    handoff_rule = data.get("handoff_rule")
    if handoff_rule is not None and not isinstance(handoff_rule, str):
        handoff_rule = None

    confidence = data.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)):
        confidence = 0.5
    confidence = max(0.0, min(1.0, float(confidence)))

    reasoning = data.get("reasoning") or ""
    if not isinstance(reasoning, str):
        reasoning = ""

    # 4. Safety check
    prompt_leak = _detect_prompt_leak(response)

    # 5. Confidence floor → si duda, escalar a humano
    if confidence < CONFIDENCE_FLOOR:
        requires_human = True

    return LLMResponse(
        intent=intent.strip(),
        response=response.strip(),
        use_media_keys=use_media_keys,
        requires_human=requires_human,
        handoff_rule=handoff_rule,
        confidence=confidence,
        reasoning=reasoning,
        prompt_leak_detected=prompt_leak,
        raw_dict=data,
    )


def replace_prompt_leak(response: LLMResponse) -> LLMResponse:
    """Devuelve una copia del LLMResponse con el campo response
    reemplazado por el fallback genérico."""
    return LLMResponse(
        intent=response.intent,
        response=_PROMPT_LEAK_FALLBACK,
        use_media_keys=response.use_media_keys,
        requires_human=response.requires_human,
        handoff_rule=response.handoff_rule,
        confidence=response.confidence,
        reasoning=response.reasoning,
        prompt_leak_detected=True,
        raw_dict=response.raw_dict,
    )
