"""Reservation lifecycle: create, confirm, remind, cancel."""

from datetime import datetime, timezone

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

PAYMENT_TEMPLATE = (
    "Para confirmar tu reserva de *{combo}* para {guests} persona(s) "
    "del *{check_in}* al *{check_out}*, realiza el pago a:\n\n"
    "💳 *Cuenta:* {account}\n"
    "💰 *Valor:* ${price:,.0f} COP\n\n"
    "Envía el comprobante aquí y lo confirmaremos en máximo 2 horas. 🙌"
)


async def create_reservation(
    conversation_id: int,
    tenant_id: int,
    guest_name: str,
    guest_id: str,
    check_in: str,
    check_out: str,
    combo: str,
    guests_count: int,
    session: AsyncSession,
) -> int:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        sa.text(
            "INSERT INTO reservations "
            "(conversation_id, tenant_id, guest_name, guest_id_number, "
            "check_in, check_out, combo, guests_count, state, created_at, updated_at) "
            "VALUES (:cid, :tid, :name, :gid, :ci, :co, :combo, :gc, 'tentative', :now, :now) "
            "RETURNING id"
        ),
        {
            "cid": conversation_id, "tid": tenant_id, "name": guest_name,
            "gid": guest_id, "ci": check_in, "co": check_out,
            "combo": combo, "gc": guests_count, "now": now,
        },
    )
    await session.commit()
    rid = result.scalar()
    logger.info(f"Reservation {rid} created for tenant {tenant_id}")
    return rid


async def confirm_reservation(
    reservation_id: int, confirmed_by: str, session: AsyncSession
) -> None:
    now = datetime.now(timezone.utc)
    await session.execute(
        sa.text(
            "UPDATE reservations SET state='confirmed', confirmed_by=:by, "
            "confirmed_at=:now, updated_at=:now WHERE id=:id"
        ),
        {"by": confirmed_by, "now": now, "id": reservation_id},
    )
    await session.commit()


async def cancel_reservation(reservation_id: int, reason: str, session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    await session.execute(
        sa.text(
            "UPDATE reservations SET state='cancelled', notes=:reason, "
            "updated_at=:now WHERE id=:id"
        ),
        {"reason": reason, "now": now, "id": reservation_id},
    )
    await session.commit()


def build_payment_message(reservation: dict, account_info: str = "Nequi: 300-xxx-xxxx") -> str:
    return PAYMENT_TEMPLATE.format(
        combo=reservation.get("combo", ""),
        guests=reservation.get("guests_count", 1),
        check_in=reservation.get("check_in", ""),
        check_out=reservation.get("check_out", ""),
        account=account_info,
        price=reservation.get("total_price") or 0,
    )


async def send_reminder(
    reservation: dict,
    hours_before: int,
    session: AsyncSession,
) -> None:
    logger.info(
        f"Reminder: reservation {reservation.get('id')} — "
        f"{hours_before}h before check-in {reservation.get('check_in')}"
    )
    # Actual sending handled by ARQ worker
