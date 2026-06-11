"""Admin routes: services catalog (offering) per tenant.

CRUD básico con soft delete. La imagen de portada se elige de
la biblioteca de media (`/admin/media/`), no se sube en este form.
La key de media se genera automáticamente en el upload.
"""

import re
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.admin.auth_utils import effective_tenant
from app.db.session import async_session_factory

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/plans", tags=["admin-plans"])
# Alias para que el admin pueda usar /admin/services/ también
services_alias = APIRouter(prefix="/admin/services", tags=["admin-services"])
api_router = APIRouter(prefix="/api", tags=["api-plans-media"])


def _slug_ok(s: str) -> bool:
    return bool(re.match(r"^[a-z0-9_-]{1,100}$", s))


def _parse_incluye(raw: str) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split("\n") if x.strip()]


def _format_cop(value) -> str:
    """Formatea un monto en pesos colombianos: 30000 -> '$30.000'."""
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return str(value)
    return f"${n:,}".replace(",", ".")


async def _list(tenant: str) -> tuple[list, list[str]]:
    """Returns (offerings_with_imagen_url, tenant_slugs)."""
    schemas = [f"tenant_{tenant}"]
    offerings: list = []
    async with async_session_factory() as session:
        tenants = (await session.execute(
            sa.text("SELECT slug, name FROM public.tenants WHERE status='active' ORDER BY slug")
        )).fetchall()
        try:
            await session.execute(sa.text(f'SET search_path TO "{schemas[0]}", public'))
            rows = (await session.execute(
                sa.text(
                    "SELECT o.id, o.slug, o.nombre, o.descripcion, o.precio_cop, "
                    "o.incluye, o.imagen_id, o.display_order, o.is_active, o.source, "
                    "m.path AS media_path, m.is_active AS media_active "
                    "FROM offering o LEFT JOIN media m ON m.id = o.imagen_id "
                    "ORDER BY o.display_order, o.id"
                )
            )).fetchall()
            for r in rows:
                img_url = (
                    f"/media/{tenant}/{r.media_path}"
                    if r.imagen_id and r.media_path and r.media_active
                    else None
                )
                offerings.append({
                    "id": r.id, "slug": r.slug, "nombre": r.nombre,
                    "descripcion": r.descripcion,
                    "precio_cop": float(r.precio_cop) if r.precio_cop is not None else 0.0,
                    "precio_cop_fmt": _format_cop(r.precio_cop),
                    "incluye": list(r.incluye or []),
                    "imagen_id": r.imagen_id,
                    "imagen_url": img_url,
                    "display_order": r.display_order,
                    "is_active": r.is_active,
                    "source": r.source,
                })
        except Exception:
            pass
    return offerings, [t.slug for t in tenants]


async def _media_images(tenant: str) -> list[dict]:
    """Lista de imágenes activas de la biblioteca del tenant."""
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            rows = (await session.execute(
                sa.text(
                    "SELECT id, key, mime_type, path FROM media "
                    "WHERE tipo='image' AND is_active=true ORDER BY key"
                )
            )).fetchall()
            return [
                {"id": r.id, "key": r.key, "mime_type": r.mime_type, "path": r.path}
                for r in rows
            ]
        except Exception:
            return []


@router.get("/", response_class=HTMLResponse)
async def plans_index(request: Request, tenant: str = "green-glamping"):
    tenant = effective_tenant(request, tenant)
    offerings, tenants = await _list(tenant)
    return templates.TemplateResponse(request, "plans/index.html", {
        "tenant": tenant,
        "tenants": tenants,
        "offerings": offerings,
        "saved": request.query_params.get("saved"),
        "error": request.query_params.get("error"),
    })


@router.get("/{plan_id}/edit", response_class=HTMLResponse)
async def plans_edit(request: Request, plan_id: int, tenant: str = "green-glamping"):
    tenant = effective_tenant(request, tenant)
    offerings, tenants = await _list(tenant)
    plan = next((o for o in offerings if o["id"] == plan_id), None)
    if not plan:
        return RedirectResponse(f"/admin/plans?tenant={tenant}&error=not_found", status_code=303)
    media_images = await _media_images(tenant)
    return templates.TemplateResponse(request, "plans/edit.html", {
        "tenant": tenant,
        "tenants": tenants,
        "plan": plan,
        "media_images": media_images,
        "error": request.query_params.get("error"),
    })


@router.post("/")
async def plans_create(
    request: Request,
    tenant: str = Form(...),
    slug: str = Form(...),
    nombre: str = Form(...),
    descripcion: str = Form(""),
    precio_cop: float = Form(0),
    incluye: str = Form(""),
    display_order: int = Form(100),
    is_active: str = Form("true"),
):
    tenant = effective_tenant(request, tenant)
    if not _slug_ok(slug):
        return RedirectResponse(
            f"/admin/plans?tenant={tenant}&error=slug_invalid", status_code=303
        )
    if not nombre.strip():
        return RedirectResponse(
            f"/admin/plans?tenant={tenant}&error=nombre_required", status_code=303
        )

    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        existing = (await session.execute(
            sa.text("SELECT id FROM offering WHERE slug=:s"), {"s": slug}
        )).fetchone()
        if existing:
            return RedirectResponse(
                f"/admin/plans?tenant={tenant}&error=slug_duplicado", status_code=303
            )
        await session.execute(
            sa.text(
                "INSERT INTO offering "
                "(slug, nombre, descripcion, precio_cop, incluye, display_order, is_active, source) "
                "VALUES (:slug, :nombre, :desc, :precio, CAST(:incluye AS jsonb), :ord, :active, 'manual')"
            ),
            {
                "slug": slug,
                "nombre": nombre.strip(),
                "desc": descripcion.strip() or None,
                "precio": precio_cop,
                "incluye": __import__("json").dumps(_parse_incluye(incluye)),
                "ord": display_order,
                "active": is_active == "true",
            },
        )
        await session.commit()
    return RedirectResponse(
        f"/admin/plans?tenant={tenant}&saved=creado", status_code=303
    )


