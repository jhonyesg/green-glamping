"""System status page rendered with the platform's look (instead of raw JSON)."""

import time
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import __version__
from app.config import get_settings

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/status", tags=["admin-status"])
settings = get_settings()

_started_at = time.time()


@router.get("/", response_class=HTMLResponse)
async def status_page(request: Request):
    checks = []

    # Database
    db_ok, db_detail = False, ""
    t0 = time.monotonic()
    try:
        from app.db.session import engine
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
        db_ok = True
        db_detail = f"{round((time.monotonic() - t0) * 1000)}ms"
    except Exception as e:
        db_detail = str(e)[:120]
    checks.append({"name": "PostgreSQL", "ok": db_ok, "detail": db_detail})

    # Redis
    redis_ok, redis_detail = False, ""
    t0 = time.monotonic()
    try:
        await request.app.state.redis.ping()
        redis_ok = True
        redis_detail = f"{round((time.monotonic() - t0) * 1000)}ms"
    except Exception as e:
        redis_detail = str(e)[:120]
    checks.append({"name": "Redis", "ok": redis_ok, "detail": redis_detail})

    # Telegram token (fresco, por si se cambió en Ajustes)
    from app.config import get_settings as _gs
    tg_configured = bool(_gs().TELEGRAM_BOT_TOKEN)
    checks.append({
        "name": "Telegram bot token",
        "ok": tg_configured,
        "detail": "configurado" if tg_configured else "sin configurar",
        "fix_url": "/admin/settings", "fix_label": "Configurar en Ajustes",
    })

    # WhatsApp no oficial: estado del proveedor configurado en Canales
    wa_ok, wa_detail = False, "sin configurar"
    try:
        from app.admin.routes.channels import _load as _load_channels
        ch = (await _load_channels("green-glamping"))["channels"].get("whatsapp_unofficial", {})
        if ch.get("provider"):
            from app.channels.registry import get_adapter
            adapter = get_adapter("whatsapp_unofficial", ch)
            if hasattr(adapter, "get_status"):
                st = await adapter.get_status()
                wa_ok = st.get("status") == "connected"
                wa_detail = f"{ch['provider']}: {st.get('status', '?')}"
    except Exception as e:
        wa_detail = str(e)[:80]
    checks.append({
        "name": "WhatsApp (no oficial)", "ok": wa_ok, "detail": wa_detail,
        "fix_url": "/admin/channels", "fix_label": "Configurar en Canales",
    })

    # Tenants
    tenants = []
    try:
        from app.db.session import async_session_factory
        async with async_session_factory() as session:
            tenants = (await session.execute(sa.text(
                "SELECT slug, name, status, operation_mode FROM public.tenants ORDER BY id"
            ))).fetchall()
    except Exception:
        pass

    # Estado de los pollers de Telegram por tenant
    from app.channels.poller import poller_manager
    poller_states = poller_manager.status()
    poller_rows = [{"tenant": slug, "state": st} for slug, st in poller_states.items()]

    uptime_s = int(time.time() - _started_at)
    h, rem = divmod(uptime_s, 3600)
    m, s = divmod(rem, 60)

    all_ok = all(c["ok"] for c in checks[:2])  # DB + Redis are the critical ones

    return templates.TemplateResponse(request, "status.html", {
        "version": __version__,
        "checks": checks,
        "tenants": tenants,
        "poller_rows": poller_rows,
        "uptime": f"{h}h {m}m {s}s",
        "environment": settings.ENVIRONMENT,
        "all_ok": all_ok,
    })
