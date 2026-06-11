"""Core bot pipeline: anti_injection → memory → classify → respond → persist → send."""

import time
from dataclasses import dataclass
from datetime import UTC

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.anti_injection import check_injection
from app.bot.classifier import classify
from app.bot.handoff import is_in_handoff_pause, resume_conversation, should_resume, trigger_handoff
from app.bot.memory import get_or_create_conversation, get_recent_turns, persist_message
from app.bot.responder import OutboundMessage, build_response
from app.bot.response_parser import parse_llm_response, replace_prompt_leak
from app.core.template_render import render_response
from app.llm.prompts import build_response_prompt, extract_kb_payload
from app.llm.router import route_response_generation


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

    # 8a. LLM-first: si el modo está activo y el regex no es bypass,
    #     invocar al LLM con el contexto completo. Si el regex
    #     matchea con alta confianza (configurable), se ahorra el LLM.
    classification.conversation_id = conv_id  # type: ignore[attr-defined]
    llm_response = await _maybe_call_llm(
        text=text,
        tenant_id=tenant_id,
        session=session,
        cfg=cfg,
        recent_turns=recent_turns,
        regex_classification=classification,
    )
    if llm_response is not None:
        outbound.text = llm_response.response
        # Si el LLM detectó un intent de la KB existente, tomar su
        # handoff_rule y media adjuntos. Si no, mantener los del
        # regex match.
        if llm_response.intent and llm_response.intent != "fallback":
            try:
                await session.execute(sa.text(f'SET search_path TO "tenant_{_tenant_slug(tenant_id, session)}", public'))
                row = (await session.execute(
                    sa.text(
                        "SELECT handoff_rule, response_media_ids, requires_human "
                        "FROM kb_intents WHERE intent_name=:n"
                    ),
                    {"n": llm_response.intent},
                )).fetchone()
                if row is not None:
                    if row.handoff_rule:
                        outbound.handoff_rule = row.handoff_rule
                    if row.response_media_ids:
                        import json as _json
                        if isinstance(row.response_media_ids, str):
                            ids = _json.loads(row.response_media_ids)
                        else:
                            ids = row.response_media_ids
                        outbound.media_attachments = [int(x) for x in ids if x]
                    if row.requires_human:
                        llm_response.requires_human = True
            except Exception as e:
                logger.warning(f"llm_intent_lookup_failed intent={llm_response.intent} error={e}")
        if llm_response.requires_human:
            outbound.requires_human = True
        if llm_response.handoff_rule:
            outbound.handoff_rule = llm_response.handoff_rule
        # Adjuntar media_keys mencionados por el LLM (los resolvemos a ids después)
        # Por ahora los guardamos en outbound.text con un marker; el webhook
        # de Telegram los podría usar. v1: solo si el intent existe en KB.
        outbound.intent_name = llm_response.intent
        # Actualizar el intent_id del classification para métricas
        classification.intent_name = llm_response.intent
        classification.matched_via = "llm"

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


async def _check_llm_rate_limit(
    session, conversation_id: int, max_per_hour: int
) -> bool:
    """Retorna True si está OK invocar el LLM (count < max).

    Función separada para facilitar el mocking en tests.
    """
    from datetime import datetime, timedelta
    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    count = (await session.execute(
        sa.text(
            "SELECT COUNT(*) FROM messages "
            "WHERE conversation_id=:cid AND role='assistant' "
            "AND matched_via='llm' AND created_at >= :since"
        ),
        {"cid": conversation_id, "since": one_hour_ago},
    )).scalar() or 0
    return count < max_per_hour


