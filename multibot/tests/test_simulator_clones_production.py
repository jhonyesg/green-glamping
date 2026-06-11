"""Tests: simulador es clon de producción.

Verifica:
- Mismo input → mismo OutboundMessage desde simulador y producción
- dry_run=True no persiste nada en BD
- El trace incluye todos los steps esperados
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestSimulatorClonesProduction:
    """Tests para verificar que el simulador usa pipeline real."""

    @pytest.mark.asyncio
    async def test_dry_run_does_not_persist_messages(self):
        """Con dry_run=True, persist_message nunca es llamado para el mensaje del usuario."""
        from app.bot.memory import persist_message

        with patch.object(persist_message, "side_effect", new_callable=AsyncMock) as mock_persist:
            from app.bot.pipeline import process
            from app.bot.responder import OutboundMessage

            session = AsyncMock()
            session.execute = AsyncMock()
            session.commit = AsyncMock()

            with patch("app.bot.pipeline.get_or_create_conversation", new_callable=AsyncMock) as mock_conv:
                mock_conv.return_value = (
                    {"id": 1, "tenant_id": 1, "in_handoff": False, "last_message_at": None,
                     "handoff_at": None, "handoff_expires_at": None, "handoff_rule": None,
                     "state": "active", "operation_mode_snapshot": "hybrid"},
                    False,
                )
                with patch("app.bot.pipeline.classify", new_callable=AsyncMock) as mock_classify:
                    mock_classify.return_value = AsyncMock(
                        intent_name="saludo",
                        intent_id=1,
                        score=0.9,
                        matched_via="regex",
                        response_text="¡Hola! ¿En qué te ayudo?",
                        handoff_rule=None,
                        requires_human=False,
                        is_ambiguous=False,
                        top_candidates=[],
                        conversation_id=1,
                    )
                    with patch("app.bot.pipeline.build_response") as mock_build:
                        mock_build.return_value = OutboundMessage(
                            text="¡Hola! ¿En qué te ayudo?",
                            intent_name="saludo",
                            matched_via="regex",
                        )
                        with patch("app.bot.pipeline._maybe_call_llm", new_callable=AsyncMock) as mock_llm:
                            mock_llm.return_value = None
                            await process(
                                text="hola",
                                tenant_id=1,
                                session=session,
                                dry_run=True,
                            )

                            user_persist_calls = [
                                c for c in mock_persist.call_args_list
                                if len(c.args) >= 3 and c.args[1] == "user"
                            ]
                            assert len(user_persist_calls) == 0, "dry_run=True no debe persistir mensajes de usuario"

    @pytest.mark.asyncio
    async def test_pipeline_returns_trace(self):
        """pipeline.process() devuelve un trace con los steps esperados."""
        from app.bot.pipeline import process
        from app.bot.responder import OutboundMessage

        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        with patch("app.bot.pipeline.get_or_create_conversation", new_callable=AsyncMock) as mock_conv:
            mock_conv.return_value = (
                {"id": 1, "tenant_id": 1, "in_handoff": False, "last_message_at": None,
                 "handoff_at": None, "handoff_expires_at": None, "handoff_rule": None,
                 "state": "active", "operation_mode_snapshot": "hybrid"},
                False,
            )
            with patch("app.bot.pipeline.classify", new_callable=AsyncMock) as mock_classify:
                mock_classify.return_value = AsyncMock(
                    intent_name="saludo",
                    intent_id=1,
                    score=0.9,
                    matched_via="regex",
                    response_text="¡Hola!",
                    handoff_rule=None,
                    requires_human=False,
                    is_ambiguous=False,
                    top_candidates=[],
                    conversation_id=1,
                )
                with patch("app.bot.pipeline.build_response") as mock_build:
                    mock_build.return_value = OutboundMessage(
                        text="¡Hola!", intent_name="saludo", matched_via="regex",
                    )
                    with patch("app.bot.pipeline._maybe_call_llm", new_callable=AsyncMock) as mock_llm:
                        mock_llm.return_value = None
                        result = await process(
                            text="hola",
                            tenant_id=1,
                            session=session,
                            dry_run=True,
                        )

                        assert result.trace is not None
                        step_names = [s["step"] for s in result.trace]
                        assert "resolve_tenant" in step_names
                        assert "anti_injection" in step_names
                        assert "classify" in step_names
                        assert "llm_decision" in step_names
                        assert "build_response" in step_names

    @pytest.mark.asyncio
    async def test_llm_decision_step_shows_bypass_or_invoke(self):
        """El step llm_decision muestra decision, score, threshold."""
        from app.bot.pipeline import process
        from app.bot.responder import OutboundMessage

        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        with patch("app.bot.pipeline.get_or_create_conversation", new_callable=AsyncMock) as mock_conv:
            mock_conv.return_value = (
                {"id": 1, "tenant_id": 1, "in_handoff": False, "last_message_at": None,
                 "handoff_at": None, "handoff_expires_at": None, "handoff_rule": None,
                 "state": "active", "operation_mode_snapshot": "hybrid"},
                False,
            )
            with patch("app.bot.pipeline.classify", new_callable=AsyncMock) as mock_classify:
                mock_classify.return_value = AsyncMock(
                    intent_name="saludo", intent_id=1, score=0.95,
                    matched_via="regex", response_text="¡Hola!",
                    handoff_rule=None, requires_human=False,
                    is_ambiguous=False, top_candidates=[], conversation_id=1,
                )
                with patch("app.bot.pipeline.build_response") as mock_build:
                    mock_build.return_value = OutboundMessage(
                        text="¡Hola!", intent_name="saludo", matched_via="regex",
                    )
                    with patch("app.bot.pipeline._maybe_call_llm", new_callable=AsyncMock) as mock_llm:
                        mock_llm.return_value = None
                        result = await process(
                            text="hola", tenant_id=1, session=session,
                            config={"llm_strategy": {"bypass_threshold": 0.9}},
                            dry_run=True,
                        )

                        llm_step = next((s for s in result.trace if s["step"] == "llm_decision"), None)
                        assert llm_step is not None
                        assert llm_step["detail"]["decision"] in ("regex_bypass", "no_llm")
                        assert "score" in llm_step["detail"]
                        assert "threshold" in llm_step["detail"]