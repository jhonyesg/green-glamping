import json

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import ContentType
from app.channels.telegram import TelegramAdapter
from app.config import get_settings
from app.core.tenant import get_tenant_by_slug
from app.db.session import get_session

router = APIRouter(prefix="/webhook", tags=["webhooks"])
settings = get_settings()


async def _get_channel_creds(session: AsyncSession, tenant_slug: str, ch_type: str) -> dict:
    """Credenciales del canal del tenant (descifradas), {} si no hay."""
    import json as _json

    from app.core.security import decrypt_credentials
    try:
        await session.execute(sa.text(f'SET search_path TO "tenant_{tenant_slug}", public'))
        row = (await session.execute(
            sa.text("SELECT credentials FROM channels WHERE type=:t AND is_active=true LIMIT 1"),
            {"t": ch_type},
        )).fetchone()
        if not row:
            return {}
        creds = row.credentials or {}
        if isinstance(creds, str):
            creds = _json.loads(creds)
        if "encrypted" in creds:
            return decrypt_credentials(creds["encrypted"])
        return creds
    except Exception:
        return {}


async def _run_pipeline(tenant_slug: str, tenant_id: int, text: str, session: AsyncSession,
                        thread_id: str, user_id: str, push_name: str | None):
    cfg_row = (await session.execute(
        sa.text("SELECT bot_config FROM public.tenants WHERE id = :tid"), {"tid": tenant_id}
    )).fetchone()
    bot_config = (cfg_row.bot_config or {}) if cfg_row else {}

    await session.execute(sa.text(f'SET search_path TO "tenant_{tenant_slug}", public'))
    from app.bot.pipeline import process
    return await process(
        text=text,
        tenant_id=tenant_id,
        session=session,
        external_thread_id=thread_id,
        user_external_id=user_id,
        push_name=push_name,
        config=bot_config,
    )


async def handle_telegram_update(tenant_slug: str, payload: dict) -> dict:
    """
    Procesa un update de Telegram por el pipeline y envía la respuesta.
    Compartido por: webhook, poller (polling) y prueba end-to-end.
    Crea su propia sesión — no requiere contexto de request.
    """
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        tenant = await get_tenant_by_slug(tenant_slug, session)
        if tenant is None:
            return {"status": "tenant_not_found"}

        tg_creds = await _get_channel_creds(session, tenant_slug, "telegram")
        bot_token = tg_creds.get("bot_token") or get_settings().TELEGRAM_BOT_TOKEN
        if not bot_token:
            return {"status": "no_token"}

        try:
            adapter = TelegramAdapter(bot_token=bot_token)
            inbound = adapter.parse_inbound(payload)
            inbound.tenant_slug = tenant_slug
        except Exception as exc:
            return {"status": "parse_error", "detail": str(exc)}

        if inbound.content.text is None:
            return {"status": "ok", "note": "non-text message ignored"}

        try:
            result = await _run_pipeline(
                tenant_slug, tenant.id, inbound.content.text, session,
                inbound.external_thread_id, inbound.user_external_id, inbound.push_name,
            )
        except Exception as exc:
            logger.exception(f"Pipeline error: {exc}")
            return {"status": "pipeline_error"}

        from app.bot.humanizer import send_humanized
        await send_humanized(
            adapter, inbound.external_thread_id, result.outbound.text,
            tenant_id=tenant.id, channel_type="telegram", session=session,
        )

        # Media adjuntos del intent: descargar de la biblioteca y enviar
        if result.outbound.media_attachments:
            await _send_attached_media(
                tenant, session, adapter, inbound.external_thread_id,
                result.outbound.media_attachments,
            )

        return {
            "status": "ok",
            "latency_ms": result.latency_ms,
            "intent": result.outbound.intent_name,
            "media_sent": len(result.outbound.media_attachments),
        }


async def _send_attached_media(
    tenant, session, adapter, thread_id: str, media_ids: list[int]
) -> None:
    """Descarga media de la biblioteca del tenant y los envía al thread."""
    from loguru import logger as _log

    from app.channels.base import OutboundMessage

    if not media_ids:
        return
    schema = f"tenant_{tenant.slug}"
    try:
        await session.execute(__import__("sqlalchemy").text(
            f'SET search_path TO "{schema}", public'
        ))
        rows = (await session.execute(
            __import__("sqlalchemy").text(
                "SELECT id, key, tipo, path, mime_type FROM media "
                "WHERE id = ANY(:ids) AND is_active=true"
            ),
            {"ids": list(media_ids)},
        )).fetchall()
    except Exception as e:
        _log.warning(f"media_attach_lookup_failed ids={media_ids} error={e}")
        return

    for row in rows:
        # Construir URL pública del archivo en /media/<slug>/<path>
        # y enviar como link. Para imágenes podemos descargar y enviar como file;
        # para audios, lo mismo. Para simplificar en esta versión, enviamos
        # el path absoluto al server para que el adapter pueda manejarlo.
        try:
            await adapter.send(OutboundMessage(
                thread_id=thread_id,
                text=f"[Adjunto: {row.key}]",
                content_type=ContentType.text,
            ))
        except Exception as e:
            _log.warning(f"media_attach_send_failed key={row.key} error={e}")


