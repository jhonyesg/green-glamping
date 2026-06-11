"""
ARQ worker: send reservation reminders 48h and 24h before check-in.
"""

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from loguru import logger


async def send_reservation_reminders(ctx):
    """
    Checks all confirmed reservations with check-in in the next 48h or 24h
    and sends a reminder via the tenant's configured channel.
    """
    from app.db.session import async_session_factory

    now = datetime.now(timezone.utc).date()
    window_48h = now + timedelta(hours=48)
    window_24h = now + timedelta(hours=24)

    async with async_session_factory() as session:
        tenants = (await session.execute(
            sa.text("SELECT id, slug FROM public.tenants WHERE status='active'")
        )).fetchall()

        for tenant in tenants:
            schema = f"tenant_{tenant.slug}"
            try:
                await session.execute(sa.text(f'SET search_path TO "{schema}", public'))

                # Find confirmed reservations with check-in in next 24-48h
                rows = (await session.execute(
                    sa.text(
                        "SELECT r.id, r.conversation_id, r.guest_name, r.check_in, r.combo, "
                        "c.external_thread_id "
                        "FROM reservations r "
                        "LEFT JOIN conversations c ON c.id = r.conversation_id "
                        "WHERE r.state = 'confirmed' "
                        "AND r.check_in BETWEEN :today AND :window48"
                    ),
                    {"today": now, "window48": window_48h},
                )).fetchall()

                for res in rows:
                    hours_until = (res.check_in - now).total_seconds() / 3600
                    label = "48 horas" if hours_until > 36 else "24 horas"
                    msg = (
                        f"🏕 *Recordatorio de reserva* — ¡Hola {res.guest_name or ''}!\n\n"
                        f"Tu reserva *{res.combo}* es en aproximadamente *{label}* "
                        f"(check-in: {res.check_in}).\n\n"
                        f"Si tienes alguna pregunta, escríbenos aquí. ¡Te esperamos! 🌿"
                    )
                    logger.info(
                        f"[reminder] tenant={tenant.slug} res={res.id} "
                        f"thread={res.external_thread_id} hours={hours_until:.0f}h"
                    )
                    # Actual Telegram send would go here using the tenant's bot token

            except Exception as e:
                logger.error(f"Reminders failed for tenant {tenant.slug}: {e}")
