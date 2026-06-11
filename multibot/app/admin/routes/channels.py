"""Channel configuration per tenant: Telegram + WhatsApp (Evolution/Baileys/WAHA)."""

import json
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.security import decrypt_credentials, encrypt_credentials
from app.db.session import async_session_factory

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/channels", tags=["admin-channels"])

WA_PROVIDERS = {
    "evolution": {
        "label": "Evolution API (recomendado)",
        "hint": "Gateway open-source muy usado en LATAM. Se despliega con docker (carpeta whatsapp-evolution/). Multi-instancia, QR por API, webhooks.",
        "default_url": "http://localhost:8080",
    },
    "baileys": {
        "label": "Puente Baileys propio",
        "hint": "Microservicio Node.js incluido en este proyecto (carpeta whatsapp-nooficial/). Ligero, una sesión.",
        "default_url": "http://localhost:3001",
    },
    "waha": {
        "label": "WAHA",
        "hint": "WhatsApp HTTP API (devlikeapro/waha). Imagen docker lista, API REST estable.",
        "default_url": "http://localhost:3000",
    },
}


def _decrypt_channel(row) -> dict:
    creds = row.credentials or {}
    if isinstance(creds, str):
        creds = json.loads(creds)
    if "encrypted" in creds:
        try:
            return decrypt_credentials(creds["encrypted"])
        except Exception:
            return {}
    return creds


async def _load(tenant: str) -> dict:
    schema = f"tenant_{tenant}"
    channels, tenants = {}, []
    async with async_session_factory() as session:
        tenants = (await session.execute(sa.text(
            "SELECT slug, name FROM public.tenants WHERE status='active' ORDER BY slug"
        ))).fetchall()
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            rows = (await session.execute(sa.text(
                "SELECT id, type, credentials, is_active FROM channels ORDER BY id"
            ))).fetchall()
            for r in rows:
                channels[r.type] = {"id": r.id, "is_active": r.is_active, **_decrypt_channel(r)}
        except Exception:
            pass
    return {"channels": channels, "tenants": tenants}


async def _upsert(tenant: str, ch_type: str, creds: dict):
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        tenant_row = (await session.execute(
            sa.text("SELECT id FROM public.tenants WHERE slug=:s"), {"s": tenant}
        )).fetchone()
        if not tenant_row:
            return
        payload = json.dumps({"encrypted": encrypt_credentials(creds)})
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        existing = (await session.execute(
            sa.text("SELECT id FROM channels WHERE type=:t LIMIT 1"), {"t": ch_type}
        )).fetchone()
        if existing:
            await session.execute(
                sa.text("UPDATE channels SET credentials=CAST(:c AS jsonb), is_active=true WHERE id=:id"),
                {"c": payload, "id": existing.id},
            )
        else:
            await session.execute(
                sa.text(
                    "INSERT INTO channels (tenant_id, type, credentials, is_active) "
                    "VALUES (:tid, :t, CAST(:c AS jsonb), true)"
                ),
                {"tid": tenant_row.id, "t": ch_type, "c": payload},
            )
        await session.commit()


@router.get("/", response_class=HTMLResponse)
async def channels_view(request: Request, tenant: str = "green-glamping"):
    ctx = await _load(tenant)

    # Estado en vivo del proveedor de WhatsApp configurado
    wa = ctx["channels"].get("whatsapp_unofficial", {})
    wa_status = None
    if wa.get("provider"):
        try:
            from app.channels.registry import get_adapter
            adapter = get_adapter("whatsapp_unofficial", wa)
            if hasattr(adapter, "get_status"):
                wa_status = await adapter.get_status()
        except Exception as e:
            wa_status = {"status": "error", "error": str(e)[:80]}

    # Destino de prueba + estado del poller
    async with async_session_factory() as session:
        row = (await session.execute(
            sa.text("SELECT bot_config FROM public.tenants WHERE slug=:s"), {"s": tenant}
        )).fetchone()
    bot_cfg = (row.bot_config or {}) if row else {}
    test_destination = bot_cfg.get("test_destination", {})

    from app.channels.poller import poller_manager
    from app.admin.channel_info import CHANNEL_INFO

    return templates.TemplateResponse(request, "channels/index.html", {
        "tenant": tenant, "wa_providers": WA_PROVIDERS, "wa_status": wa_status,
        "saved": request.query_params.get("saved"),
        "warn": request.query_params.get("warn"),
        "test_destination": test_destination,
        "poller_state": poller_manager.state_of(tenant),
        "channel_info": CHANNEL_INFO,
        **ctx,
    })


