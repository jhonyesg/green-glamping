"""Metrics dashboard with aggregated stats and feedback ticket review."""

from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db.session import async_session_factory
from app.admin.auth_utils import effective_tenant

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/metrics", tags=["admin-metrics"])


@router.get("/", response_class=HTMLResponse)
async def metrics_dashboard(request: Request, tenant: str = "green-glamping", days: int = 7):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"

    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))

            # Volume
            total_msgs = (await session.execute(sa.text(
                "SELECT COUNT(*) FROM messages WHERE ts > NOW() - INTERVAL ':days days'"
            ).bindparams(sa.bindparam("days", days)))).scalar() or 0

            # Avg latency (bot messages only)
            avg_latency = (await session.execute(sa.text(
                "SELECT AVG(latency_ms) FROM messages WHERE role='bot' AND latency_ms IS NOT NULL "
                "AND ts > NOW() - INTERVAL ':days days'"
            ).bindparams(sa.bindparam("days", days)))).scalar()

            # LLM calls
            llm_calls = (await session.execute(sa.text(
                "SELECT COUNT(*) FROM messages WHERE llm_tokens_used > 0 "
                "AND ts > NOW() - INTERVAL ':days days'"
            ).bindparams(sa.bindparam("days", days)))).scalar() or 0

            # Total conversations
            total_convs = (await session.execute(sa.text(
                "SELECT COUNT(*) FROM conversations WHERE last_message_at > NOW() - INTERVAL ':days days'"
            ).bindparams(sa.bindparam("days", days)))).scalar() or 0

            # Handoff rate
            handoff_convs = (await session.execute(sa.text(
                "SELECT COUNT(*) FROM conversations WHERE in_handoff = true "
                "AND last_message_at > NOW() - INTERVAL ':days days'"
            ).bindparams(sa.bindparam("days", days)))).scalar() or 0

            # Top intents
            top_intents = (await session.execute(sa.text(
                "SELECT ki.intent_name, COUNT(m.id) AS cnt "
                "FROM messages m "
                "JOIN kb_intents ki ON m.intent_id = ki.id "
                "WHERE m.ts > NOW() - INTERVAL ':days days' "
                "GROUP BY ki.intent_name ORDER BY cnt DESC LIMIT 10"
            ).bindparams(sa.bindparam("days", days)))).fetchall()

            # Daily volume for chart (last 14 days)
            daily = (await session.execute(sa.text(
                "SELECT DATE(ts) AS day, COUNT(*) AS cnt "
                "FROM messages WHERE ts > NOW() - INTERVAL '14 days' "
                "GROUP BY DATE(ts) ORDER BY day"
            ))).fetchall()

            # Feedback breakdown
            feedback_counts = (await session.execute(sa.text(
                "SELECT feedback, COUNT(*) AS cnt FROM messages "
                "WHERE feedback != 'none' AND ts > NOW() - INTERVAL ':days days' "
                "GROUP BY feedback"
            ).bindparams(sa.bindparam("days", days)))).fetchall()

            # Open feedback tickets
            open_tickets = (await session.execute(sa.text(
                "SELECT ft.id, ft.conversation_id, ft.message_id, ft.ticket_type, "
                "ft.notes, ft.status, m.content_text "
                "FROM feedback_tickets ft "
                "LEFT JOIN messages m ON m.id = ft.message_id "
                "WHERE ft.status = 'pending' ORDER BY ft.id DESC LIMIT 20"
            ))).fetchall()

        except Exception:
            total_msgs = avg_latency = llm_calls = total_convs = handoff_convs = 0
            top_intents = daily = feedback_counts = open_tickets = []

    chart_labels = [str(d.day) for d in daily]
    chart_data = [d.cnt for d in daily]

    return templates.TemplateResponse(request, "metrics/dashboard.html", {
        "tenant": tenant, "days": days,
        "total_msgs": total_msgs,
        "avg_latency": round(avg_latency or 0),
        "llm_calls": llm_calls,
        "total_convs": total_convs,
        "handoff_convs": handoff_convs,
        "top_intents": top_intents,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
        "feedback_counts": {r.feedback: r.cnt for r in feedback_counts},
        "open_tickets": open_tickets,
    })


@router.post("/tickets/{ticket_id}", response_class=HTMLResponse)
async def resolve_ticket(
    request: Request,
    ticket_id: int,
    tenant: str = "green-glamping",
    action: str = Form(...),
    resolution_note: str = Form(""),
):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    new_status = "approved" if action == "approve" else "rejected"
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        await session.execute(
            sa.text(
                "UPDATE feedback_tickets SET status=:s, notes=:n WHERE id=:id"
            ),
            {"s": new_status, "n": resolution_note or None, "id": ticket_id},
        )
        await session.commit()

    return RedirectResponse(f"/admin/metrics?tenant={tenant}", status_code=303)
