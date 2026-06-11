"""Knowledge base editor: list, create, edit, delete intents."""

from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.admin.auth_utils import effective_tenant
from app.db.session import async_session_factory

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/kb", tags=["admin-kb"])

PAGE_SIZE = 25


async def _get_tenant_id(slug: str) -> int | None:
    async with async_session_factory() as session:
        row = (await session.execute(
            sa.text("SELECT id FROM public.tenants WHERE slug = :s"), {"s": slug}
        )).fetchone()
    return row.id if row else None


@router.get("/", response_class=HTMLResponse)
async def kb_list(request: Request, tenant: str = "green-glamping", page: int = 1,
                  search: str = "", status: str = ""):
    offset = (page - 1) * PAGE_SIZE
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"

    filters = "WHERE 1=1"
    params: dict = {"limit": PAGE_SIZE, "offset": offset}
    if search:
        filters += " AND (intent_name ILIKE :search OR response_text ILIKE :search)"
        params["search"] = f"%{search}%"
    if status:
        filters += " AND status = :status"
        params["status"] = status

    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            rows = (await session.execute(
                sa.text(
                    f"SELECT id, intent_name, priority, status, requires_human, "
                    f"LENGTH(response_text) AS resp_len "
                    f"FROM kb_intents {filters} "
                    f"ORDER BY priority DESC, intent_name "
                    f"LIMIT :limit OFFSET :offset"
                ),
                params,
            )).fetchall()
            total = (await session.execute(
                sa.text(f"SELECT COUNT(*) FROM kb_intents {filters}"), params
            )).scalar()
        except Exception:
            rows, total = [], 0

    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse(request, "kb/list.html", {
        "intents": rows, "tenant": tenant, "page": page, "pages": pages,
        "total": total, "search": search, "status": status,
    })


@router.get("/new", response_class=HTMLResponse)
async def kb_new(request: Request, tenant: str = "green-glamping"):
    tenant = effective_tenant(request, tenant)
    media_options = await _media_options(tenant)
    return templates.TemplateResponse(request, "kb/edit.html", {
        "intent": None, "tenant": tenant,
        "action": f"/admin/kb/new?tenant={tenant}",
        "media_options": media_options,
        "selected_media_ids": set(),
    })


@router.post("/new", response_class=HTMLResponse)
async def kb_create(
    request: Request,
    tenant: str = Form("green-glamping"),
    intent_name: str = Form(...),
    keywords_regex: str = Form(...),
    response_text: str = Form(...),
    priority: int = Form(5),
    requires_human: bool = Form(False),
    handoff_rule: str = Form(""),
    status: str = Form("active"),
    response_media_ids: list[int] = Form([]),
):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    tenant_id = await _get_tenant_id(tenant)
    if not tenant_id:
        return templates.TemplateResponse(request, "kb/edit.html", {
            "intent": None, "tenant": tenant, "error": f"Tenant '{tenant}' no encontrado",
            "action": f"/admin/kb/new?tenant={tenant}",
        })

    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            await session.execute(
                sa.text(
                    "INSERT INTO kb_intents "
                    "(tenant_id, intent_name, keywords_regex, response_text, priority, "
                    "requires_human, handoff_rule, status, source, response_media_ids) "
                    "VALUES (:tid, :name, :regex, :resp, :prio, :rh, :hr, :st, 'manual', "
                    "CAST(:media AS jsonb))"
                ),
                {
                    "tid": tenant_id, "name": intent_name, "regex": keywords_regex,
                    "resp": response_text, "prio": priority,
                    "rh": requires_human, "hr": handoff_rule or None, "st": status,
                    "media": __import__("json").dumps([int(x) for x in response_media_ids if x]),
                },
            )
            await session.commit()
        except Exception as e:
            return templates.TemplateResponse(request, "kb/edit.html", {
                "intent": None, "tenant": tenant, "error": str(e),
                "action": f"/admin/kb/new?tenant={tenant}",
            })

    return RedirectResponse(f"/admin/kb?tenant={tenant}", status_code=303)


@router.get("/{intent_id}", response_class=HTMLResponse)
async def kb_edit(request: Request, intent_id: int, tenant: str = "green-glamping"):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        row = (await session.execute(
            sa.text("SELECT * FROM kb_intents WHERE id = :id"), {"id": intent_id}
        )).fetchone()

    if not row:
        return RedirectResponse(f"/admin/kb?tenant={tenant}", status_code=303)

    intent_dict = dict(row._mapping)
    media_options = await _media_options(tenant)
    selected_media_ids = set(int(x) for x in (intent_dict.get("response_media_ids") or []))
    return templates.TemplateResponse(request, "kb/edit.html", {
        "intent": intent_dict, "tenant": tenant,
        "action": f"/admin/kb/{intent_id}?tenant={tenant}",
        "media_options": media_options,
        "selected_media_ids": selected_media_ids,
    })


