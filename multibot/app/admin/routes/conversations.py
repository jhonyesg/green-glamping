"""Conversation list and detail views with feedback quick actions."""

from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db.session import async_session_factory
from app.admin.auth_utils import effective_tenant

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/conversations", tags=["admin-conversations"])

PAGE_SIZE = 20


@router.get("/", response_class=HTMLResponse)
async def conversations_list(
    request: Request,
    tenant: str = "green-glamping",
    state: str = "",
    page: int = 1,
):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    offset = (page - 1) * PAGE_SIZE
    filters = "WHERE 1=1"
    params: dict = {"limit": PAGE_SIZE, "offset": offset}
    if state:
        filters += " AND state = :state"
        params["state"] = state

    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            rows = (await session.execute(
                sa.text(
                    f"SELECT id, external_thread_id, push_name, state, in_handoff, "
                    f"last_message_at, handoff_rule, operation_mode_snapshot "
                    f"FROM conversations {filters} "
                    f"ORDER BY last_message_at DESC NULLS LAST "
                    f"LIMIT :limit OFFSET :offset"
                ),
                params,
            )).fetchall()
            total = (await session.execute(
                sa.text(f"SELECT COUNT(*) FROM conversations {filters}"), params
            )).scalar()
        except Exception:
            rows, total = [], 0

    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse(request, "conversations/list.html", {
        "conversations": rows, "tenant": tenant, "state": state,
        "page": page, "pages": pages, "total": total,
    })


@router.get("/{conv_id}", response_class=HTMLResponse)
async def conversation_detail(request: Request, conv_id: int, tenant: str = "green-glamping"):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            conv = (await session.execute(
                sa.text("SELECT * FROM conversations WHERE id = :id"), {"id": conv_id}
            )).fetchone()
            messages = (await session.execute(
                sa.text(
                    "SELECT id, role, content_text, matched_via, intent_id, "
                    "latency_ms, feedback, ts "
                    "FROM messages WHERE conversation_id = :cid ORDER BY ts ASC"
                ),
                {"cid": conv_id},
            )).fetchall()
        except Exception:
            conv, messages = None, []

    if not conv:
        return RedirectResponse(f"/admin/conversations?tenant={tenant}", status_code=303)

    return templates.TemplateResponse(request, "conversations/detail.html", {
        "conv": conv._asdict(), "messages": messages, "tenant": tenant,
    })


@router.post("/{conv_id}/feedback/{msg_id}", response_class=HTMLResponse)
async def set_feedback(
    request: Request,
    conv_id: int,
    msg_id: int,
    tenant: str = "green-glamping",
    feedback: str = Form(...),
    feedback_note: str = Form(""),
):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        await session.execute(
            sa.text(
                "UPDATE messages SET feedback=:fb, feedback_note=:note WHERE id=:id"
            ),
            {"fb": feedback, "note": feedback_note or None, "id": msg_id},
        )
        # Create feedback ticket if bad
        if feedback == "bad":
            tenant_row = (await session.execute(
                sa.text("SELECT id FROM public.tenants WHERE slug = :s"),
                {"s": tenant},
            )).fetchone()
            tid = tenant_row.id if tenant_row else 0
            await session.execute(
                sa.text(
                    "INSERT INTO feedback_tickets "
                    "(tenant_id, conversation_id, message_id, ticket_type, notes, status) "
                    "VALUES (:tid, :cid, :mid, 'bad_response', :note, 'pending') "
                    "ON CONFLICT DO NOTHING"
                ),
                {"tid": tid, "cid": conv_id, "mid": msg_id, "note": feedback_note or None},
            )
        await session.commit()

    return RedirectResponse(
        f"/admin/conversations/{conv_id}?tenant={tenant}", status_code=303
    )