@router.post("/{plan_id}")
async def plans_update(
    request: Request,
    plan_id: int,
    tenant: str = Form(...),
    slug: str = Form(...),
    nombre: str = Form(...),
    descripcion: str = Form(""),
    precio_cop: float = Form(0),
    incluye: str = Form(""),
    display_order: int = Form(100),
    is_active: str = Form("true"),
    imagen_id: int = Form(0),
):
    tenant = effective_tenant(request, tenant)
    if not _slug_ok(slug):
        return RedirectResponse(
            f"/admin/plans/{plan_id}/edit?tenant={tenant}&error=slug_invalid", status_code=303
        )

    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        # Si imagen_id = 0 → null (sin imagen). Validar que la media existe
        # y pertenece al tenant antes de asignar.
        if imagen_id > 0:
            check = (await session.execute(
                sa.text("SELECT id FROM media WHERE id=:i AND is_active=true"),
                {"i": imagen_id},
            )).fetchone()
            if not check:
                return RedirectResponse(
                    f"/admin/plans/{plan_id}/edit?tenant={tenant}&error=imagen_no_encontrada",
                    status_code=303,
                )
        await session.execute(
            sa.text(
                "UPDATE offering SET slug=:slug, nombre=:nombre, descripcion=:desc, "
                "precio_cop=:precio, incluye=CAST(:incluye AS jsonb), "
                "display_order=:ord, is_active=:active, imagen_id=:img "
                "WHERE id=:id"
            ),
            {
                "slug": slug, "nombre": nombre.strip(),
                "desc": descripcion.strip() or None, "precio": precio_cop,
                "incluye": __import__("json").dumps(_parse_incluye(incluye)),
                "ord": display_order, "active": is_active == "true",
                "img": imagen_id if imagen_id > 0 else None,
                "id": plan_id,
            },
        )
        await session.commit()
    return RedirectResponse(
        f"/admin/plans?tenant={tenant}&saved=actualizado", status_code=303
    )


@router.post("/{plan_id}/deactivate")
async def plans_deactivate(request: Request, plan_id: int, tenant: str = Form(...)):
    """Soft delete: marca is_active=false. El servicio se puede reactivar."""
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        await session.execute(
            sa.text("UPDATE offering SET is_active=false WHERE id=:id"),
            {"id": plan_id},
        )
        await session.commit()
    return RedirectResponse(
        f"/admin/plans?tenant={tenant}&saved=desactivado", status_code=303
    )


@router.post("/{plan_id}/delete")
async def plans_delete(request: Request, plan_id: int, tenant: str = Form(...)):
    """Hard delete: borra la fila permanentemente. La imagen_id queda libre."""
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        await session.execute(
            sa.text("DELETE FROM offering WHERE id=:id"),
            {"id": plan_id},
        )
        await session.commit()
    return RedirectResponse(
        f"/admin/plans?tenant={tenant}&saved=eliminado", status_code=303
    )


# Alias: /admin/services/ apunta al mismo handler de /admin/plans/
# para que el admin use la URL semántica sin romper bookmarks.
@services_alias.get("/", response_class=HTMLResponse)
async def services_alias_index(request: Request, tenant: str = "green-glamping"):
    return await plans_index(request, tenant)


@api_router.get("/plans")
async def api_plans(tenant: str = "green-glamping"):
    """JSON con servicios activos del tenant (uso interno del pipeline y simulador)."""
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            rows = (await session.execute(
                sa.text(
                    "SELECT o.id, o.slug, o.nombre, o.descripcion, o.precio_cop, "
                    "o.incluye, o.imagen_id, o.display_order, o.is_active, "
                    "m.path AS media_path, m.key AS media_key "
                    "FROM offering o LEFT JOIN media m ON m.id = o.imagen_id "
                    "WHERE o.is_active=true "
                    "ORDER BY o.display_order, o.id"
                )
            )).fetchall()
        except Exception as e:
            return JSONResponse({"error": str(e)[:200]}, status_code=500)
        out = []
        for r in rows:
            out.append({
                "id": r.id, "slug": r.slug, "nombre": r.nombre,
                "descripcion": r.descripcion,
                "precio_cop": float(r.precio_cop),
                "precio_cop_fmt": _format_cop(r.precio_cop),
                "incluye": list(r.incluye or []),
                "imagen_id": r.imagen_id,
                "imagen_url": (
                    f"/media/{tenant}/{r.media_path}"
                    if r.imagen_id and r.media_path else None
                ),
                "imagen_key": r.media_key,
                "display_order": r.display_order,
                "is_active": r.is_active,
            })
        return JSONResponse(out)
