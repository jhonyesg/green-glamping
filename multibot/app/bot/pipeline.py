"""Core bot pipeline: anti_injection → memory → classify → respond → persist → send."""

import time
from dataclasses import dataclass

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.anti_injection import check_injection
from app.bot.classifier import classify
from app.bot.handoff import is_in_handoff_pause, resume_conversation, should_resume, trigger_handoff
from app.bot.memory import get_or_create_conversation, get_recent_turns, persist_message
from app.bot.responder import OutboundMessage, build_response
from app.core.template_render import render_response


@dataclass
class PipelineResult:
    outbound: OutboundMessage
    latency_ms: int
    blocked_injection: bool = False
    in_handoff_silence: bool = False
    conversation_id: int | None = None
    is_new_conversation: bool = False


INJECTION_BLOCK_RESPONSE = (
    "Lo siento, no puedo procesar ese tipo de mensaje. "
    "¿En qué puedo ayudarte con Green Glamping? 🌿"
)

HANDOFF_SILENCE_RESPONSE = (
    "Gracias por tu mensaje. En este momento mi compañera está atendiendo tu caso 🙌\n\n"
    "Te responderemos en breve por este mismo chat."
)


async def process(
    text: str,
    tenant_id: int,
    session: AsyncSession,
    external_thread_id: str = "unknown",
    user_external_id: str = "unknown",
    push_name: str | None = None,
    operation_mode: str = "autonomous",
    config: dict | None = None,
) -> PipelineResult:
    start = time.monotonic()
    cfg = config or {}

    # 1. Anti-injection gate (configurable per tenant)
    if cfg.get("anti_injection_enabled", True) and check_injection(text):
        elapsed = int((time.monotonic() - start) * 1000)
        return PipelineResult(
            outbound=OutboundMessage(
                text=cfg.get("injection_response") or INJECTION_BLOCK_RESPONSE,
                intent_name="blocked_injection",
                matched_via="anti_injection",
            ),
            latency_ms=elapsed,
            blocked_injection=True,
        )

    # 2. Get/create conversation
    conversation, is_new = await get_or_create_conversation(
        tenant_id=tenant_id,
        external_thread_id=external_thread_id,
        user_external_id=user_external_id,
        push_name=push_name,
        operation_mode=operation_mode,
        session=session,
    )
    conv_id = conversation["id"]

    # 3. Check handoff silence
    if is_in_handoff_pause(conversation):
        # Log user message but don't respond
        await persist_message(conv_id, "user", text, session, matched_via="fallback")
        elapsed = int((time.monotonic() - start) * 1000)
        return PipelineResult(
            outbound=OutboundMessage(
                text=cfg.get("handoff_silence_response") or HANDOFF_SILENCE_RESPONSE,
                intent_name="handoff_silence",
                matched_via="fallback",
            ),
            latency_ms=elapsed,
            in_handoff_silence=True,
            conversation_id=conv_id,
        )

    # 4. If long pause has elapsed → resume bot
    if should_resume(conversation, long_pause_hours=cfg.get("long_pause_hours")):
        await resume_conversation(conversation, session)
        conversation["in_handoff"] = False

    # 5. Get recent context (configurable: enabled + window size)
    if cfg.get("memory_enabled", True):
        recent_turns = await get_recent_turns(
            conv_id, session, k=int(cfg.get("memory_turns", 10))
        )
    else:
        recent_turns = []

    # 6. Classify
    classification = await classify(text, tenant_id, session)

    # 6b. Custom fallback response from tenant config
    if classification.matched_via == "fallback" and cfg.get("fallback_response"):
        classification.response_text = cfg["fallback_response"]

    # 7. Persist user message
    await persist_message(
        conv_id, "user", text, session,
        intent_id=classification.intent_id,
        matched_via=classification.matched_via,
    )

    # 8. Build response
    outbound = build_response(classification)

    # 8b. Render template (data_driven / template_jinja) si el intent lo pide
    intent_dict = {
        "intent_name": classification.intent_name,
        "response_type": "static",  # default
        "response_text": outbound.text,
        "response_template": None,
    }
    if classification.intent_id is not None:
        try:
            await session.execute(sa.text(f'SET search_path TO "tenant_{_tenant_slug(tenant_id, session)}", public'))
            row = (await session.execute(
                sa.text(
                    "SELECT response_type, response_text, response_template, "
                    "requires_data, response_media_ids "
                    "FROM kb_intents WHERE id=:id"
                ),
                {"id": classification.intent_id},
            )).fetchone()
            if row is not None:
                intent_dict["response_type"] = row.response_type or "static"
                intent_dict["response_text"] = row.response_text or outbound.text
                intent_dict["response_template"] = row.response_template
                intent_dict["requires_data"] = row.requires_data or []
                # Media adjuntos al intent: se mandan junto con la respuesta
                media_ids = row.response_media_ids or []
                if isinstance(media_ids, str):
                    import json as _json
                    media_ids = _json.loads(media_ids)
                outbound.media_attachments = [int(x) for x in media_ids if x]
        except Exception as e:
            logger.warning(f"template_lookup_failed intent_id={classification.intent_id} error={e}")

    if intent_dict["response_type"] != "static" and intent_dict.get("response_template"):
        ctx = await _build_render_context(tenant_id, session, recent_turns, channel="telegram")
        rendered, fell_back = render_response(intent_dict, ctx)
        if not fell_back:
            outbound.text = rendered

    # 9. Handle handoff trigger
    if classification.handoff_rule and classification.requires_human:
        await trigger_handoff(
            conversation, classification.handoff_rule, classification.intent_name, session,
            pause_hours=cfg.get("short_pause_hours"),
        )
        # Look up notify_target from handoff_rules table
        rule_row = (await session.execute(
            sa.text(
                "SELECT notify_channel, notify_target, custom_message "
                "FROM handoff_rules "
                "WHERE tenant_id = :tid AND rule_code = :code AND is_active = true "
                "LIMIT 1"
            ),
            {"tid": tenant_id, "code": classification.handoff_rule},
        )).fetchone()

        if rule_row:
            from app.config import get_settings
            from app.notifications.human_notify import notify_human
            settings = get_settings()
            await notify_human(
                conversation=conversation,
                rule_code=classification.handoff_rule,
                user_message=text,
                recent_turns=recent_turns,
                notify_channel=rule_row.notify_channel,
                notify_target=rule_row.notify_target or "",
                bot_token=settings.TELEGRAM_BOT_TOKEN,
            )

    elapsed = int((time.monotonic() - start) * 1000)

    # 10. Persist bot message
    await persist_message(
        conv_id, "bot", outbound.text, session,
        intent_id=classification.intent_id,
        matched_via=classification.matched_via,
        latency_ms=elapsed,
    )

    return PipelineResult(
        outbound=outbound,
        latency_ms=elapsed,
        conversation_id=conv_id,
        is_new_conversation=is_new,
    )


