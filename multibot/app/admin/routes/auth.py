"""Admin login/logout with signed session cookie and DB-backed users with roles."""

import secrets
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.core.passwords import verify_password
from app.db.session import async_session_factory

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin", tags=["admin-auth"])
settings = get_settings()


async def _authenticate(username: str, password: str) -> dict | None:
    """
    Return session payload dict if credentials are valid, else None.
    Checks DB users first; falls back to the .env superadmin.
    """
    async with async_session_factory() as session:
        row = (await session.execute(
            sa.text(
                "SELECT u.id, u.username, u.password_hash, u.role, u.tenant_id, t.slug AS tenant_slug "
                "FROM public.admin_users u "
                "LEFT JOIN public.tenants t ON t.id = u.tenant_id "
                "WHERE u.username = :u AND u.is_active = true LIMIT 1"
            ),
            {"u": username},
        )).fetchone()

    if row and verify_password(password, row.password_hash):
        return {
            "user": row.username,
            "role": row.role,
            "tenant_id": row.tenant_id,
            "tenant_slug": row.tenant_slug,
        }

    # Fallback: .env superadmin (always works even if DB is empty)
    user_ok = secrets.compare_digest(username, settings.ADMIN_USERNAME)
    pass_ok = secrets.compare_digest(password, settings.ADMIN_PASSWORD)
    if user_ok and pass_ok:
        return {"user": username, "role": "superadmin", "tenant_id": None, "tenant_slug": None}

    return None


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    if request.session.get("user"):
        return RedirectResponse("/admin/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    payload = await _authenticate(username.strip(), password)
    if payload:
        request.session.update(payload)
        next_url = request.query_params.get("next", "/admin/")
        if not next_url.startswith("/"):
            next_url = "/admin/"
        return RedirectResponse(next_url, status_code=303)

    return templates.TemplateResponse(
        request, "login.html", {"error": "Usuario o contraseña incorrectos"}
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)
