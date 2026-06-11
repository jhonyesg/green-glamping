"""Admin routes: media library per tenant.

CRUD + upload, validación MIME/tamaño, soft delete con preservación
del archivo en disco. Endpoints JSON para uso del template render
y simulador."""

import re
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.admin.auth_utils import effective_tenant
from app.core.media_keys import next_media_key
from app.core.media_store import save_upload
from app.db.session import async_session_factory

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/media", tags=["admin-media"])
api_router = APIRouter(prefix="/api", tags=["api-plans-media"])


def _key_ok(k: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_-]{1,150}$", k))


async def _list(tenant: str) -> tuple[list, list[str]]:
    schema = f"tenant_{tenant}"
    media: list = []
    async with async_session_factory() as session:
        tenants = (await session.execute(
            sa.text("SELECT slug FROM public.tenants WHERE status='active' ORDER BY slug")
        )).fetchall()
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            rows = (await session.execute(
                sa.text("SELECT id, key, tipo, path, mime_type, size_bytes, "
                        "original_filename, descripcion, is_active, source, created_at "
                        "FROM media ORDER BY created_at DESC")
            )).fetchall()
            for r in rows:
                media.append({
                    "id": r.id, "key": r.key, "tipo": r.tipo,
                    "path": r.path, "mime_type": r.mime_type, "size_bytes": r.size_bytes,
                    "original_filename": r.original_filename, "descripcion": r.descripcion,
                    "is_active": r.is_active, "source": r.source,
                    "url": f"/media/{tenant}/{r.path}",
                })
        except Exception:
            pass
    return media, [t.slug for t in tenants]


@router.get("/", response_class=HTMLResponse)
async def media_index(request: Request, tenant: str = "green-glamping"):
    tenant = effective_tenant(request, tenant)
    media, tenants = await _list(tenant)
    return templates.TemplateResponse(request, "media/index.html", {
        "tenant": tenant,
        "tenants": tenants,
        "media": media,
        "saved": request.query_params.get("saved"),
        "error": request.query_params.get("error"),
    })


@router.post("/upload")
async def media_upload(
    request: Request,
    tenant: str = Form(...),
    descripcion: str = Form(""),
    file: UploadFile = File(...),
):
    tenant = effective_tenant(request, tenant)

    rel_path, sha, size = await save_upload(file, tenant)
    mime = (file.content_type or "").lower()
    tipo_str = "image" if mime.startswith("image/") else (
        "audio" if mime.startswith("audio/") else "document"
    )

    schema = f"tenant_{tenant}"
    username = request.session.get("user") or "unknown"
    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            # Auto-generar key. El admin la puede renombrar después.
            auto_key = await next_media_key(tenant, session)
            await session.execute(
                sa.text(
                    "INSERT INTO media (key, tipo, path, mime_type, size_bytes, "
                    "original_filename, descripcion, uploaded_by, source) "
                    "VALUES (:k, :t, :p, :m, :s, :o, :d, :u, 'uploaded')"
                ),
                {"k": auto_key, "t": tipo_str, "p": rel_path, "m": mime,
                 "s": size, "o": file.filename, "d": descripcion or None, "u": username},
            )
            await session.commit()
        except Exception as e:
            return RedirectResponse(
                f"/admin/media?tenant={tenant}&error={str(e)[:60]}", status_code=303
            )
    return RedirectResponse(
        f"/admin/media?tenant={tenant}&saved=subido+({auto_key})", status_code=303
    )


@router.post("/{media_id}")
async def media_update(
    request: Request,
    media_id: int,
    tenant: str = Form(...),
    key: str = Form(...),
    descripcion: str = Form(""),
    is_active: str = Form("true"),
):
    tenant = effective_tenant(request, tenant)
    if not _key_ok(key):
        return RedirectResponse(
            f"/admin/media?tenant={tenant}&error=key_invalid", status_code=303
        )
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            await session.execute(
                sa.text("UPDATE media SET key=:k, descripcion=:d, is_active=:a WHERE id=:id"),
                {"k": key, "d": descripcion or None, "a": is_active == "true", "id": media_id},
            )
            await session.commit()
        except Exception as e:
            return RedirectResponse(
                f"/admin/media?tenant={tenant}&error={str(e)[:60]}", status_code=303
            )
    return RedirectResponse(
        f"/admin/media?tenant={tenant}&saved=updated", status_code=303
    )


@router.post("/{media_id}/deactivate")
async def media_deactivate(request: Request, media_id: int, tenant: str = Form(...)):
    """Soft delete: marca is_active=false. El archivo sigue en disco."""
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            await session.execute(
                sa.text("UPDATE media SET is_active=false WHERE id=:id"),
                {"id": media_id},
            )
            await session.commit()
        except Exception:
            pass
    return RedirectResponse(
        f"/admin/media?tenant={tenant}&saved=desactivado", status_code=303
    )


@router.post("/{media_id}/delete")
async def media_delete(request: Request, media_id: int, tenant: str = Form(...)):
    """
    Hard delete: borra la fila Y el archivo físico del disco.
    El admin lo usa cuando sabe que no va a volver a necesitar el archivo.
    """
    from pathlib import Path as _Path
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    path_to_unlink: str | None = None
    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            row = (await session.execute(
                sa.text("SELECT path FROM media WHERE id=:id"),
                {"id": media_id},
            )).fetchone()
            if row:
                path_to_unlink = row[0]
            await session.execute(
                sa.text("DELETE FROM media WHERE id=:id"),
                {"id": media_id},
            )
            await session.commit()
        except Exception as e:
            return RedirectResponse(
                f"/admin/media?tenant={tenant}&error={str(e)[:60]}", status_code=303
            )
    # Borrar archivo físico (después del commit, para no dejar BD desincronizada)
    if path_to_unlink:
        from app.core.media_store import DATA_ROOT
        try:
            full = _Path(DATA_ROOT) / path_to_unlink
            full.unlink(missing_ok=True)
        except Exception:
            pass  # no fallar la operación si el unlink falla
    return RedirectResponse(
        f"/admin/media?tenant={tenant}&saved=eliminado", status_code=303
    )


@api_router.get("/media/{tenant_slug}/{key}")
async def api_media_by_key(tenant_slug: str, key: str):
    """JSON con la URL pública del media (uso del template render y simulador)."""
    schema = f"tenant_{tenant_slug}"
    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            row = (await session.execute(
                sa.text("SELECT path FROM media WHERE key=:k AND is_active=true LIMIT 1"),
                {"k": key},
            )).fetchone()
        except Exception as e:
            return JSONResponse({"error": str(e)[:200]}, status_code=500)
        if not row:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return JSONResponse({
            "key": key,
            "url": f"/media/{tenant_slug}/{row.path}",
        })