async def _tenant_slug(tenant_id: int, session: AsyncSession) -> str:
    row = (await session.execute(
        sa.text("SELECT slug FROM public.tenants WHERE id=:id"),
        {"id": tenant_id},
    )).fetchone()
    return row[0] if row else ""


async def _build_render_context(
    tenant_id: int,
    session: AsyncSession,
    recent_turns: list[dict],
    channel: str,
) -> dict:
    """Arma el contexto seguro para el render de templates."""
    from app.models.media import Media
    from app.models.offering import Offering

    offerings = (await session.execute(
        sa.select(Offering)
        .where(Offering.is_active.is_(True))
        .order_by(Offering.display_order, Offering.id)
    )).scalars().all()

    media_rows = (await session.execute(
        sa.select(Media).where(Media.is_active.is_(True))
    )).scalars().all()

    slug = await _tenant_slug(tenant_id, session)
    media_map = {m.key: f"/media/{slug}/{m.path}" for m in media_rows}

    return {
        "plans": [
            {
                "id": o.id, "slug": o.slug, "nombre": o.nombre,
                "descripcion": o.descripcion or "",
                "precio_cop": o.precio_cop,
                "incluye": list(o.incluye or []),
            }
            for o in offerings
        ],
        "recent_turns": [
            {"role": t.get("role"), "text": t.get("content_text") or ""}
            for t in (recent_turns or [])
        ],
        "channel": channel,
        "user": {},
        "_media_map": media_map,
    }
