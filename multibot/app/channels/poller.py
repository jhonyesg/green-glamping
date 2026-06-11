"""
PollerManager: pollers de Telegram (getUpdates) por tenant.

Un asyncio.Task por tenant con backoff exponencial, offset persistido
en bot_config, y detección de conflicto 409 (webhook activo).
"""

import asyncio
import json

import httpx
import sqlalchemy as sa
from loguru import logger


class PollerManager:
    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._states: dict[str, str] = {}  # running | stopped | conflicted | error:<msg>

    # ── API pública ──

    async def start(self, tenant_slug: str, bot_token: str):
        await self.stop(tenant_slug)
        self._states[tenant_slug] = "running"
        self._tasks[tenant_slug] = asyncio.create_task(
            self._poll_loop(tenant_slug, bot_token),
            name=f"tg-poller-{tenant_slug}",
        )
        logger.info(f"[poller] iniciado para {tenant_slug}")

    async def stop(self, tenant_slug: str):
        task = self._tasks.pop(tenant_slug, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        if self._states.get(tenant_slug) == "running":
            self._states[tenant_slug] = "stopped"

    async def stop_all(self):
        for slug in list(self._tasks):
            await self.stop(slug)

    def status(self) -> dict[str, str]:
        return dict(self._states)

    def state_of(self, tenant_slug: str) -> str:
        return self._states.get(tenant_slug, "stopped")

    # ── Loop interno ──

    async def _poll_loop(self, tenant_slug: str, bot_token: str):
        api = f"https://api.telegram.org/bot{bot_token}"
        offset = await self._load_offset(tenant_slug)
        backoff = 1

        from app.api.webhooks import handle_telegram_update

        while True:
            try:
                async with httpx.AsyncClient(timeout=35) as client:
                    resp = await client.get(
                        f"{api}/getUpdates", params={"timeout": 25, "offset": offset}
                    )
                data = resp.json()

                if resp.status_code == 409:
                    self._states[tenant_slug] = "conflicted"
                    logger.warning(
                        f"[poller:{tenant_slug}] 409 — hay un webhook activo. "
                        f"Resolver desde Canales (Tomar el control)."
                    )
                    return

                if not data.get("ok"):
                    raise RuntimeError(data.get("description", "respuesta no ok"))

                backoff = 1
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        result = await handle_telegram_update(tenant_slug, update)
                        logger.info(f"[poller:{tenant_slug}] update → {result.get('status')}")
                    except Exception as e:
                        logger.exception(f"[poller:{tenant_slug}] error procesando update: {e}")
                if data.get("result"):
                    await self._save_offset(tenant_slug, offset)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._states[tenant_slug] = f"error:{str(e)[:60]}"
                logger.warning(f"[poller:{tenant_slug}] {e} — reintento en {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
                self._states[tenant_slug] = "running"

    # ── Offset persistente ──

    async def _load_offset(self, tenant_slug: str) -> int:
        from app.db.session import async_session_factory
        try:
            async with async_session_factory() as s:
                row = (await s.execute(
                    sa.text("SELECT bot_config FROM public.tenants WHERE slug=:s"),
                    {"s": tenant_slug},
                )).fetchone()
                return int(((row.bot_config or {}) if row else {}).get("tg_poll_offset", 0))
        except Exception:
            return 0

    async def _save_offset(self, tenant_slug: str, offset: int):
        from app.db.session import async_session_factory
        try:
            async with async_session_factory() as s:
                await s.execute(
                    sa.text(
                        "UPDATE public.tenants SET bot_config = "
                        "COALESCE(bot_config, '{}'::jsonb) || "
                        "jsonb_build_object('tg_poll_offset', CAST(:o AS int)) "
                        "WHERE slug = :s"
                    ),
                    {"o": offset, "s": tenant_slug},
                )
                await s.commit()
        except Exception as e:
            logger.warning(f"[poller:{tenant_slug}] no se pudo guardar offset: {e}")


poller_manager = PollerManager()


async def resolve_transport(creds: dict) -> str:
    """auto → polling si no hay PUBLIC_BASE_URL global; webhook si la hay."""
    transport = creds.get("transport", "auto")
    if transport != "auto":
        return transport
    from app.config import get_settings
    public = getattr(get_settings(), "PUBLIC_BASE_URL", "") or ""
    return "webhook" if public.startswith("https://") else "polling"


async def sync_tenant_poller(tenant_slug: str):
    """
    Asegura el estado correcto del transporte para el canal Telegram del
    tenant: arranca/detiene el poller y registra/borra el webhook según
    el modo. Llamado al guardar el canal y en el arranque de la app.
    """
    import json as _json
    from app.core.security import decrypt_credentials
    from app.db.session import async_session_factory

    async with async_session_factory() as s:
        try:
            await s.execute(sa.text(f'SET search_path TO "tenant_{tenant_slug}", public'))
            row = (await s.execute(sa.text(
                "SELECT credentials, is_active FROM channels WHERE type='telegram' LIMIT 1"
            ))).fetchone()
        except Exception:
            row = None

    if not row or not row.is_active:
        await poller_manager.stop(tenant_slug)
        return

    creds = row.credentials or {}
    if isinstance(creds, str):
        creds = _json.loads(creds)
    if "encrypted" in creds:
        creds = decrypt_credentials(creds["encrypted"])

    token = creds.get("bot_token", "")
    if not token:
        await poller_manager.stop(tenant_slug)
        return

    from app.channels.telegram import TelegramAdapter
    adapter = TelegramAdapter(bot_token=token)
    transport = await resolve_transport(creds)

    if transport == "polling":
        # Exclusión mutua: el webhook debe estar libre para poder hacer polling
        info = await adapter.get_webhook_info()
        if info.get("ok") and info.get("url"):
            logger.info(f"[poller:{tenant_slug}] webhook ajeno detectado ({info['url']}) — no se arranca polling")
            poller_manager._states[tenant_slug] = "conflicted"
            return
        await poller_manager.start(tenant_slug, token)
    else:  # webhook
        await poller_manager.stop(tenant_slug)
        from app.config import get_settings
        public = getattr(get_settings(), "PUBLIC_BASE_URL", "") or ""
        if public:
            url = f"{public.rstrip('/')}/webhook/telegram/{tenant_slug}"
            await adapter.set_webhook(url, creds.get("secret_token", ""))
            logger.info(f"[poller:{tenant_slug}] webhook registrado: {url}")


async def start_all_pollers():
    """Arranca pollers de todos los tenants activos con canal Telegram."""
    from app.db.session import async_session_factory

    async with async_session_factory() as s:
        tenants = (await s.execute(sa.text(
            "SELECT slug FROM public.tenants WHERE status='active'"
        ))).fetchall()

    for t in tenants:
        try:
            await sync_tenant_poller(t.slug)
        except Exception as e:
            logger.warning(f"[poller] no se pudo sincronizar {t.slug}: {e}")