@router.post("/{intent_id}", response_class=HTMLResponse)
async def kb_update(
    request: Request,
    intent_id: int,
    tenant: str = Form("green-glamping"),
    intent_name: str = Form(...),
    keywords_regex: str = Form(...),
    response_text: str = Form(...),
    priority: int = Form(5),
    requires_human: bool = Form(False),
    handoff_rule: str = Form(""),
    status: str = Form("active"),
    response_media_ids: list[int] = Form([]),
):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    media_ids_clean = [int(x) for x in response_media_ids if x]
    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            await session.execute(
                sa.text(
                    "UPDATE kb_intents SET "
                    "intent_name=:name, keywords_regex=:regex, response_text=:resp, "
                    "priority=:prio, requires_human=:rh, handoff_rule=:hr, status=:st, "
                    "response_media_ids=CAST(:media AS jsonb) "
                    "WHERE id=:id"
                ),
                {
                    "name": intent_name, "regex": keywords_regex, "resp": response_text,
                    "prio": priority, "rh": requires_human, "hr": handoff_rule or None,
                    "st": status, "id": intent_id,
                    "media": __import__("json").dumps(media_ids_clean),
                },
            )
            await session.commit()
        except Exception as e:
            row = (await session.execute(
                sa.text("SELECT * FROM kb_intents WHERE id = :id"), {"id": intent_id}
            )).fetchone()
            media_options = await _media_options(tenant)
            return templates.TemplateResponse(request, "kb/edit.html", {
                "intent": dict(row._mapping) if row else None, "tenant": tenant,
                "error": str(e), "action": f"/admin/kb/{intent_id}?tenant={tenant}",
                "media_options": media_options,
                "selected_media_ids": set(media_ids_clean),
            })

    return RedirectResponse(f"/admin/kb?tenant={tenant}", status_code=303)


async def _media_options(tenant: str) -> list[dict]:
    """Lista de media activos del tenant (para el multi-select del form de intent)."""
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            rows = (await session.execute(
                sa.text(
                    "SELECT id, key, tipo, mime_type, descripcion "
                    "FROM media WHERE is_active=true "
                    "ORDER BY tipo, key"
                )
            )).fetchall()
            return [
                {"id": r.id, "key": r.key, "tipo": r.tipo,
                 "mime_type": r.mime_type, "descripcion": r.descripcion}
                for r in rows
            ]
        except Exception:
            return []


@router.get("/{intent_id}", response_class=HTMLResponse)
async def kb_edit(request: Request, intent_id: int, tenant: str = "green-glamping"):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        row = (await session.execute(
            sa.text("SELECT * FROM kb_intents WHERE id = :id"), {"id": intent_id}
        )).fetchone()

    if not row:
        return RedirectResponse(f"/admin/kb?tenant={tenant}", status_code=303)

    return templates.TemplateResponse(request, "kb/edit.html", {
        "intent": row._asdict(), "tenant": tenant,
        "action": f"/admin/kb/{intent_id}?tenant={tenant}",
    })


@router.post("/{intent_id}", response_class=HTMLResponse)
async def kb_update(
    request: Request,
    intent_id: int,
    tenant: str = "green-glamping",
    intent_name: str = Form(...),
    keywords_regex: str = Form(...),
    response_text: str = Form(...),
    priority: int = Form(5),
    requires_human: bool = Form(False),
    handoff_rule: str = Form(""),
    status: str = Form("active"),
):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        try:
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            await session.execute(
                sa.text(
                    "UPDATE kb_intents SET "
                    "intent_name=:name, keywords_regex=:regex, response_text=:resp, "
                    "priority=:prio, requires_human=:rh, handoff_rule=:hr, status=:st "
                    "WHERE id=:id"
                ),
                {
                    "name": intent_name, "regex": keywords_regex, "resp": response_text,
                    "prio": priority, "rh": requires_human, "hr": handoff_rule or None,
                    "st": status, "id": intent_id,
                },
            )
            await session.commit()
        except Exception as e:
            row = (await session.execute(
                sa.text("SELECT * FROM kb_intents WHERE id = :id"), {"id": intent_id}
            )).fetchone()
            return templates.TemplateResponse(request, "kb/edit.html", {
                "intent": row._asdict() if row else None, "tenant": tenant,
                "error": str(e), "action": f"/admin/kb/{intent_id}?tenant={tenant}",
            })

    return RedirectResponse(f"/admin/kb?tenant={tenant}", status_code=303)


@router.post("/{intent_id}/delete", response_class=HTMLResponse)
async def kb_delete(request: Request, intent_id: int, tenant: str = "green-glamping"):
    tenant = effective_tenant(request, tenant)
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        await session.execute(
            sa.text("DELETE FROM kb_intents WHERE id = :id"), {"id": intent_id}
        )
        await session.commit()
    return RedirectResponse(f"/admin/kb?tenant={tenant}", status_code=303)