async def _maybe_call_llm(
    text: str,
    tenant_id: int,
    session,
    cfg: dict,
    recent_turns: list[dict],
    regex_classification,
):
    """
    Decide si invocar al LLM y devuelve un LLMResponse parseado, o None.

    Reglas:
    1. Si `llm_strategy.mode == "regex_first"`, skip.
    2. Si el regex matchea con score > bypass_threshold y no hay
       ambigüedad, skip (ahorrar tokens).
    3. Si excedió el rate limit por conversación, skip.
    4. Construye el KB payload + system prompt y llama al LLM.
    5. Parsea el JSON con parse_llm_response.
    6. Si el LLM falla (parse, no provider, timeout), skip
       silenciosamente. La pipeline sigue con el regex match.
    """
    llm_strategy = cfg.get("llm_strategy") or {}
    mode = llm_strategy.get("mode", "regex_first")

    # 1. Modo legacy
    if mode == "regex_first":
        return None

    # 2. Bypass con regex de alta confianza
    bypass = llm_strategy.get("bypass_llm_on_high_regex_score", True)
    threshold = float(llm_strategy.get("bypass_threshold", 0.9))
    if (
        bypass
        and regex_classification.matched_via == "regex"
        and regex_classification.score > threshold
        and not regex_classification.is_ambiguous
    ):
        return None

    # 3. Rate limit por conversación
    max_per_hour = int(llm_strategy.get("max_llm_calls_per_conversation_per_hour", 20))
    if max_per_hour > 0 and session is not None:
        try:
            rate_ok = await _check_llm_rate_limit(
                session, regex_classification.conversation_id
                if hasattr(regex_classification, "conversation_id") else 0,
                max_per_hour,
            )
            if not rate_ok:
                logger.warning(
                    f"llm_rate_limit_hit conv={regex_classification.conversation_id} max={max_per_hour}"
                )
                return None
        except Exception as e:
            logger.warning(f"llm_rate_limit_check_failed error={e}")
            # Si falla el check, dejar pasar (fail-open)

    # 4. Construir KB payload desde el schema del tenant
    try:
        kb_payload = await _load_kb_for_llm(tenant_id, session, recent_turns, cfg)
    except Exception as e:
        logger.warning(f"llm_kb_load_failed error={e}")
        return None

    # 5. System + user prompts
    tenant_name = cfg.get("_tenant_name", "el negocio")
    system, user = build_response_prompt(
        tenant_name=tenant_name,
        kb_payload=kb_payload,
        message=text,
        recent_turns=recent_turns,
        n_turns=int(cfg.get("memory_turns", 10)),
    )

    # 6. Llamada al LLM
    try:
        llm_resp = await route_response_generation(
            system_prompt=system,
            user_prompt=user,
            tenant_id=tenant_id,
            session=session,
        )
    except Exception as e:
        logger.warning(f"llm_call_failed error={e}")
        return None

    # 7. Parse
    parsed = parse_llm_response(llm_resp.text)
    if parsed is None:
        logger.warning(f"llm_parse_failed raw={llm_resp.text[:200]}")
        return None

    # 8. Prompt leak
    if parsed.prompt_leak_detected:
        logger.warning(f"prompt_leak_detected response={parsed.response[:200]}")
        parsed = replace_prompt_leak(parsed)

    return parsed


async def _load_kb_for_llm(
    tenant_id: int, session, recent_turns: list[dict], cfg: dict
) -> dict:
    """Carga el KB payload para inyectar en el prompt del LLM."""

    schema = f"tenant_{await _tenant_slug(tenant_id, session)}"
    await session.execute(sa.text(f'SET search_path TO "{schema}", public'))

    # Intents activos (resumidos: name + description + examples)
    intent_rows = (await session.execute(
        sa.text(
            "SELECT intent_name, response_text, keywords_regex "
            "FROM kb_intents WHERE status='active' "
            "ORDER BY priority DESC, intent_name LIMIT 50"
        )
    )).fetchall()
    intents = []
    for r in intent_rows:
        # Usar el nombre y una descripción corta (no el regex completo, eso es del clasificador)
        intents.append({
            "name": r.intent_name,
            "description": (r.response_text or "")[:200],
            "examples": [],  # Se puede popular después con un dataset
        })

    # Handoff rules activas
    handoff_rows = (await session.execute(
        sa.text(
            "SELECT rule_code, trigger_intent, custom_message "
            "FROM handoff_rules WHERE is_active=true"
        )
    )).fetchall()
    handoff_rules = [
        {"code": r.rule_code, "trigger": r.trigger_intent, "message": r.custom_message}
        for r in handoff_rows
    ]

    # Reusar _build_render_context para los planes
    render_ctx = await _build_render_context(tenant_id, session, recent_turns, channel="telegram")
    plans = render_ctx.get("plans", [])

    # Media keys activas
    media_rows = (await session.execute(
        sa.text("SELECT key FROM media WHERE is_active=true LIMIT 100")
    )).fetchall()
    media_keys = [r[0] for r in media_rows]

    return extract_kb_payload(
        plans=plans,
        intents=intents,
        handoff_rules=handoff_rules,
        media_keys=media_keys,
    )
