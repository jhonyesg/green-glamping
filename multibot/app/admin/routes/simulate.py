"""Pipeline emulator: POST /admin/simulate → decision trace + metrics."""

import time
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.admin.auth_utils import effective_tenant
from app.db.session import async_session_factory

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/simulate", tags=["admin-simulate"])


@router.get("/", response_class=HTMLResponse)
async def simulate_ui(request: Request, tenant: str = "green-glamping"):
    tenant = effective_tenant(request, tenant)
    return templates.TemplateResponse(request, "simulate/index.html", {"tenant": tenant})


@router.post("/", response_class=JSONResponse)
async def simulate(
    request: Request,
    tenant: str = Form("green-glamping"),
    thread_id: str = Form("sim-001"),
    message: str = Form(...),
):
    tenant = effective_tenant(request, tenant)
    trace: list[dict] = []
    start = time.monotonic()

    async with async_session_factory() as session:
        # Resolve tenant
        t0 = time.monotonic()
        tenant_row = (await session.execute(
            sa.text("SELECT id, operation_mode, bot_config FROM public.tenants WHERE slug = :s"),
            {"s": tenant},
        )).fetchone()
        t1 = time.monotonic()
        if not tenant_row:
            return JSONResponse({"error": f"Tenant '{tenant}' not found"}, status_code=404)

        cfg = tenant_row.bot_config or {}

        trace.append({
            "step": "resolve_tenant",
            "ok": True,
            "detail": f"tenant_id={tenant_row.id}, mode={tenant_row.operation_mode}",
            "ms": round((t1 - t0) * 1000),
        })

        await session.execute(sa.text(f'SET search_path TO "tenant_{tenant}", public'))

        # Anti-injection check (respects tenant config)
        t0 = time.monotonic()
        if cfg.get("anti_injection_enabled", True):
            from app.bot.anti_injection import check_injection
            blocked = check_injection(message)
            detail = "BLOCKED" if blocked else "clean"
        else:
            blocked = False
            detail = "omitido (desactivado en configuración)"
        t1 = time.monotonic()
        trace.append({
            "step": "anti_injection",
            "ok": not blocked,
            "detail": detail,
            "ms": round((t1 - t0) * 1000),
        })

        if blocked:
            return JSONResponse({
                "blocked": True,
                "trace": trace,
                "total_ms": round((time.monotonic() - start) * 1000),
            })

        # Classifier
        t0 = time.monotonic()
        from app.bot.classifier import classify
        classification = await classify(message, tenant_row.id, session)
        if classification.matched_via == "fallback" and cfg.get("fallback_response"):
            classification.response_text = cfg["fallback_response"]
        t1 = time.monotonic()
        trace.append({
            "step": "classify",
            "ok": True,
            "detail": {
                "intent": classification.intent_name,
                "score": round(classification.score, 3),
                "matched_via": classification.matched_via,
                "is_ambiguous": classification.is_ambiguous,
                "top_candidates": list(classification.top_candidates or [])[:3],
            },
            "ms": round((t1 - t0) * 1000),
        })

        # Responder
        t0 = time.monotonic()
        from app.bot.responder import build_response
        outbound = build_response(classification)
        t1 = time.monotonic()
        trace.append({
            "step": "build_response",
            "ok": True,
            "detail": {
                "text_preview": (outbound.text or "")[:200],
                "requires_human": outbound.requires_human,
                "handoff_rule": outbound.handoff_rule,
            },
            "ms": round((t1 - t0) * 1000),
        })

        # Handoff check
        if classification.requires_human:
            trace.append({
                "step": "handoff_trigger",
                "ok": True,
                "detail": f"Would trigger {classification.handoff_rule} (simulation only — no DB write)",
                "ms": 0,
            })

    total_ms = round((time.monotonic() - start) * 1000)

    # Plan de humanización (no espera los delays — previsualización)
    bubble_plan = []
    try:
        from app.bot.humanizer import default_humanization, plan
        hz = cfg.get("humanization")
        if not isinstance(hz, dict):
            hz = default_humanization()
        for ch in (hz.get("channels") or []):
            plan_for_ch = plan(outbound.text or "", hz)
            if plan_for_ch:
                bubble_plan.append({
                    "channel": ch,
                    "applies": hz.get("enabled", False),
                    "bubbles": [
                        {
                            "i": i,
                            "text": b.text,
                            "typing_ms": b.typing_ms,
                            "pause_before_ms": b.pause_before_ms,
                        }
                        for i, b in enumerate(plan_for_ch)
                    ],
                })
    except Exception:
        bubble_plan = []

    return JSONResponse({
        "blocked": False,
        "llm_calls": 0,
        "total_ms": total_ms,
        "intent": classification.intent_name,
        "response_preview": (outbound.text or "")[:300],
        "requires_human": outbound.requires_human,
        "trace": trace,
        "bubble_plan": bubble_plan,
        "humanization_enabled": (cfg.get("humanization") or {}).get("enabled", False),
    })


@router.post("/export-test")
async def export_test(
    tenant: str = Form("green-glamping"),
    message: str = Form(...),
    expected_intent: str = Form(""),
):
    """Generate a pytest snippet for the given test case."""
    safe_msg = message.replace('"', '\\"').replace("\n", "\\n")
    code = f'''\
import pytest

@pytest.mark.asyncio
async def test_{(expected_intent or "message").replace("-","_")}():
    """Auto-generated by Multibot emulator."""
    from app.bot.classifier import classify
    # message: "{safe_msg}"
    class FakeSession:
        async def execute(self, *a, **kw):
            raise NotImplementedError("Offline test — mock the session")
    result = ...  # run offline using seed JSON as in tests/test_classifier.py
    assert result.intent_name == "{expected_intent}"
'''
    return JSONResponse({"code": code})
