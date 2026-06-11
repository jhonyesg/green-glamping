"""6-step tenant onboarding wizard."""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/wizard", tags=["admin-wizard"])

STEPS = [
    ("1", "Datos del tenant"),
    ("2", "Modo de operación"),
    ("3", "Canal"),
    ("4", "Disponibilidad"),
    ("5", "Assets"),
    ("6", "KB y prueba"),
]

MODE_FLOWS = {
    "autonomous": """\
Cliente → [Bot]
  ├─ Responde con KB
  ├─ Maneja objeciones
  └─ Cierra reserva
       ↓
  Pago + confirmación""",
    "assisted": """\
Cliente → [Bot] → Clasifica
  ↓
Human revisa propuesta
  ↓
[Bot] envía respuesta aprobada""",
    "hybrid": """\
Cliente → [Bot]
  ├─ Temas simples: Bot responde
  └─ Temas complejos/pago:
       ↓
  Handoff → Human
       ↓
  Human cierra trato""",
}


def _ctx(step: str, extra: dict | None = None) -> dict:
    ctx = {"steps": STEPS, "current_step": step}
    if extra:
        ctx.update(extra)
    return ctx


@router.get("/", response_class=HTMLResponse)
async def wizard_start(request: Request):
    return templates.TemplateResponse(request, "wizard/step1.html", _ctx("1"))


@router.get("/step/{step}", response_class=HTMLResponse)
async def wizard_step(request: Request, step: str):
    template = f"wizard/step{step}.html"
    return templates.TemplateResponse(request, template, _ctx(step))


@router.post("/step/1", response_class=HTMLResponse)
async def wizard_step1_submit(
    request: Request,
    slug: str = Form(...),
    name: str = Form(...),
    contact_email: str = Form(""),
):
    ctx = _ctx("2", {"slug": slug, "name": name, "contact_email": contact_email, "mode_flows": MODE_FLOWS})
    return templates.TemplateResponse(request, "wizard/step2.html", ctx)


@router.post("/step/2", response_class=HTMLResponse)
async def wizard_step2_submit(
    request: Request,
    slug: str = Form(...),
    name: str = Form(...),
    operation_mode: str = Form("autonomous"),
):
    ctx = _ctx("3", {"slug": slug, "name": name, "operation_mode": operation_mode})
    return templates.TemplateResponse(request, "wizard/step3.html", ctx)


@router.post("/step/3", response_class=HTMLResponse)
async def wizard_step3_submit(
    request: Request,
    slug: str = Form(...),
    name: str = Form(...),
    operation_mode: str = Form("autonomous"),
    channel_type: str = Form("telegram"),
    bot_token: str = Form(""),
):
    ctx = _ctx("4", {
        "slug": slug, "name": name, "operation_mode": operation_mode,
        "channel_type": channel_type, "bot_token": bot_token,
    })
    return templates.TemplateResponse(request, "wizard/step4.html", ctx)


@router.post("/step/4", response_class=HTMLResponse)
async def wizard_step4_submit(
    request: Request,
    slug: str = Form(...),
    name: str = Form(...),
    operation_mode: str = Form("autonomous"),
    channel_type: str = Form("telegram"),
    bot_token: str = Form(""),
    short_pause_hours: int = Form(12),
    long_pause_hours: int = Form(48),
):
    ctx = _ctx("5", {
        "slug": slug, "name": name, "operation_mode": operation_mode,
        "channel_type": channel_type, "bot_token": bot_token,
        "short_pause_hours": short_pause_hours, "long_pause_hours": long_pause_hours,
    })
    return templates.TemplateResponse(request, "wizard/step5.html", ctx)


@router.post("/step/5", response_class=HTMLResponse)
async def wizard_step5_submit(
    request: Request,
    slug: str = Form(...),
    name: str = Form(...),
    operation_mode: str = Form("autonomous"),
    channel_type: str = Form("telegram"),
    bot_token: str = Form(""),
    short_pause_hours: int = Form(12),
    long_pause_hours: int = Form(48),
    welcome_message: str = Form("¡Hola! Bienvenido. ¿En qué puedo ayudarte?"),
):
    ctx = _ctx("6", {
        "slug": slug, "name": name, "operation_mode": operation_mode,
        "channel_type": channel_type, "bot_token": bot_token,
        "short_pause_hours": short_pause_hours, "long_pause_hours": long_pause_hours,
        "welcome_message": welcome_message,
    })
    return templates.TemplateResponse(request, "wizard/step6.html", ctx)


@router.post("/step/6", response_class=HTMLResponse)
async def wizard_step6_submit(
    request: Request,
    slug: str = Form(...),
    name: str = Form(...),
    operation_mode: str = Form("autonomous"),
    channel_type: str = Form("telegram"),
    bot_token: str = Form(""),
    short_pause_hours: int = Form(12),
    long_pause_hours: int = Form(48),
    welcome_message: str = Form(""),
    client_username: str = Form(""),
    client_password: str = Form(""),
):
    import subprocess
    import sys

    cmd = [
        sys.executable, "-m", "scripts.create_tenant",
        "--slug", slug,
        "--name", name,
        "--mode", operation_mode,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    success = result.returncode == 0
    output = (result.stdout + result.stderr).strip()

    # Create the client's panel user tied to this tenant
    client_user_created = False
    client_user_error = ""
    if success and client_username and len(client_password) >= 8:
        try:
            import sqlalchemy as sa
            from app.core.passwords import hash_password
            from app.db.session import async_session_factory

            async with async_session_factory() as session:
                tenant_row = (await session.execute(
                    sa.text("SELECT id FROM public.tenants WHERE slug = :s"), {"s": slug}
                )).fetchone()
                if tenant_row:
                    await session.execute(
                        sa.text(
                            "INSERT INTO public.admin_users (username, password_hash, role, tenant_id) "
                            "VALUES (:u, :p, 'client', :t) "
                            "ON CONFLICT (username) DO NOTHING"
                        ),
                        {
                            "u": client_username.strip().lower(),
                            "p": hash_password(client_password),
                            "t": tenant_row.id,
                        },
                    )
                    await session.commit()
                    client_user_created = True
        except Exception as e:
            client_user_error = str(e)

    ctx = _ctx("6", {
        "slug": slug, "name": name, "operation_mode": operation_mode,
        "success": success, "output": output,
        "webhook_url": f"/webhook/telegram/{slug}" if channel_type == "telegram" else "",
        "client_username": client_username,
        "client_user_created": client_user_created,
        "client_user_error": client_user_error,
    })
    return templates.TemplateResponse(request, "wizard/done.html", ctx)
