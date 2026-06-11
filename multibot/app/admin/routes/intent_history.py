"""Admin routes: intent history & rollback.

Permite ver el historial de versiones de un intent (snapshots
guardados por el auto-learner o por ediciones manuales) y
revertir a cualquier versión anterior.
"""

from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.admin.auth_utils import effective_tenant
from app.db.session import async_session_factory

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/intents", tags=["admin-intent-history"])


@router.get("/{intent_name}/history", response_class=HTMLResponse)
async def intent_history(
    request: Request, intent_name: str, tenant: str = "green-glamping"
):
    """Muestra todas las versiones de un intent en orden cronológico."""
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"

    async with async_session_factory() as session:
        # Tenant ID
        tenant_id = (await session.execute(
            sa.text("SELECT id FROM public.tenants WHERE slug=:s"),
            {"s": tenant},
        )).scalar()

        # Versiones (filtradas por tenant + intent_name; el intent_id
        # puede ser NULL si el intent fue borrado después)
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        intent_row = (await session.execute(
            sa.text(
                "SELECT id, intent_name, keywords_regex, response_text, "
                "response_type, response_template, priority, status, source "
                "FROM kb_intents WHERE intent_name=:n"
            ),
            {"n": intent_name},
        )).fetchone()
        current_intent = dict(intent_row._mapping) if intent_row else None

        await session.execute(sa.text('SET search_path TO "public"'))
        versions = (await session.execute(
            sa.text(
                "SELECT id, snapshot, source, created_at, reverted_from "
                "FROM public.intent_versions "
                "WHERE tenant_id=:tid AND intent_name=:n "
                "ORDER BY created_at DESC LIMIT 50"
            ),
            {"tid": tenant_id, "n": intent_name},
        )).fetchall()
        versions = [dict(v._mapping) for v in versions]

    return templates.TemplateResponse(request, "intent_history.html", {
        "tenant": tenant,
        "intent_name": intent_name,
        "current": current_intent,
        "versions": versions,
    })


@router.post("/{intent_name}/revert/{version_id}")
async def intent_revert(
    request: Request, intent_name: str, version_id: int, tenant: str = Form(...)
):
    """Restaura un intent al estado del snapshot seleccionado."""
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"

    async with async_session_factory() as session:
        # 1. Tenant ID
        tenant_id = (await session.execute(
            sa.text("SELECT id FROM public.tenants WHERE slug=:s"),
            {"s": tenant},
        )).scalar()

        # 2. Cargar el snapshot
        await session.execute(sa.text('SET search_path TO "public"'))
        snap = (await session.execute(
            sa.text(
                "SELECT snapshot FROM public.intent_versions "
                "WHERE id=:id AND tenant_id=:tid"
            ),
            {"id": version_id, "tid": tenant_id},
        )).fetchone()
        if not snap:
            return RedirectResponse(
                f"/admin/intents/{intent_name}/history?tenant={tenant}&error=not_found",
                status_code=303,
            )
        snapshot = snap[0] if isinstance(snap[0], dict) else __import__("json").loads(snap[0])

        # 3. Snapshot del estado actual antes de revertir
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        current = (await session.execute(
            sa.text(
                "SELECT * FROM kb_intents WHERE intent_name=:n"
            ),
            {"n": intent_name},
        )).fetchone()
        if current:
            cur_snap = dict(current._mapping)
            cur_snap.pop("id", None)
            # Convertir tipos no serializables
            for k, v in list(cur_snap.items()):
                if hasattr(v, "isoformat"):
                    cur_snap[k] = v.isoformat()
            await session.execute(sa.text('SET search_path TO "public"'))
            await session.execute(
                sa.text(
                    "INSERT INTO public.intent_versions "
                    "(tenant_id, intent_id, intent_name, snapshot, source, reverted_from) "
                    "VALUES (:tid, :iid, :n, CAST(:s AS jsonb), 'revert', :prev)"
                ),
                {
                    "tid": tenant_id, "iid": current.id, "n": intent_name,
                    "s": __import__("json").dumps(cur_snap, ensure_ascii=False, default=str),
                    "prev": version_id,
                },
            )

        # 4. Aplicar el snapshot
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        await session.execute(
            sa.text(
                "UPDATE kb_intents SET "
                "keywords_regex=:kw, response_text=:rt, response_type=:rtype, "
                "response_template=:rtpl, priority=:prio, status='active' "
                "WHERE intent_name=:n"
            ),
            {
                "kw": snapshot.get("keywords_regex"),
                "rt": snapshot.get("response_text"),
                "rtype": snapshot.get("response_type", "static"),
                "rtpl": snapshot.get("response_template"),
                "prio": snapshot.get("priority", 5),
                "n": intent_name,
            },
        )
        await session.commit()

    return RedirectResponse(
        f"/admin/intents/{intent_name}/history?tenant={tenant}&saved=revertido",
        status_code=303,
    )
