"""Global settings editor (superadmin): edits .env values from the panel."""

import re
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])

ENV_PATH = Path(".env")

# Variables editables desde el panel: (clave, etiqueta, ayuda, es_secreto)
EDITABLE = [
    ("TELEGRAM_BOT_TOKEN", "Token global del bot de Telegram",
     "Se usa si el tenant no tiene token propio en Canales. De @BotFather.", True),
    ("NOTIFY_TELEGRAM_CHAT_ID", "Chat ID para notificaciones de handoff",
     "El chat_id de Telegram de quien recibe las alertas (ej. Johana). Obtenerlo con @userinfobot.", False),
    ("CORS_ORIGINS", "Orígenes CORS permitidos",
     "Dominios separados por coma que pueden llamar a la API.", False),
    ("LOG_LEVEL", "Nivel de logs",
     "DEBUG, INFO, WARNING o ERROR.", False),
]


def _read_env() -> dict:
    values = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                values[k.strip()] = v.strip()
    return values


def _write_env(updates: dict):
    """Actualiza solo las claves indicadas, preservando el resto del archivo."""
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    seen = set()
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.partition("=")[0].strip()
            if k in updates:
                out.append(f"{k}={updates[k]}")
                seen.add(k)
                continue
        out.append(line)
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(out) + "\n")


@router.get("/", response_class=HTMLResponse)
async def settings_view(request: Request):
    env = _read_env()
    fields = [
        {"key": k, "label": label, "hint": hint, "secret": secret, "value": env.get(k, "")}
        for k, label, hint, secret in EDITABLE
    ]
    return templates.TemplateResponse(request, "settings/index.html", {
        "fields": fields,
        "saved": request.query_params.get("saved"),
        "env_path": str(ENV_PATH.resolve()),
    })


@router.post("/save")
async def settings_save(request: Request):
    form = await request.form()
    allowed = {k for k, *_ in EDITABLE}
    updates = {}
    for k in allowed:
        if k in form:
            v = str(form[k]).strip()
            # No machacar un secreto existente con el placeholder enmascarado
            if v and set(v) != {"•"}:
                updates[k] = v
            elif not v:
                updates[k] = ""

    if updates:
        _write_env(updates)
        # Aplicar en caliente: limpiar el caché de settings
        import os
        for k, v in updates.items():
            os.environ[k] = v
        get_settings.cache_clear()

    return RedirectResponse("/admin/settings?saved=1", status_code=303)
