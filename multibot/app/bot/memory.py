"""Conversation memory: get/create conversation and persist messages."""

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


async def get_or_create_conversation(
    tenant_id: int,
    external_thread_id: str,
    user_external_id: str,
    push_name: str | None,
    operation_mode: str,
    session: AsyncSession,
) -> tuple[dict, bool]:
    """
    Return (conversation_row_dict, is_new).
    Uses raw SQL so it works with any tenant schema via search_path.
    """
    result = await session.execute(
        sa.text(
            "SELECT id, tenant_id, in_handoff, handoff_at, handoff_expires_at, "
            "handoff_rule, state, operation_mode_snapshot, last_message_at "
            "FROM conversations "
            "WHERE tenant_id = :tid AND external_thread_id = :thread_id "
            "LIMIT 1"
        ),
        {"tid": tenant_id, "thread_id": external_thread_id},
    )
    row = result.fetchone()

    if row:
        # Update last_message_at
        await session.execute(
            sa.text(
                "UPDATE conversations SET last_message_at = NOW() "
                "WHERE tenant_id = :tid AND external_thread_id = :thread_id"
            ),
            {"tid": tenant_id, "thread_id": external_thread_id},
        )
        await session.commit()
        return dict(row._mapping), False

    # Create new conversation
    result = await session.execute(
        sa.text(
            "INSERT INTO conversations "
            "(tenant_id, external_thread_id, user_external_id, push_name, "
            "operation_mode_snapshot, state, in_handoff, last_message_at, created_at) "
            "VALUES (:tid, :thread_id, :user_id, :push_name, :mode, 'active', false, NOW(), NOW()) "
            "RETURNING id, tenant_id, in_handoff, handoff_at, handoff_expires_at, "
            "handoff_rule, state, operation_mode_snapshot, last_message_at"
        ),
        {
            "tid": tenant_id,
            "thread_id": external_thread_id,
            "user_id": user_external_id,
            "push_name": push_name,
            "mode": operation_mode,
        },
    )
    await session.commit()
    row = result.fetchone()
    return dict(row._mapping), True


async def get_recent_turns(
    conversation_id: int,
    session: AsyncSession,
    k: int = 10,
) -> list[dict]:
    result = await session.execute(
        sa.text(
            "SELECT id, role, content_text, intent_id, matched_via, ts "
            "FROM messages "
            "WHERE conversation_id = :cid "
            "ORDER BY ts DESC LIMIT :k"
        ),
        {"cid": conversation_id, "k": k},
    )
    rows = result.fetchall()
    return [dict(r._mapping) for r in reversed(rows)]


async def persist_message(
    conversation_id: int,
    role: str,
    content_text: str | None,
    session: AsyncSession,
    intent_id: int | None = None,
    matched_via: str = "regex",
    latency_ms: int = 0,
) -> int:
    result = await session.execute(
        sa.text(
            "INSERT INTO messages "
            "(conversation_id, role, content_type, content_text, intent_id, "
            "matched_via, llm_tokens_used, latency_ms, feedback, ts) "
            "VALUES (:cid, :role, 'text', :text, :intent_id, :matched_via, 0, :latency, 'none', NOW()) "
            "RETURNING id"
        ),
        {
            "cid": conversation_id,
            "role": role,
            "text": content_text,
            "intent_id": intent_id,
            "matched_via": matched_via,
            "latency": latency_ms,
        },
    )
    await session.commit()
    return result.scalar_one()