@router.post("/telegram")
async def save_telegram(
    request: Request,
    tenant: str = Form(...),
    bot_token: str = Form(""),
    secret_token: str = Form(""),
    transport: str = Form("auto"),
):
    await _upsert(tenant, "telegram", {
        "bot_token": bot_token.strip(),
        "secret_token": secret_token.strip(),
        "transport": transport,
    })

    # Validación nivel 0 (no bloquea) + "lo agrego y queda habilitado"
    from app.channels.telegram import token_shape_problem
    problem = token_shape_problem(bot_token)
    extra = f"&warn={problem}" if problem else ""
    if not problem and bot_token.strip():
        from app.channels.poller import sync_tenant_poller
        try:
            await sync_tenant_poller(tenant)
        except Exception:
            pass

    return RedirectResponse(
        f"/admin/channels?tenant={tenant}&saved=telegram{extra}", status_code=303
    )


# ─── Pruebas de canal ───────────────────────────────────────────────

@router.post("/test/{ch_type}")
async def test_channel(request: Request, ch_type: str, tenant: str = Form(...)):
    """Nivel 1: verificación de credenciales/estado contra la API real."""
    data = await _load(tenant)
    creds = data["channels"].get(ch_type if ch_type != "whatsapp" else "whatsapp_unofficial", {})

    if ch_type == "telegram":
        from app.channels.telegram import TelegramAdapter, token_shape_problem
        token = creds.get("bot_token", "")
        if not token:
            return {"ok": False, "error": "No hay token guardado"}
        problem = token_shape_problem(token)
        if problem:
            return {"ok": False, "error": problem}

        adapter = TelegramAdapter(bot_token=token)
        me = await adapter.get_me()
        if not me.get("ok"):
            return {"ok": False, "error": f"Telegram no reconoce este token ({me.get('error')}). Revísalo en @BotFather"}

        wh = await adapter.get_webhook_info()
        from app.channels.poller import poller_manager
        result = {
            "ok": True,
            "detail": f"Bot verificado: @{me['username']} ({me['first_name']})",
            "webhook_url": wh.get("url", ""),
            "webhook_error": wh.get("last_error", ""),
            "pending": wh.get("pending", 0),
            "poller": poller_manager.state_of(tenant),
        }
        if wh.get("url"):
            result["foreign_webhook"] = True
            result["warning"] = (
                f"⚠ Este bot está conectado a otra plataforma: {wh['url']}"
                + (f" (último error: {wh['last_error']})" if wh.get("last_error") else "")
            )
        return result

    if ch_type == "whatsapp":
        provider = creds.get("provider", "")
        if not provider:
            return {"ok": False, "error": "No hay proveedor de WhatsApp configurado"}
        try:
            from app.channels.registry import get_adapter
            adapter = get_adapter("whatsapp_unofficial", creds)
            st = await adapter.get_status() if hasattr(adapter, "get_status") else {"status": "?"}
        except Exception as e:
            return {"ok": False, "error": f"No se pudo conectar a {creds.get('base_url')}: {str(e)[:80]}. ¿Está corriendo el servicio?"}

        status = st.get("status", "?")
        if status == "connected":
            return {"ok": True, "detail": f"{provider}: número vinculado y conectado ✓"}
        if status in ("close", "connecting", "qr_pending"):
            return {"ok": False, "error": f"{provider}: la instancia existe pero el número no está vinculado — escanea el QR", "needs_qr": True}
        return {"ok": False, "error": f"{provider}: {status}. ¿Está corriendo el docker en {creds.get('base_url')}?"}

    if ch_type == "whatsapp_official":
        wa = data["channels"].get("whatsapp_official", {})
        if not wa.get("access_token") or not wa.get("phone_number_id"):
            return {"ok": False, "error": "Faltan Phone Number ID o Access Token"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://graph.facebook.com/v19.0/{wa['phone_number_id']}",
                    headers={"Authorization": f"Bearer {wa['access_token']}"},
                )
                d = resp.json()
            if resp.status_code == 200:
                return {"ok": True, "detail": f"Número verificado: {d.get('display_phone_number', d.get('id'))}"}
            return {"ok": False, "error": d.get("error", {}).get("message", f"HTTP {resp.status_code}")}
        except Exception as e:
            return {"ok": False, "error": str(e)[:100]}

    return {"ok": False, "error": f"Tipo desconocido: {ch_type}"}


@router.post("/takeover/telegram")
async def takeover_telegram(request: Request, tenant: str = Form(...)):
    """Borra el webhook ajeno (conservando pendientes) y activa el transporte configurado."""
    data = await _load(tenant)
    creds = data["channels"].get("telegram", {})
    token = creds.get("bot_token", "")
    if not token:
        return {"ok": False, "error": "No hay token guardado"}

    from app.channels.telegram import TelegramAdapter
    adapter = TelegramAdapter(bot_token=token)
    result = await adapter.delete_webhook(drop_pending=False)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("description", "deleteWebhook falló")}

    from app.channels.poller import sync_tenant_poller, poller_manager
    await sync_tenant_poller(tenant)
    return {"ok": True, "detail": "Control tomado. Webhook ajeno eliminado.", "poller": poller_manager.state_of(tenant)}


