"""
ARQ worker entrypoint.
Run with: arq app.workers.arq_worker.WorkerSettings
"""

import os
from arq import cron
from app.workers.media_retention import run_media_retention
from app.workers.reminders import send_reservation_reminders


async def startup(ctx):
    from app.config import get_settings
    from app.core.logging import setup_logging
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL, settings.ENVIRONMENT)


class WorkerSettings:
    functions = [run_media_retention, send_reservation_reminders]
    cron_jobs = [
        cron(run_media_retention, hour=3, minute=0),          # 3 AM UTC daily
        cron(send_reservation_reminders, hour={8, 20}, minute=0),  # 8 AM + 8 PM UTC
    ]
    on_startup = startup
    redis_settings_from_dsn = os.getenv("REDIS_URL", "redis://localhost:6379")
