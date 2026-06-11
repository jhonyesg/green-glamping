import uuid
from contextlib import asynccontextmanager

import sqlalchemy as sa
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.webhooks import router as webhooks_router
from app.admin.routes.dashboard import router as dashboard_router
from app.admin.routes.wizard import router as wizard_router
from app.admin.routes.kb import router as kb_router
from app.admin.routes.conversations import router as conversations_router
from app.admin.routes.metrics import router as metrics_router
from app.admin.routes.simulate import router as simulate_router
from app.admin.routes.tts import router as tts_router
from app.admin.routes.reservations import router as reservations_router
from app.admin.routes.auth import router as auth_router
from app.admin.routes.status import router as status_router
from app.admin.routes.users import router as users_router
from app.admin.routes.flow import router as flow_router
from app.admin.routes.llm import router as llm_router
from app.admin.routes.channels import router as channels_router
from app.admin.routes.settings import router as settings_router
from app.admin.routes.plans import router as plans_router, services_alias, api_router as plans_api_router
from app.admin.routes.media import router as media_router, api_router as media_api_router
from app.mcp.server import router as mcp_router
from app.config import get_settings
from app.core.logging import setup_logging
from app.core.media_store import tenant_uploads_dir

settings = get_settings()
setup_logging(settings.LOG_LEVEL, settings.ENVIRONMENT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import engine
    import redis.asyncio as aioredis
    app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    async with engine.connect() as conn:
        await conn.execute(sa.text("SELECT 1"))

    # Arrancar pollers de Telegram (modo polling / auto sin URL pública)
    from app.channels.poller import poller_manager, start_all_pollers
    app.state.poller_manager = poller_manager
    try:
        await start_all_pollers()
    except Exception:
        from loguru import logger
        logger.exception("No se pudieron arrancar los pollers de Telegram")

    yield

    await poller_manager.stop_all()
    await app.state.redis.aclose()
    await engine.dispose()


app = FastAPI(
    title="Multibot",
    description="Plataforma de Atención Multi-Canal multi-tenant",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths under /admin that do NOT require login
_ADMIN_PUBLIC = ("/admin/login", "/admin/static")

# Sections reserved for superadmin role
_SUPERADMIN_ONLY = ("/admin/wizard", "/admin/status", "/admin/tts", "/admin/users",
                    "/admin/llm", "/admin/channels", "/admin/settings")


@app.middleware("http")
async def admin_auth_guard(request: Request, call_next):
    path = request.url.path
    if path.startswith("/admin") and not path.startswith(_ADMIN_PUBLIC):
        from fastapi.responses import RedirectResponse
        if not request.session.get("user"):
            return RedirectResponse(f"/admin/login?next={path}", status_code=303)
        if path.startswith(_SUPERADMIN_ONLY) and request.session.get("role") != "superadmin":
            return RedirectResponse("/admin/", status_code=303)
    response = await call_next(request)
    # Las páginas del panel nunca se cachean — siempre la versión actual
    if path.startswith("/admin") and not path.startswith("/admin/static"):
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Registered last so it wraps the auth guard (outermost = session available inside)
from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="multibot_session",
    max_age=60 * 60 * 12,  # 12 hours
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    from loguru import logger
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/", tags=["root"])
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/admin/", status_code=303)


@app.get("/health", tags=["health"])
async def health(request: Request):
    db_status = "error"
    redis_status = "error"
    try:
        from app.db.session import engine
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
        db_status = "ok"
    except Exception:
        pass
    try:
        await request.app.state.redis.ping()
        redis_status = "ok"
    except Exception:
        pass
    return {"status": "ok", "db": db_status, "redis": redis_status, "version": __version__}


app.include_router(webhooks_router)
app.include_router(dashboard_router)
app.include_router(wizard_router)
app.include_router(kb_router)
app.include_router(conversations_router)
app.include_router(metrics_router)
app.include_router(simulate_router)
app.include_router(tts_router)
app.include_router(reservations_router)
app.include_router(auth_router)
app.include_router(status_router)
app.include_router(users_router)
app.include_router(flow_router)
app.include_router(llm_router)
app.include_router(channels_router)
app.include_router(settings_router)
app.include_router(plans_router)
app.include_router(services_alias)
app.include_router(media_router)
app.include_router(plans_api_router)
app.include_router(media_api_router)
app.include_router(mcp_router)

from pathlib import Path
STATIC_DIR = Path(__file__).parent / "admin" / "static"
app.mount("/admin/static", StaticFiles(directory=str(STATIC_DIR)), name="admin-static")

# Media uploads: /media/<tenant_slug>/<archivo> → data/uploads/<tenant_slug>/
_uploads_root = tenant_uploads_dir()
app.mount(
    "/media",
    StaticFiles(directory=str(_uploads_root), check_dir=False),
    name="media-uploads",
)