@router.post("/test-destination")
async def save_test_destination(
    request: Request,
    tenant: str = Form(...),
    telegram_chat_id: str = Form(""),
    whatsapp_number: str = Form(""),
):
    import json as _json
    async with async_session_factory() as session:
        row = (await session.execute(
            sa.text("SELECT id, bot_config FROM public.tenants WHERE slug=:s"), {"s": tenant}
        )).fetchone()
        if row:
            cfg = dict(row.bot_config or {})
            cfg["test_destination"] = {
                "telegram_chat_id": telegram_chat_id.strip(),
                "whatsapp_number": whatsapp_number.strip(),
            }
            await session.execute(
                sa.text("UPDATE public.tenants SET bot_config=CAST(:c AS jsonb) WHERE id=:id"),
                {"c": _json.dumps(cfg), "id": row.id},
            )
            await session.commit()
    return RedirectResponse(f"/admin/channels?tenant={tenant}&saved=destino", status_code=303)


@router.post("/test-e2e/{ch_type}")
async def test_e2e(request: Request, ch_type: str, tenant: str = Form(...)):
    """Nivel 2: mensaje simulado por el pipeline completo → respuesta real al destino de prueba."""
    async with async_session_factory() as session:
        row = (await session.execute(
            sa.text("SELECT bot_config FROM public.tenants WHERE slug=:s"), {"s": tenant}
        )).fetchone()
    dest = ((row.bot_config or {}) if row else {}).get("test_destination", {})

    if ch_type == "telegram":
        chat_id = dest.get("telegram_chat_id", "")
        if not chat_id:
            return {"ok": False, "error": "Configura primero el chat de prueba (tu chat_id de Telegram — pídelo a @userinfobot)", "needs_destination": True}

        fake_update = {
            "update_id": 0,
            "message": {
                "message_id": 0,
                "date": 0,
                "chat": {"id": int(chat_id), "type": "private"},
                "from": {"id": int(chat_id), "is_bot": False, "first_name": "Prueba E2E"},
                "text": "hola",
            },
        }
        from app.api.webhooks import handle_telegram_update
        result = await handle_telegram_update(tenant, fake_update)
        if result.get("status") == "ok":
            return {"ok": True, "detail": f"✓ Pipeline completo OK — intent [{result.get('intent')}] en {result.get('latency_ms')}ms. Revisa tu Telegram: la respuesta llegó allá.", **result}
        return {"ok": False, "error": f"El pipeline respondió: {result.get('status')} {result.get('detail', '')}"}

    if ch_type == "whatsapp":
        number = dest.get("whatsapp_number", "")
        if not number:
            return {"ok": False, "error": "Configura primero el número de prueba de WhatsApp", "needs_destination": True}
        data = await _load(tenant)
        creds = data["channels"].get("whatsapp_unofficial", {})
        try:
            from app.channels.registry import get_adapter
            from app.channels.base import OutboundMessage, ContentType
            adapter = get_adapter("whatsapp_unofficial", creds)
            r = await adapter.send(OutboundMessage(
                thread_id=number, text="✅ Prueba de Multibot: el canal de WhatsApp está configurado correctamente.",
                content_type=ContentType.text,
            ))
            if r.success:
                return {"ok": True, "detail": f"Mensaje de prueba enviado a {number} — revisa ese WhatsApp"}
            return {"ok": False, "error": r.error or "envío falló"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:100]}

    return {"ok": False, "error": f"Tipo desconocido: {ch_type}"}


@router.post("/whatsapp")
async def save_whatsapp(
    request: Request,
    tenant: str = Form(...),
    provider: str = Form("evolution"),
    base_url: str = Form(""),
    api_key: str = Form(""),
    instance: str = Form("multibot"),
):
    await _upsert(tenant, "whatsapp_unofficial", {
        "provider": provider,
        "base_url": base_url.strip() or WA_PROVIDERS.get(provider, {}).get("default_url", ""),
        "api_key": api_key.strip(),
        "instance": instance.strip() or "multibot",
    })
    return RedirectResponse(f"/admin/channels?tenant={tenant}&saved=whatsapp", status_code=303)


@router.post("/whatsapp_official")
async def save_whatsapp_official(
    request: Request,
    tenant: str = Form(...),
    phone_number_id: str = Form(""),
    access_token: str = Form(""),
    app_secret: str = Form(""),
):
    await _upsert(tenant, "whatsapp_official", {
        "phone_number_id": phone_number_id.strip(),
        "access_token": access_token.strip(),
        "app_secret": app_secret.strip(),
    })
    return RedirectResponse(f"/admin/channels?tenant={tenant}&saved=whatsapp_official", status_code=303)
