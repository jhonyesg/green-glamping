"""
Humanización del envío: parte respuestas en burbujas y las entrega con
"escribiendo…" y retardos proporcionales al largo del texto.

plan() es una función pura (testeable). send_humanized() es el único
punto de envío usado por webhooks, poller y pruebas e2e.
"""

import asyncio
import random
from dataclasses import dataclass

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import ContentType, OutboundMessage

DEFAULTS = {
    "enabled": False,
    "channels": ["whatsapp_unofficial"],
    "split_bubbles": True,
    "max_bubbles": 4,
    "wpm": 40,
    "typing_min_ms": 800,
    "typing_max_ms": 6000,
    "pause_min_ms": 600,
    "pause_max_ms": 2200,
}


def default_humanization() -> dict:
    """Devuelve una copia fresca de los defaults (para inicializar bot_config)."""
    return dict(DEFAULTS)


def ensure_humanization_in_config(bot_config: dict | None) -> dict:
    """
    Asegura que `bot_config` tenga la clave `humanization` con los defaults.
    Si ya existe, se respeta; si no, se inserta con los defaults seguros
    (enabled=False para no humanizar de entrada por accidente).
    Idempotente: no se reinicia ni se pisa al recargar.
    """
    cfg = dict(bot_config or {})
    if "humanization" not in cfg:
        cfg["humanization"] = default_humanization()
    return cfg


@dataclass
class Bubble:
    text: str
    typing_ms: int
    pause_before_ms: int


def _cfg(humanization: dict | None) -> dict:
    merged = dict(DEFAULTS)
    merged.update(humanization or {})
    return merged


def plan(text: str, humanization: dict | None = None, rng: random.Random | None = None) -> list[Bubble]:
    """Calcula las burbujas y sus tiempos. Pura: misma semilla → mismo plan."""
    cfg = _cfg(humanization)
    rng = rng or random.Random()
    text = (text or "").strip()
    if not text:
        return []

    if cfg["split_bubbles"]:
        parts = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(parts) > cfg["max_bubbles"]:
            # Fusionar el excedente en la última burbuja
            head = parts[: cfg["max_bubbles"] - 1]
            tail = "\n\n".join(parts[cfg["max_bubbles"] - 1:])
            parts = head + [tail]
    else:
        parts = [text]

    bubbles: list[Bubble] = []
    for i, part in enumerate(parts):
        words = max(1, len(part.split()))
        base_ms = int(words / cfg["wpm"] * 60_000)
        jitter = rng.uniform(0.8, 1.25)
        typing_ms = int(min(max(base_ms * jitter, cfg["typing_min_ms"]), cfg["typing_max_ms"]))
        pause_ms = 0 if i == 0 else int(rng.uniform(cfg["pause_min_ms"], cfg["pause_max_ms"]))
        bubbles.append(Bubble(text=part, typing_ms=typing_ms, pause_before_ms=pause_ms))
    return bubbles


async def _load_humanization(tenant_id: int, session: AsyncSession) -> dict:
    try:
        row = (await session.execute(
            sa.text("SELECT bot_config FROM public.tenants WHERE id=:id"), {"id": tenant_id}
        )).fetchone()
        return ((row.bot_config or {}) if row else {}).get("humanization") or {}
    except Exception:
        return {}


def applies(humanization: dict | None, channel_type: str) -> bool:
    cfg = _cfg(humanization)
    return bool(cfg["enabled"]) and channel_type in cfg["channels"]


async def send_humanized(
    adapter,
    thread_id: str,
    text: str,
    tenant_id: int,
    channel_type: str,
    session: AsyncSession,
) -> None:
    """
    Envía `text` por el adapter. Si la humanización aplica al canal del
    tenant: burbujas + typing + pausas. Si no: envío directo inmediato.
    Los retardos ocurren DESPUÉS de medir latency_ms del pipeline.
    """
    humanization = await _load_humanization(tenant_id, session)

    if not applies(humanization, channel_type):
        await adapter.send(OutboundMessage(
            thread_id=thread_id, text=text, content_type=ContentType.text,
        ))
        return

    for bubble in plan(text, humanization):
        if bubble.pause_before_ms:
            await asyncio.sleep(bubble.pause_before_ms / 1000)
        try:
            await adapter.send_typing(thread_id)
        except Exception:
            pass
        await asyncio.sleep(bubble.typing_ms / 1000)
        result = await adapter.send(OutboundMessage(
            thread_id=thread_id, text=bubble.text, content_type=ContentType.text,
        ))
        if not getattr(result, "success", True):
            logger.warning(f"Burbuja no enviada: {getattr(result, 'error', '?')}")
            break
