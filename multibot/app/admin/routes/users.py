"""User management (superadmin only): list, create, deactivate users."""

from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.passwords import hash_password
from app.db.session import async_session_factory

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


async def _load_context(error: str | None = None, ok: str | None = None) -> dict:
    async with async_session_factory() as session:
        users = (await session.execute(sa.text(
            "SELECT u.id, u.username, u.role, u.is_active, u.created_at, t.slug AS tenant_slug "
            "FROM public.admin_users u "
            "LEFT JOIN public.tenants t ON t.id = u.tenant_id "
            "ORDER BY u.id"
        ))).fetchall()
        tenants = (await session.execute(sa.text(
            "SELECT id, slug, name FROM public.tenants WHERE status='active' ORDER BY slug"
        ))).fetchall()
    return {"users": users, "tenants": tenants, "error": error, "ok": ok}


@router.get("/", response_class=HTMLResponse)
async def users_list(request: Request):
    ctx = await _load_context()
    return templates.TemplateResponse(request, "users/list.html", ctx)


@router.post("/new", response_class=HTMLResponse)
async def user_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("client"),
    tenant_id: str = Form(""),
):
    username = username.strip().lower()
    if len(password) < 8:
        ctx = await _load_context(error="La contraseña debe tener al menos 8 caracteres")
        return templates.TemplateResponse(request, "users/list.html", ctx)

    if role == "client" and not tenant_id:
        ctx = await _load_context(error="Un usuario cliente debe tener un tenant asignado")
        return templates.TemplateResponse(request, "users/list.html", ctx)

    async with async_session_factory() as session:
        try:
            await session.execute(
                sa.text(
                    "INSERT INTO public.admin_users (username, password_hash, role, tenant_id) "
                    "VALUES (:u, :p, :r, :t)"
                ),
                {
                    "u": username,
                    "p": hash_password(password),
                    "r": role,
                    "t": int(tenant_id) if tenant_id else None,
                },
            )
            await session.commit()
        except Exception:
            ctx = await _load_context(error=f"El usuario '{username}' ya existe")
            return templates.TemplateResponse(request, "users/list.html", ctx)

    return RedirectResponse("/admin/users", status_code=303)


@router.post("/{user_id}/toggle")
async def user_toggle(request: Request, user_id: int):
    async with async_session_factory() as session:
        await session.execute(
            sa.text("UPDATE public.admin_users SET is_active = NOT is_active WHERE id = :id"),
            {"id": user_id},
        )
        await session.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.post("/{user_id}/password")
async def user_change_password(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
):
    if len(new_password) < 8:
        ctx = await _load_context(error="La contraseña debe tener al menos 8 caracteres")
        return templates.TemplateResponse(request, "users/list.html", ctx)

    async with async_session_factory() as session:
        await session.execute(
            sa.text("UPDATE public.admin_users SET password_hash = :p WHERE id = :id"),
            {"p": hash_password(new_password), "id": user_id},
        )
        await session.commit()
    return RedirectResponse("/admin/users", status_code=303)
