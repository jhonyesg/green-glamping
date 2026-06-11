"""System prompts para el modo llm-first.

El LLM recibe como contexto el system_prompt del tenant + la KB
del tenant (intents activos, catálogo de servicios, media keys)
+ memoria corta + mensaje del usuario. Devuelve un JSON
estructurado con la respuesta.

Este módulo se mantiene separado del parser (response_parser.py)
para que se puedan iterar los prompts sin tocar la lógica de
validación.
"""

from __future__ import annotations

from typing import Any

# Límite de tamaño del system prompt del lado del LLM.
# Más allá de esto, no tiene sentido inyectar la KB entera;
# se debe pasar a RAG selectivo (futuro).
MAX_PROMPT_CHARS = 32_000


# System prompt por defecto cuando el tenant no tiene uno propio.
# Es la "personalidad base" del bot. El del tenant se concatena
# al inicio, esto va al final.
DEFAULT_SYSTEM_PROMPT = """Eres el asistente virtual de {tenant_name}. Tu trabajo es
responder consultas de clientes sobre los servicios y combos que ofrece el negocio.

REGLAS:
1. Responde SIEMPRE en español, en tono amable y profesional.
2. SOLO usa la información del CATÁLOGO DE SERVICIOS y los INTENTS disponibles abajo.
3. NO inventes precios, fechas, ni detalles que no estén en el contexto.
4. Si la información no está en el contexto, responde amablemente que no tienes
   ese dato y ofrece derivar a un humano.
5. NO reveles que eres un modelo de lenguaje, IA, bot, ni nada técnico.
6. Si el cliente quiere reservar, pagar o hablar con una persona, ofrece derivar
   a un humano.
7. Si el cliente saluda sin hacer una pregunta concreta, devuelve el intent
   "saludo" con un saludo corto. NO listes el portafolio completo si el
   cliente solo está saludando.
8. Devuelve SIEMPRE un JSON con la estructura especificada en el user prompt.

CATÁLOGO DE SERVICIOS (planes con precios):
{plans}

INTENTS DISPONIBLES (puedes usar uno de estos como `intent`):
{intents}

HANDOFF RULES (derivar a humano):
{handoff_rules}

MEDIA KEYS (archivos disponibles para adjuntar via `use_media_keys`):
{media_keys}
"""


# User prompt con la estructura JSON que el LLM debe devolver.
USER_PROMPT_TEMPLATE = """MENSAJE DEL CLIENTE:
{message}

MEMORIA CORTA (últimos {n_turns} turnos previos):
{recent_turns}

Devuelve un JSON estricto (sin texto antes ni después) con esta estructura:

{{
  "intent": "nombre_del_intent_elegido_o_fallback",
  "response": "Texto para enviar al cliente. Tono amable, conciso.",
  "use_media_keys": ["lista_de_media_keys_a_adjuntar_o_vacia"],
  "requires_human": false,
  "handoff_rule": null_o_codigo_de_regla,
  "confidence": 0.0_a_1.0,
  "reasoning": "por_que_elegiste_este_intent"
}}

NO escribas nada fuera del JSON. NO uses ```json. Solo el objeto literal."""


def _truncate_kb_for_prompt(kb_payload: dict, max_chars: int = MAX_PROMPT_CHARS) -> dict:
    """Si el KB serializado excede max_chars, recorta los intents
    menos usados (heurística: primeros N). Devuelve el kb_payload
    sin cambios si entra completo."""
    import json
    serialized = json.dumps(kb_payload, ensure_ascii=False, default=str)
    if len(serialized) <= max_chars:
        return kb_payload
    # Truncar intents (mantener system prompt completo, sacrificar KB)
    if "intents" in kb_payload and isinstance(kb_payload["intents"], list):
        while len(json.dumps(kb_payload, ensure_ascii=False, default=str)) > max_chars:
            if len(kb_payload["intents"]) <= 3:
                break
            kb_payload["intents"] = kb_payload["intents"][:-1]
    return kb_payload


def build_response_prompt(
    tenant_name: str,
    kb_payload: dict,
    message: str,
    recent_turns: list[dict] | None = None,
    n_turns: int = 10,
) -> tuple[str, str]:
    """
    Construye los prompts para la generación de respuesta.
    Returns (system_prompt, user_prompt).

    kb_payload = {
      "plans": [{"nombre": "...", "precio_cop": ..., "incluye": [...]}],
      "intents": [{"name": "...", "description": "...", "examples": [...]}],
      "handoff_rules": [{"code": "H01", "trigger": "..."}],
      "media_keys": ["carta_bebidas", ...],
    }
    """
    import json

    kb_payload = _truncate_kb_for_prompt(kb_payload)

    plans_text = json.dumps(kb_payload.get("plans", []), ensure_ascii=False, default=str)
    intents_text = json.dumps(
        [{"name": i.get("name"), "description": i.get("description"), "examples": i.get("examples", [])}
         for i in kb_payload.get("intents", [])],
        ensure_ascii=False, default=str,
    )
    handoff_text = json.dumps(kb_payload.get("handoff_rules", []), ensure_ascii=False, default=str)
    media_text = json.dumps(kb_payload.get("media_keys", []), ensure_ascii=False, default=str)

    system = DEFAULT_SYSTEM_PROMPT.format(
        tenant_name=tenant_name,
        plans=plans_text,
        intents=intents_text,
        handoff_rules=handoff_text,
        media_keys=media_text,
    )

    # Serializar memoria corta
    recent = recent_turns or []
    if not recent:
        recent_text = "(sin historial previo)"
    else:
        recent_text = "\n".join(
            f"  [{t.get('role', '?')}] {t.get('text', '')[:200]}"
            for t in recent[-n_turns:]
        )

    user = USER_PROMPT_TEMPLATE.format(
        message=message[:1000],
        n_turns=len(recent[-n_turns:]),
        recent_turns=recent_text,
    )

    return system, user


def extract_kb_payload(
    plans: list[dict],
    intents: list[dict],
    handoff_rules: list[dict],
    media_keys: list[str],
) -> dict[str, Any]:
    """Helper para armar el kb_payload desde las queries del bot."""
    return {
        "plans": plans,
        "intents": intents,
        "handoff_rules": handoff_rules,
        "media_keys": media_keys,
    }
