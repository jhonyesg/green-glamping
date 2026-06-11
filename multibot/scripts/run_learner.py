"""Script: corre el auto-learner para todos los tenants activos.

Uso:
    python -m scripts.run_learner
    python -m scripts.run_learner --tenant=green-glamping
    python -m scripts.run_learner --since-hours=48

En producción, este script se llama cada 6h desde el lifespan
de la app (ver app/main.py) o desde un cron externo.
"""

import argparse
import asyncio

import sqlalchemy as sa
from loguru import logger

from app.bot.learner import analyze_recent_conversations
from app.db.session import async_session_factory


async def run_for_tenant(tenant_id: int, since_hours: int, min_cluster: int) -> int:
    async with async_session_factory() as session:
        try:
            ids = await analyze_recent_conversations(
                tenant_id=tenant_id,
                session=session,
                since_hours=since_hours,
                min_messages_per_cluster=min_cluster,
            )
            return len(ids)
        except Exception as e:
            logger.exception(f"learner_run_failed tenant={tenant_id} error={e}")
            return 0


async def main(slug: str | None, since_hours: int, min_cluster: int) -> None:
    async with async_session_factory() as session:
        if slug:
            row = (await session.execute(
                sa.text("SELECT id FROM public.tenants WHERE slug=:s"),
                {"s": slug},
            )).fetchone()
            if not row:
                logger.error(f"tenant_not_found slug={slug}")
                return
            tenants = [(row[0], slug)]
        else:
            rows = (await session.execute(
                sa.text(
                    "SELECT id, slug FROM public.tenants "
                    "WHERE status='active' ORDER BY id"
                )
            )).fetchall()
            tenants = [(r[0], r[1]) for r in rows]

    if not tenants:
        logger.warning("learner_no_active_tenants")
        return

    total = 0
    for tid, tslug in tenants:
        n = await run_for_tenant(tid, since_hours, min_cluster)
        logger.info(f"learner_done tenant={tslug} proposals_created={n}")
        total += n
    logger.info(f"learner_total proposals_created={total}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default=None, help="Slug del tenant (default: todos)")
    parser.add_argument("--since-hours", type=int, default=24)
    parser.add_argument("--min-cluster", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(main(args.tenant, args.since_hours, args.min_cluster))
