"""Admin routes: auto-learner dashboard.

Permite al admin ver, aprobar, rechazar o editar las
propuestas generadas por analyze_recent_conversations.
"""

from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.admin.auth_utils import effective_tenant
from app.bot.learner import apply_proposal, reject_proposal
from app.db.session import async_session_factory

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/learner", tags=["admin-learner"])


async def _list_proposals(tenant: str, status: str | None = "pending") -> list[dict]:
    """Lista propuestas para un tenant, opcionalmente filtradas por status."""
    async with async_session_factory() as session:
        where = "WHERE tenant_id=(SELECT id FROM public.tenants WHERE slug=:s)"
        params: dict = {"s": tenant}
        if status:
            where += " AND status=:st"
            params["st"] = status
        rows = (await session.execute(
            sa.text(
                f"SELECT id, kind, payload, sample_messages, status, "
                f"confidence, proposed_at, reviewed_at, reviewed_by "
                f"FROM public.learner_proposals {where} "
                f"ORDER BY proposed_at DESC LIMIT 200"
            ),
            params,
        )).fetchall()
        return [
            {
                "id": r.id, "kind": r.kind, "payload": r.payload,
                "sample_messages": r.sample_messages or [],
                "status": r.status, "confidence": r.confidence,
                "proposed_at": r.proposed_at, "reviewed_at": r.reviewed_at,
                "reviewed_by": r.reviewed_by,
            }
            for r in rows
        ]


@router.get("/", response_class=HTMLResponse)
async def learner_index(request: Request, tenant: str = "green-glamping", status: str = "pending"):
    tenant = effective_tenant(request, tenant)
    proposals = await _list_proposals(tenant, status=status)
    async with async_session_factory() as session:
        tenants = (await session.execute(
            sa.text("SELECT slug FROM public.tenants WHERE status='active' ORDER BY slug")
        )).fetchall()
    return templates.TemplateResponse(request, "learner/index.html", {
        "tenant": tenant,
        "tenants": [t[0] for t in tenants],
        "proposals": proposals,
        "status_filter": status,
        "saved": request.query_params.get("saved"),
    })


@router.get("/{proposal_id}", response_class=HTMLResponse)
async def learner_diff(request: Request, proposal_id: int, tenant: str = "green-glamping"):
    """Vista de diff lado a lado con el intent actual (si existe) y la propuesta."""
    tenant = effective_tenant(request, tenant)
    async with async_session_factory() as session:
        # Proposal
        row = (await session.execute(
            sa.text(
                "SELECT id, tenant_id, kind, payload, sample_messages, "
                "status, confidence, proposed_at "
                "FROM public.learner_proposals WHERE id=:id"
            ),
            {"id": proposal_id},
        )).fetchone()
        if not row or row.tenant_id != (await session.execute(
            sa.text("SELECT id FROM public.tenants WHERE slug=:s"),
            {"s": tenant},
        )).scalar():
            return RedirectResponse(f"/admin/learner?tenant={tenant}", status_code=303)

        proposal = {
            "id": row.id, "kind": row.kind, "payload": row.payload,
            "sample_messages": row.sample_messages or [],
            "status": row.status, "confidence": row.confidence,
            "proposed_at": row.proposed_at,
        }

        # Si es update_intent, traer el intent actual
        current_intent = None
        if row.kind in ("update_intent", "deprecate_intent"):
            intent_name = row.payload.get("intent_name") or row.payload.get("to_remove", "")
            if intent_name:
                schema = f"tenant_{tenant}"
                await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
                ir = (await session.execute(
                    sa.text(
                        "SELECT intent_name, keywords_regex, response_text "
                        "FROM kb_intents WHERE intent_name=:n"
                    ),
                    {"n": intent_name},
                )).fetchone()
                if ir:
                    current_intent = dict(ir._mapping)

    return templates.TemplateResponse(request, "learner/diff.html", {
        "tenant": tenant,
        "proposal": proposal,
        "current_intent": current_intent,
    })


@router.post("/{proposal_id}/approve")
async def learner_approve(
    request: Request, proposal_id: int,
    tenant: str = Form(...),
    edited_intent_name: str = Form(""),
    edited_response: str = Form(""),
    edited_keywords: str = Form(""),
):
    tenant = effective_tenant(request, tenant)
    edited_payload: dict | None = None
    if edited_intent_name or edited_response or edited_keywords:
        # Admin editó antes de aprobar: usar el payload editado
        edited_payload = {
            "intent_name": edited_intent_name or None,
            "response": edited_response or None,
            "keywords": [k.strip() for k in edited_keywords.split(",") if k.strip()] or None,
        }
        edited_payload = {k: v for k, v in edited_payload.items() if v is not None}

    username = request.session.get("user", "admin")
    async with async_session_factory() as session:
        applied = await apply_proposal(
            proposal_id=proposal_id,
            session=session,
            edited_payload=edited_payload,
            editor=username,
        )
    saved = "aplicado" if applied else "error"
    return RedirectResponse(
        f"/admin/learner?tenant={tenant}&saved={saved}", status_code=303
    )


@router.post("/{proposal_id}/reject")
async def learner_reject(request: Request, proposal_id: int, tenant: str = Form(...)):
    tenant = effective_tenant(request, tenant)
    username = request.session.get("user", "admin")
    async with async_session_factory() as session:
        await reject_proposal(proposal_id, session, editor=username)
    return RedirectResponse(
        f"/admin/learner?tenant={tenant}&saved=rechazado", status_code=303
    )
