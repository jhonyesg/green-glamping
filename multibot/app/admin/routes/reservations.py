"""Reservations admin panel: list, confirm, cancel."""

from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db.session import async_session_factory
from app.admin.auth_utils import effective_tenant

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/reservations", tags=["admin-reservations"])

PAGE_SIZE = 20


@router.get("/", response_class=HTMLResponse)
async def reservations_list(
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
        filters += " AND state=:state"
        params["state"] = state

    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            rows = (await session.execute(
                sa.text(
                    f"SELECT id, guest_name, guest_id_number, check_in, check_out, "
                    f"combo, guests_count, total_price, state, created_at "
                    f"FROM reservations {filters} "
                    f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
                ),
                params,
            )).fetchall()
            total = (await session.execute(
                sa.text(f"SELECT COUNT(*) FROM reservations {filters}"), params
            )).scalar()
        except Exception:
            rows, total = [], 0

    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse(request, "reservations/list.html", {
        "reservations": rows, "tenant": tenant, "state": state,
        "page": page, "pages": pages, "total": total,
    })


@router.post("/{reservation_id}/confirm")
async def confirm_reservation(
    request: Request,
    reservation_id: int,
    tenant: str = "green-glamping",
    confirmed_by: str = Form("admin"),
):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        from app.reservations.lifecycle import confirm_reservation as _confirm
        await _confirm(reservation_id, confirmed_by, session)
    return RedirectResponse(f"/admin/reservations?tenant={tenant}", status_code=303)


@router.post("/{reservation_id}/cancel")
async def cancel_reservation(
    request: Request,
    reservation_id: int,
    tenant: str = "green-glamping",
    reason: str = Form("Cancelado por admin"),
):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        from app.reservations.lifecycle import cancel_reservation as _cancel
        await _cancel(reservation_id, reason, session)
    return RedirectResponse(f"/admin/reservations?tenant={tenant}", status_code=303)
