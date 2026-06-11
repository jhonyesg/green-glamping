"""Visual pipeline flow view (n8n-style) with the tenant's live, editable configuration."""

import json
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.admin.auth_utils import effective_tenant
from app.db.session import async_session_factory

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/flow", tags=["admin-flow"])


@router.get("/", response_class=HTMLResponse)
async def flow_view(request: Request, tenant: str = "green-glamping"):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"

    from app.bot.anti_injection import _INJECTION_PATTERNS
    from app.bot.handoff import LONG_PAUSE_HOURS, SHORT_PAUSE_HOURS

    cfg = {
        "tenant_name": tenant,
        "mode": "—",
        "intents_total": 0,
        "intents_handoff": 0,
        "handoff_rules": [],
        "short_pause": SHORT_PAUSE_HOURS,
        "long_pause": LONG_PAUSE_HOURS,
        "injection_patterns": len(_INJECTION_PATTERNS),
        "memory_turns": 10,
        "conversations": 0,
        "messages": 0,
        "llm_providers": 0,
    }

    bot_cfg = {}
    async with async_session_factory() as session:
        try:
            row = (await session.execute(
                sa.text("SELECT name, operation_mode, bot_config FROM public.tenants WHERE slug=:s"),
                {"s": tenant},
            )).fetchone()
            if row:
                cfg["tenant_name"] = row.name
                cfg["mode"] = row.operation_mode
                bot_cfg = row.bot_config or {}

            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            cfg["intents_total"] = (await session.execute(
                sa.text("SELECT COUNT(*) FROM kb_intents WHERE status='active'")
            )).scalar() or 0
            cfg["intents_handoff"] = (await session.execute(
                sa.text("SELECT COUNT(*) FROM kb_intents WHERE status='active' AND requires_human=true")
            )).scalar() or 0
            cfg["handoff_rules"] = (await session.execute(
                sa.text("SELECT rule_code, notify_channel, COALESCE(notify_target,'') AS target "
                        "FROM handoff_rules WHERE is_active=true ORDER BY priority DESC")
            )).fetchall()
            cfg["conversations"] = (await session.execute(
                sa.text("SELECT COUNT(*) FROM conversations")
            )).scalar() or 0
            cfg["llm_providers"] = (await session.execute(
                sa.text("SELECT COUNT(*) FROM llm_providers WHERE is_active=true")
            )).scalar() or 0
            cfg["messages"] = (await session.execute(
                sa.text("SELECT COUNT(*) FROM messages")
            )).scalar() or 0
        except Exception:
            pass

    # Effective values: tenant config overrides defaults
    cfg["anti_injection_enabled"] = bot_cfg.get("anti_injection_enabled", True)
    cfg["memory_enabled"] = bot_cfg.get("memory_enabled", True)
    cfg["memory_turns"] = bot_cfg.get("memory_turns", cfg["memory_turns"])
    cfg["short_pause"] = bot_cfg.get("short_pause_hours", cfg["short_pause"])
    cfg["long_pause"] = bot_cfg.get("long_pause_hours", cfg["long_pause"])
    cfg["fallback_response"] = bot_cfg.get("fallback_response", "")
    cfg["injection_response"] = bot_cfg.get("injection_response", "")
    cfg["handoff_silence_response"] = bot_cfg.get("handoff_silence_response", "")

    # Humanización: defaults seguros si no existe
    from app.bot.humanizer import default_humanization
    hz = bot_cfg.get("humanization")
    if not isinstance(hz, dict):
        hz = default_humanization()
    cfg["humanization"] = hz

    return templates.TemplateResponse(request, "flow/index.html", {
        "tenant": tenant, "cfg": cfg,
    })


@router.post("/config")
async def save_config(
    request: Request,
    tenant: str = Form("green-glamping"),
    section: str = Form(...),
    anti_injection_enabled: bool = Form(False),
    injection_response: str = Form(""),
    memory_enabled: bool = Form(False),
    memory_turns: int = Form(10),
    short_pause_hours: int = Form(12),
    long_pause_hours: int = Form(48),
    handoff_silence_response: str = Form(""),
    fallback_response: str = Form(""),
    humanization_enabled: str = Form("false"),
    humanization_channels: str = Form("whatsapp_unofficial"),
    humanization_split_bubbles: str = Form("true"),
    humanization_max_bubbles: int = Form(4),
    humanization_wpm: int = Form(40),
    humanization_typing_min_ms: int = Form(800),
    humanization_typing_max_ms: int = Form(6000),
    humanization_pause_min_ms: int = Form(600),
    humanization_pause_max_ms: int = Form(2200),
):
    """Update one section of the tenant's bot_config (merges with existing JSON)."""
    tenant = effective_tenant(request, tenant)

    async with async_session_factory() as session:
        row = (await session.execute(
            sa.text("SELECT id, bot_config FROM public.tenants WHERE slug=:s"), {"s": tenant}
        )).fetchone()
        if not row:
            return RedirectResponse(f"/admin/flow?tenant={tenant}", status_code=303)

        cfg = dict(row.bot_config or {})

        if section == "injection":
            cfg["anti_injection_enabled"] = anti_injection_enabled
            cfg["injection_response"] = injection_response.strip()
        elif section == "memory":
            cfg["memory_enabled"] = memory_enabled
            cfg["memory_turns"] = max(1, min(50, memory_turns))
        elif section == "handoff":
            cfg["short_pause_hours"] = max(1, min(168, short_pause_hours))
            cfg["long_pause_hours"] = max(1, min(336, long_pause_hours))
            cfg["handoff_silence_response"] = handoff_silence_response.strip()
        elif section == "classifier":
            cfg["fallback_response"] = fallback_response.strip()
        elif section == "humanization":
            # Parsear canales como lista CSV
            channels = [c.strip() for c in humanization_channels.split(",") if c.strip()]
            cfg["humanization"] = {
                "enabled": humanization_enabled == "true",
                "channels": channels or ["whatsapp_unofficial"],
                "split_bubbles": humanization_split_bubbles == "true",
                "max_bubbles": max(1, min(20, humanization_max_bubbles)),
                "wpm": max(5, min(300, humanization_wpm)),
                "typing_min_ms": max(0, min(60_000, humanization_typing_min_ms)),
                "typing_max_ms": max(0, min(60_000, humanization_typing_max_ms)),
                "pause_min_ms": max(0, min(60_000, humanization_pause_min_ms)),
                "pause_max_ms": max(0, min(60_000, humanization_pause_max_ms)),
            }

        await session.execute(
            sa.text("UPDATE public.tenants SET bot_config = CAST(:c AS jsonb) WHERE id = :id"),
            {"c": json.dumps(cfg), "id": row.id},
        )
        await session.commit()

    return RedirectResponse(f"/admin/flow?tenant={tenant}&saved={section}", status_code=303)
