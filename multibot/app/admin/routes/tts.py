"""TTS voice configuration admin panel."""

from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db.session import async_session_factory
from app.admin.auth_utils import effective_tenant

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/tts", tags=["admin-tts"])


@router.get("/", response_class=HTMLResponse)
async def tts_config(request: Request, tenant: str = "green-glamping"):
    tenant = effective_tenant(request, tenant)
    async with async_session_factory() as session:
        try:
            tenant_row = (await session.execute(
                sa.text("SELECT id FROM public.tenants WHERE slug=:s"), {"s": tenant}
            )).fetchone()
            if not tenant_row:
                providers = []
            else:
                await session.execute(
                    sa.text(f'SET search_path TO "tenant_{tenant}", public')
                )
                providers = (await session.execute(sa.text(
                    "SELECT id, provider_name, model, capabilities, is_active, priority "
                    "FROM llm_providers ORDER BY priority DESC"
                ))).fetchall()
        except Exception:
            providers = []

    return templates.TemplateResponse(request, "tts/config.html", {
        "tenant": tenant, "providers": providers,
    })


@router.post("/update", response_class=HTMLResponse)
async def tts_update(
    request: Request,
    tenant: str = Form("green-glamping"),
    provider_id: int = Form(...),
    voice_ids: str = Form(""),
    enable_tts: bool = Form(False),
):
    tenant = effective_tenant(request, tenant)
    voice_list = [v.strip() for v in voice_ids.split(",") if v.strip()]
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "tenant_{tenant}", public'))
        row = (await session.execute(
            sa.text("SELECT capabilities FROM llm_providers WHERE id=:id"), {"id": provider_id}
        )).fetchone()
        caps = dict(row.capabilities or {}) if row else {}
        caps["tts"] = enable_tts
        caps["voice_ids"] = voice_list or caps.get("voice_ids", ["female-shaxi-1"])
        await session.execute(
            sa.text("UPDATE llm_providers SET capabilities=:c WHERE id=:id"),
            {"c": sa.cast(caps, sa.JSON) if False else str(caps).replace("'", '"'), "id": provider_id},
        )
        await session.commit()
    return RedirectResponse(f"/admin/tts?tenant={tenant}", status_code=303)
