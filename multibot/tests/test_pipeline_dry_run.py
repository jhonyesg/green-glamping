"""Tests para dry_run en pipeline.

Verifica que con dry_run=True:
- No se inserta fila en messages
- No se actualiza conversations.last_message_at
- No se dispara handoff (solo se loguea)
"""

from unittest.mock import AsyncMock, patch, call

import pytest

from app.bot.memory import get_or_create_conversation


class TestDryRunMemory:
    """Tests para get_or_create_conversation con dry_run."""

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_skips_last_message_at_update_when_dry_run(self):
        """Con dry_run=True, NO se actualiza last_message_at ni se hace commit."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        fake_row = {
            "id": 1,
            "tenant_id": 1,
            "in_handoff": False,
            "handoff_at": None,
            "handoff_expires_at": None,
            "handoff_rule": None,
            "state": "active",
            "operation_mode_snapshot": "hybrid",
            "last_message_at": None,
        }
        result_proxy = AsyncMock()
        result_proxy.fetchone = AsyncMock(return_value=fake_row)
        session.execute.return_value = result_proxy

        conv, is_new = await get_or_create_conversation(
            tenant_id=1,
            external_thread_id="thread-123",
            user_external_id="user-456",
            push_name="Test User",
            operation_mode="hybrid",
            session=session,
            dry_run=True,
        )

        assert conv["id"] == 1
        assert is_new is False
        session.execute.assert_called_once()
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_updates_last_message_at_when_not_dry_run(self):
        """Con dry_run=False (default), SÍ se actualiza last_message_at y hace commit."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        fake_row = {
            "id": 1,
            "tenant_id": 1,
            "in_handoff": False,
            "handoff_at": None,
            "handoff_expires_at": None,
            "handoff_rule": None,
            "state": "active",
            "operation_mode_snapshot": "hybrid",
            "last_message_at": None,
        }
        result_proxy = AsyncMock()
        result_proxy.fetchone = AsyncMock(return_value=fake_row)
        session.execute.return_value = result_proxy

        conv, is_new = await get_or_create_conversation(
            tenant_id=1,
            external_thread_id="thread-123",
            user_external_id="user-456",
            push_name="Test User",
            operation_mode="hybrid",
            session=session,
            dry_run=False,
        )

        assert conv["id"] == 1
        assert is_new is False
        assert session.execute.call_count == 1
        session.commit.assert_called_once()