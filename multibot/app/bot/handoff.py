"""Handoff logic: trigger, pause detection, resume."""

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

# Configurable windows (can be moved to tenant config)
SHORT_PAUSE_HOURS = 12   # bot stays silent within this window after handoff
LONG_PAUSE_HOURS = 48    # after this window, bot resumes


def is_in_handoff_pause(conversation: dict) -> bool:
    """
    Return True if the conversation is in an active handoff and within the
    short pause window (bot should stay silent).
    """
    if not conversation.get("in_handoff"):
        return False

    expires_at = conversation.get("handoff_expires_at")
    if expires_at is None:
        return True  # no expiry set → stay silent indefinitely until reset

    now = datetime.now(timezone.utc)
    if isinstance(expires_at, str):
        from datetime import datetime as dt
        expires_at = dt.fromisoformat(expires_at)

    return now < expires_at


async def trigger_handoff(
    conversation: dict,
    rule_code: str,
    reason: str,
    session: AsyncSession,
    pause_hours: int | None = None,
) -> None:
    """
    Mark conversation as in_handoff, set expiry, and create a handoff_event.
    pause_hours overrides the default SHORT_PAUSE_HOURS (per-tenant config).
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=pause_hours or SHORT_PAUSE_HOURS)
    conv_id = conversation["id"]

    await session.execute(
        sa.text(
            "UPDATE conversations SET "
            "in_handoff = true, state = 'in_handoff', "
            "handoff_at = :now, handoff_rule = :rule, "
            "handoff_expires_at = :expires "
            "WHERE id = :cid"
        ),
        {"now": now, "rule": rule_code, "expires": expires_at, "cid": conv_id},
    )

    await session.execute(
        sa.text(
            "INSERT INTO handoff_events "
            "(conversation_id, rule_code, triggered_at, expires_at, context_snapshot) "
            "VALUES (:cid, :rule, :now, :expires, :ctx)"
        ),
        {
            "cid": conv_id,
            "rule": rule_code,
            "now": now,
            "expires": expires_at,
            "ctx": sa.cast({"reason": reason}, sa.JSON) if False else f'{{"reason": "{reason}"}}',
        },
    )
    await session.commit()


async def resume_conversation(conversation: dict, session: AsyncSession) -> None:
    """Reset handoff state — bot takes over again."""
    await session.execute(
        sa.text(
            "UPDATE conversations SET "
            "in_handoff = false, state = 'active', "
            "handoff_expires_at = NULL, last_responder = 'bot' "
            "WHERE id = :cid"
        ),
        {"cid": conversation["id"]},
    )
    await session.commit()


def should_resume(conversation: dict, long_pause_hours: int | None = None) -> bool:
    """Return True if enough time has passed that the bot should resume.
    long_pause_hours overrides the default LONG_PAUSE_HOURS (per-tenant config)."""
    handoff_at = conversation.get("handoff_at")
    if handoff_at is None or not conversation.get("in_handoff"):
        return False

    now = datetime.now(timezone.utc)
    if isinstance(handoff_at, str):
        from datetime import datetime as dt
        handoff_at = dt.fromisoformat(handoff_at)

    return (now - handoff_at) > timedelta(hours=long_pause_hours or LONG_PAUSE_HOURS)