@router.post("/telegram/{tenant_slug}")
async def telegram_webhook(tenant_slug: str, request: Request):
    body = await request.body()
    try:
        payload = json.loads(body)
    except Exception:
        return JSONResponse({"status": "bad_json"}, status_code=400)
    result = await handle_telegram_update(tenant_slug, payload)
    if result.get("status") == "tenant_not_found":
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_slug}' not found")
    return JSONResponse(result)


@router.post("/whatsapp_official/{tenant_slug}")
async def whatsapp_official_webhook(
    tenant_slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    tenant = await get_tenant_by_slug(tenant_slug, session)
    if tenant is None:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_slug}' not found")

    try:
        payload = json.loads(body)
    except Exception:
        return JSONResponse({"status": "bad_json"}, status_code=400)

    # Guard: only process message events
    try:
        change = payload["entry"][0]["changes"][0]
        if change.get("field") != "messages":
            return JSONResponse({"status": "ok"})
    except (KeyError, IndexError):
        return JSONResponse({"status": "ok"})

    # Load tenant WhatsApp config
    row = (await session.execute(
        sa.text(
            "SELECT credentials FROM public.tenant_channels "
            "WHERE tenant_id=:tid AND type='whatsapp_official' AND is_active=true LIMIT 1"
        ),
        {"tid": tenant.id},
    )).fetchone() if False else None  # table lives in tenant schema; skip for now

    from app.channels.whatsapp_official import WhatsAppOfficialAdapter
    adapter = WhatsAppOfficialAdapter(
        phone_number_id="",
        access_token="",
        app_secret="",
    )

    inbound = adapter.parse_inbound(payload)
    if inbound is None or inbound.content.text is None:
        return JSONResponse({"status": "ok"})

    try:
        result = await _run_pipeline(
            tenant_slug, tenant.id, inbound.content.text, session,
            inbound.external_thread_id, inbound.user_external_id, inbound.push_name,
        )
    except Exception as exc:
        logger.exception(f"WA pipeline error: {exc}")
        return JSONResponse({"status": "pipeline_error"})

    return JSONResponse({"status": "ok", "latency_ms": result.latency_ms})


@router.get("/whatsapp_official/{tenant_slug}")
async def whatsapp_official_verify(tenant_slug: str, request: Request):
    """Meta webhook verification challenge."""
    params = request.query_params
    mode = params.get("hub.mode")
    challenge = params.get("hub.challenge", "")
    if mode == "subscribe":
        return PlainTextResponse(challenge)
    return JSONResponse({"status": "ok"})


@router.post("/whatsapp_unofficial/{tenant_slug}")
async def whatsapp_unofficial_webhook(
    tenant_slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Receive inbound messages forwarded from the Node.js Baileys bridge."""
    body = await request.body()
    tenant = await get_tenant_by_slug(tenant_slug, session)
    if tenant is None:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_slug}' not found")

    try:
        payload = json.loads(body)
    except Exception:
        return JSONResponse({"status": "bad_json"}, status_code=400)

    from app.channels.whatsapp_unofficial import WhatsAppUnofficialAdapter
    adapter = WhatsAppUnofficialAdapter()
    inbound = adapter.parse_inbound(payload)

    if not inbound.content.text:
        return JSONResponse({"status": "ok"})

    try:
        result = await _run_pipeline(
            tenant_slug, tenant.id, inbound.content.text, session,
            inbound.external_thread_id, inbound.user_external_id, inbound.push_name,
        )
    except Exception as exc:
        logger.exception(f"WA unofficial pipeline error: {exc}")
        return JSONResponse({"status": "pipeline_error"})

    from app.bot.humanizer import send_humanized
    await send_humanized(
        adapter, inbound.external_thread_id, result.outbound.text,
        tenant_id=tenant.id, channel_type="whatsapp_unofficial", session=session,
    )
    return JSONResponse({"status": "ok", "latency_ms": result.latency_ms})


@router.post("/whatsapp_evolution/{tenant_slug}")
async def whatsapp_evolution_webhook(
    tenant_slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Webhook de Evolution API (evento messages.upsert)."""
    body = await request.body()
    tenant = await get_tenant_by_slug(tenant_slug, session)
    if tenant is None:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_slug}' not found")

    try:
        payload = json.loads(body)
    except Exception:
        return JSONResponse({"status": "bad_json"}, status_code=400)

    wa_creds = await _get_channel_creds(session, tenant_slug, "whatsapp_unofficial")
    from app.channels.evolution import EvolutionAPIAdapter
    adapter = EvolutionAPIAdapter(
        base_url=wa_creds.get("base_url", "http://localhost:8080"),
        api_key=wa_creds.get("api_key", ""),
        instance=wa_creds.get("instance", "multibot"),
    )

    inbound = adapter.parse_inbound(payload)
    if inbound is None or not inbound.content.text:
        return JSONResponse({"status": "ok", "note": "evento ignorado"})

    try:
        result = await _run_pipeline(
            tenant_slug, tenant.id, inbound.content.text, session,
            inbound.external_thread_id, inbound.user_external_id, inbound.push_name,
        )
    except Exception as exc:
        logger.exception(f"Evolution pipeline error: {exc}")
        return JSONResponse({"status": "pipeline_error"})

    from app.bot.humanizer import send_humanized
    await send_humanized(
        adapter, inbound.external_thread_id, result.outbound.text,
        tenant_id=tenant.id, channel_type="whatsapp_unofficial", session=session,
    )
    return JSONResponse({"status": "ok", "latency_ms": result.latency_ms})
