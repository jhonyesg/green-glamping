"""LLM provider management (superadmin): configure AI providers per tenant."""

import json
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.security import encrypt_credentials
from app.db.session import async_session_factory

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/llm", tags=["admin-llm"])

PROVIDER_PRESETS = {
    "minimax": {"label": "MiniMax", "base_url": "", "model": ""},
    "openai": {"label": "OpenAI", "base_url": "https://api.openai.com/v1", "model": ""},
    "groq": {"label": "Groq", "base_url": "https://api.groq.com/openai/v1", "model": ""},
    "ollama": {"label": "Ollama (local)", "base_url": "http://localhost:11434/v1", "model": ""},
    "anthropic_compat": {"label": "Otro compatible OpenAI", "base_url": "", "model": ""},
}

# Lista de referencia si no se puede consultar el listado en línea
MINIMAX_MODELS = [
    "MiniMax-M2.1",
    "MiniMax-M2",
    "MiniMax-M1",
    "MiniMax-Text-01",
    "MiniMax-VL-01",
    "abab6.5s-chat",
]

# Endpoints conocidos de MiniMax (internacional y China)
MINIMAX_BASE_CANDIDATES = [
    "https://api.minimax.io/v1",
    "https://api.minimaxi.com/v1",
    "https://api.minimax.chat/v1",
]

_VISION_HINTS = ("vision", "-vl", "vl-", "4o", "gpt-4o", "llava", "pixtral", "gemini",
                 "minicpm-v", "omni", "qwen-vl", "qwen2-vl", "claude")
_AUDIO_HINTS = ("whisper", "audio", "transcribe", "voxtral", "omni", "speech")


def _detect_caps(model_id: str) -> dict:
    m = model_id.lower()
    return {
        "vision": any(h in m for h in _VISION_HINTS),
        "audio": any(h in m for h in _AUDIO_HINTS),
    }


