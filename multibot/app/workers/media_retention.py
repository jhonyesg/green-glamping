"""
ARQ worker: nightly media retention job.
- Marks expired media_assets as quarantined
- Moves quarantined files (>24h) to hard-delete
- Tracks storage freed per day
"""

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sqlalchemy as sa
from loguru import logger

QUARANTINE_AFTER_DAYS = 30
DELETE_AFTER_QUARANTINE_HOURS = 24
MEDIA_ROOT = Path("media")


async def run_media_retention(ctx):
    """
    Main ARQ task. Called nightly by ARQ scheduler.
    ctx contains an async SQLAlchemy session via ctx["db"].
    """
    from app.db.session import async_session_factory

    start = time.monotonic()
    now = datetime.now(timezone.utc)
    stats = {"quarantined": 0, "deleted": 0, "bytes_freed": 0}

    async with async_session_factory() as session:
        # Step 1: fetch all tenants
        tenants = (await session.execute(
            sa.text("SELECT id, slug FROM public.tenants WHERE status='active'")
        )).fetchall()

        for tenant in tenants:
            schema = f"tenant_{tenant.slug}"
            try:
                await session.execute(sa.text(f'SET search_path TO "{schema}", public'))

                # Quarantine: expired TTS cache assets not marked pregenerated
                await session.execute(
                    sa.text(
                        "UPDATE media_assets SET quarantined_at=:now "
                        "WHERE quarantined_at IS NULL AND deleted_at IS NULL "
                        "AND is_pregenerated = false "
                        "AND created_at < :cutoff"
                    ),
                    {"now": now, "cutoff": now - timedelta(days=QUARANTINE_AFTER_DAYS)},
                )

                # Get quarantined rows ready for hard delete
                to_delete = (await session.execute(
                    sa.text(
                        "SELECT id, file_path, size_bytes FROM media_assets "
                        "WHERE quarantined_at IS NOT NULL AND deleted_at IS NULL "
                        "AND quarantined_at < :cutoff"
                    ),
                    {"cutoff": now - timedelta(hours=DELETE_AFTER_QUARANTINE_HOURS)},
                )).fetchall()

                for asset in to_delete:
                    fp = Path(asset.file_path)
                    if fp.exists():
                        size = fp.stat().st_size
                        fp.unlink(missing_ok=True)
                        stats["bytes_freed"] += size
                    await session.execute(
                        sa.text("UPDATE media_assets SET deleted_at=:now WHERE id=:id"),
                        {"now": now, "id": asset.id},
                    )
                    stats["deleted"] += 1

                await session.commit()
                logger.info(f"Media retention complete for tenant {tenant.slug}: {stats}")

            except Exception as e:
                logger.error(f"Media retention failed for tenant {tenant.slug}: {e}")

    elapsed = int((time.monotonic() - start) * 1000)
    logger.info(f"Media retention total: {stats} in {elapsed}ms")
    return stats
