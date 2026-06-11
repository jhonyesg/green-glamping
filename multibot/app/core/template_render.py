"""Template rendering for intent responses.

Soporta tres `response_type` por intent:
- `static` (default, retrocompatible): usa `response_text` literal.
- `template_jinja`: renderiza `response_template` con Jinja2 sandboxed.
- `data_driven`: igual a template_jinja pero requiere `requires_data`
  no vacío; falla ruidoso si el contexto no tiene esas claves.

Filtros custom: `currency_cop`, `media_url`, `today_es`.

Si el render falla (sandbox, syntax, undefined), se hace fallback
silencioso a `response_text` con log `template_render_failed`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from jinja2 import DictLoader, StrictUndefined
from jinja2.exceptions import TemplateSyntaxError, UndefinedError
from jinja2.sandbox import SandboxedEnvironment, SecurityError
from loguru import logger


def _format_cop(value: Any) -> str:
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return str(value)
    formatted = f"{n:,}".replace(",", ".")
    return f"${formatted}"


def _today_es() -> str:
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    now = datetime.now(UTC)
    return f"{now.day} de {meses[now.month - 1]} de {now.year}"


def _media_url_filter(media_map: dict, key: str) -> str:
    return media_map.get(key, "")


def _build_env(media_map: dict | None = None) -> SandboxedEnvironment:
    env = SandboxedEnvironment(
        loader=DictLoader({}),
        autoescape=False,
        undefined=StrictUndefined,
    )
    env.filters["currency_cop"] = _format_cop

    media_map = media_map or {}

    def media_url_filter(key: str) -> str:
        return _media_url_filter(media_map, key)

    env.filters["media_url"] = media_url_filter
    env.globals["today_es"] = _today_es
    env.globals["media_map"] = media_map
    return env


def render_str(template_str: str, context: dict) -> str:
    """Renderiza un template con sandbox. Lanza excepciones si hay error."""
    media_map = context.get("_media_map") or {}
    env = _build_env(media_map=media_map)
    tpl = env.from_string(template_str)
    return tpl.render(**context)


def render_response(intent: dict, context: dict) -> tuple[str, bool]:
    """
    Renderiza la respuesta del intent.
    Returns (text, fell_back). fell_back=True si se usó response_text
    por algún error.
    """
    response_type = intent.get("response_type") or "static"
    response_text = intent.get("response_text") or ""

    if response_type == "static" or not intent.get("response_template"):
        return response_text, False

    template_str = intent.get("response_template") or ""
    requires_data = intent.get("requires_data") or []

    if response_type == "data_driven" and requires_data:
        missing = [k for k in requires_data if k not in context]
        if missing:
            logger.warning(
                f"template_context_missing intent={intent.get('intent_name')} missing={missing}"
            )
            return response_text, True

    try:
        rendered = render_str(template_str, context)
        return rendered, False
    except SecurityError as e:
        logger.warning(
            f"template_render_failed intent={intent.get('intent_name')} "
            f"error=security detail={e}"
        )
        return response_text, True
    except UndefinedError as e:
        logger.warning(
            f"template_render_failed intent={intent.get('intent_name')} "
            f"error=undefined detail={e}"
        )
        return response_text, True
    except TemplateSyntaxError as e:
        logger.warning(
            f"template_render_failed intent={intent.get('intent_name')} "
            f"error=syntax detail={e}"
        )
        return response_text, True
    except Exception as e:
        logger.warning(
            f"template_render_failed intent={intent.get('intent_name')} "
            f"error={type(e).__name__} detail={e}"
        )
        return response_text, True