@router.post("/models")
async def llm_fetch_models(
    provider_type: str = Form("minimax"),
    api_key: str = Form(""),
    base_url: str = Form(""),
):
    """Query the provider's API for available models + detected capabilities."""
    import httpx

    if provider_type == "minimax":
        # Intentar el listado real de la cuenta en los endpoints conocidos
        candidates = ([base_url.strip().rstrip("/")] if base_url.strip() else []) + MINIMAX_BASE_CANDIDATES
        if api_key:
            headers = {"Authorization": f"Bearer {api_key}"}
            for url in candidates:
                try:
                    async with httpx.AsyncClient(timeout=8) as client:
                        resp = await client.get(f"{url}/models", headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            ids = sorted({m.get("id", "") for m in data.get("data", []) if m.get("id")})
                            if ids:
                                models = [{"id": m, **_detect_caps(m)} for m in ids]
                                return {"models": models, "source": f"{len(models)} modelos reales desde {url}"}
                except Exception:
                    continue
        # Fallback: lista de referencia (puede estar desactualizada)
        models = [{"id": m, **_detect_caps(m)} for m in MINIMAX_MODELS]
        note = "lista de referencia — " + (
            "no se pudo consultar tu cuenta; verifica la API key" if api_key
            else "pega tu API key y vuelve a pulsar para ver los modelos reales de tu cuenta"
        ) + ". Si usas otro modelo (ej. M2.5), escríbelo manualmente abajo."
        return {"models": models, "source": note}

    url = (base_url.strip() or PROVIDER_PRESETS.get(provider_type, {}).get("base_url", "")).rstrip("/")
    if not url:
        return {"error": "Indica la Base URL del proveedor"}

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{url}/models", headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return {"error": "API key inválida o faltante (401)"}
        return {"error": f"El proveedor respondió {e.response.status_code}"}
    except Exception as e:
        return {"error": f"No se pudo conectar: {str(e)[:100]}"}

    ids = sorted({m.get("id", "") for m in data.get("data", []) if m.get("id")})
    models = [{"id": m, **_detect_caps(m)} for m in ids]
    return {"models": models, "source": f"{len(models)} modelos desde {url}/models"}


@router.get("/", response_class=HTMLResponse)
async def llm_list(request: Request, tenant: str = "green-glamping"):
    schema = f"tenant_{tenant}"
    providers, tenants = [], []
    async with async_session_factory() as session:
        try:
            tenants = (await session.execute(sa.text(
                "SELECT slug, name FROM public.tenants WHERE status='active' ORDER BY slug"
            ))).fetchall()
            await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
            providers = (await session.execute(sa.text(
                "SELECT id, provider_name, model, base_url, capabilities, is_active, priority "
                "FROM llm_providers ORDER BY priority DESC, id"
            ))).fetchall()
        except Exception:
            pass

    return templates.TemplateResponse(request, "llm/list.html", {
        "tenant": tenant, "providers": providers, "tenants": tenants,
        "presets": PROVIDER_PRESETS,
    })


@router.post("/new")
async def llm_create(
    request: Request,
    tenant: str = Form("green-glamping"),
    provider_type: str = Form("minimax"),
    model: str = Form(...),
    api_key: str = Form(""),
    base_url: str = Form(""),
    priority: int = Form(0),
    cap_audio: bool = Form(False),
    cap_vision: bool = Form(False),
):
    schema = f"tenant_{tenant}"
    provider_name = "minimax" if provider_type == "minimax" else "openai_compat"

    tenant_row = None
    async with async_session_factory() as session:
        tenant_row = (await session.execute(
            sa.text("SELECT id FROM public.tenants WHERE slug=:s"), {"s": tenant}
        )).fetchone()
        if not tenant_row:
            return RedirectResponse(f"/admin/llm?tenant={tenant}", status_code=303)

        encrypted_key = encrypt_credentials({"api_key": api_key}) if api_key else None
        # TTS no se configura aquí: la voz va por aparte en /admin/tts
        caps = {"audio_input": cap_audio, "vision": cap_vision}

        import json
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        await session.execute(
            sa.text(
                "INSERT INTO llm_providers "
                "(tenant_id, provider_name, model, api_key, base_url, capabilities, priority, is_active) "
                "VALUES (:tid, :pn, :m, :k, :b, CAST(:c AS jsonb), :p, true)"
            ),
            {
                "tid": tenant_row.id, "pn": provider_name, "m": model.strip(),
                "k": encrypted_key, "b": base_url.strip() or None,
                "c": json.dumps(caps), "p": priority,
            },
        )
        await session.commit()

    return RedirectResponse(f"/admin/llm?tenant={tenant}", status_code=303)


@router.post("/{provider_id}/toggle")
async def llm_toggle(request: Request, provider_id: int, tenant: str = "green-glamping"):
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        await session.execute(
            sa.text("UPDATE llm_providers SET is_active = NOT is_active WHERE id=:id"),
            {"id": provider_id},
        )
        await session.commit()
    return RedirectResponse(f"/admin/llm?tenant={tenant}", status_code=303)


@router.post("/{provider_id}/delete")
async def llm_delete(request: Request, provider_id: int, tenant: str = "green-glamping"):
    schema = f"tenant_{tenant}"
    async with async_session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
        await session.execute(
            sa.text("DELETE FROM llm_providers WHERE id=:id"), {"id": provider_id}
        )
        await session.commit()
    return RedirectResponse(f"/admin/llm?tenant={tenant}", status_code=303)


# ── LLM Strategy (config del modo llm_first) ──

DEFAULT_LLM_STRATEGY = {
    "mode": "regex_first",
    "bypass_llm_on_high_regex_score": True,
    "bypass_threshold": 0.9,
    "max_llm_calls_per_message": 1,
    "max_llm_calls_per_conversation_per_hour": 20,
    "auto_learner": {
        "enabled": True,
        "schedule": "every_6_hours",
        "min_messages_per_cluster": 3,
    },
}


@router.get("/strategy", response_class=HTMLResponse)
async def llm_strategy_form(request: Request, tenant: str = "green-glamping"):
    """Form para editar la config llm_strategy del bot_config del tenant."""
    async with async_session_factory() as session:
        await session.execute(sa.text('SET search_path TO "public"'))
        row = (await session.execute(
            sa.text("SELECT bot_config FROM public.tenants WHERE slug=:s"),
            {"s": tenant},
        )).fetchone()
        bot_config = row[0] if row and row[0] else {}
        tenants = (await session.execute(
            sa.text("SELECT slug FROM public.tenants WHERE status='active' ORDER BY slug")
        )).fetchall()

    current = (bot_config or {}).get("llm_strategy") or DEFAULT_LLM_STRATEGY
    return templates.TemplateResponse(request, "llm/strategy.html", {
        "tenant": tenant,
        "tenants": [t[0] for t in tenants],
        "current": current,
        "saved": request.query_params.get("saved"),
    })


@router.post("/strategy")
async def llm_strategy_save(
    request: Request,
    tenant: str = Form(...),
    mode: str = Form("regex_first"),
    bypass_enabled: str = Form("false"),
    bypass_threshold: float = Form(0.9),
    max_calls_per_message: int = Form(1),
    max_calls_per_hour: int = Form(20),
    auto_learner_enabled: str = Form("true"),
    auto_learner_schedule: str = Form("every_6_hours"),
    auto_learner_min_cluster: int = Form(3),
):
    """Guarda la config llm_strategy en bot_config del tenant."""
    strategy = {
        "mode": mode,
        "bypass_llm_on_high_regex_score": bypass_enabled == "true",
        "bypass_threshold": max(0.0, min(1.0, bypass_threshold)),
        "max_llm_calls_per_message": max(0, max_calls_per_message),
        "max_llm_calls_per_conversation_per_hour": max(0, max_calls_per_hour),
        "auto_learner": {
            "enabled": auto_learner_enabled == "true",
            "schedule": auto_learner_schedule,
            "min_messages_per_cluster": max(2, auto_learner_min_cluster),
        },
    }

    async with async_session_factory() as session:
        await session.execute(sa.text('SET search_path TO "public"'))
        row = (await session.execute(
            sa.text("SELECT bot_config FROM public.tenants WHERE slug=:s"),
            {"s": tenant},
        )).fetchone()
        bot_config = dict(row[0] or {})
        bot_config["llm_strategy"] = strategy
        await session.execute(
            sa.text("UPDATE public.tenants SET bot_config=CAST(:c AS jsonb) WHERE slug=:s"),
            {"c": json.dumps(bot_config, ensure_ascii=False),
             "s": tenant},
        )
        await session.commit()

    return RedirectResponse(
        f"/admin/llm/strategy?tenant={tenant}&saved=ok", status_code=303
    )
