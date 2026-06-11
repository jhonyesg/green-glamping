"""Tests para el modo LLM-first de la pipeline.

Mockeamos el LLM para verificar:
- Modo regex_first: nunca se invoca
- Bypass por score alto: ahorra la llamada
- LLM invocado y JSON válido: respuesta del LLM gana
- LLM devuelve JSON inválido: fallback al regex
- Confidence baja: escala a humano
- Prompt leak: se reemplaza la respuesta
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.bot.response_parser import parse_llm_response, replace_prompt_leak


def _make_classification(matched_via="regex", score=0.5, ambiguous=False):
    return SimpleNamespace(
        intent_name="horarios",
        intent_id=42,
        score=score,
        matched_via=matched_via,
        response_text="HORARIOS RESPONSE",
        handoff_rule=None,
        requires_human=False,
        is_ambiguous=ambiguous,
        top_candidates=[],
        conversation_id=1,
    )


def _make_cfg(mode="llm_first", **overrides):
    base = {
        "llm_strategy": {
            "mode": mode,
            "bypass_llm_on_high_regex_score": True,
            "bypass_threshold": 0.9,
            "max_llm_calls_per_message": 1,
            "max_llm_calls_per_conversation_per_hour": 20,
        },
        "memory_turns": 10,
        "_tenant_name": "Green Glamping",
    }
    base.update(overrides)
    return base


class TestParseIntegration:
    """Tests de integración entre response_parser y las constantes de la pipeline."""

    def test_valid_json_full(self):
        raw = json.dumps({
            "intent": "info_servicios",
            "response": "Te cuento sobre los combos disponibles",
            "use_media_keys": ["carta_bebidas"],
            "requires_human": False,
            "confidence": 0.9,
            "reasoning": "Cliente pregunta por combos",
        })
        r = parse_llm_response(raw)
        assert r is not None
        assert r.intent == "info_servicios"
        assert r.confidence == 0.9
        assert r.use_media_keys == ["carta_bebidas"]

    def test_invalid_json_falls_back_to_none(self):
        # La pipeline debe continuar con el regex match
        assert parse_llm_response("hola mundo sin json") is None

    def test_prompt_leak_replaced(self):
        raw = json.dumps({
            "intent": "x", "response": "Soy un bot asistente",
        })
        r = parse_llm_response(raw)
        assert r is not None
        assert r.prompt_leak_detected is True
        reemplazado = replace_prompt_leak(r)
        assert "bot" not in reemplazado.response.lower()
        assert reemplazado.prompt_leak_detected is True

    def test_low_confidence_escalates_to_human(self):
        raw = json.dumps({
            "intent": "x", "response": "y", "confidence": 0.3,
        })
        r = parse_llm_response(raw)
        assert r.requires_human is True


class TestLogic:
    """Tests de la lógica de bypass y rate limit (sin DB real)."""

    def test_regex_first_mode_skips_llm(self):
        # Si el cfg dice regex_first, _maybe_call_llm retorna None
        # antes de invocar al LLM.
        from app.bot.pipeline import _maybe_call_llm

        classification = _make_classification(matched_via="regex", score=0.5)
        cfg = _make_cfg(mode="regex_first")

        # Mock del LLM router — si se invoca, el test falla.
        with patch("app.llm.router.route_response_generation") as mock_llm:
            mock_llm.return_value = AsyncMock(
                text='{"intent": "x", "response": "y"}'
            )()
            result = asyncio_run(_maybe_call_llm(
                text="hola", tenant_id=1, session=None,
                cfg=cfg, recent_turns=[], regex_classification=classification,
            ))
        assert result is None
        assert not mock_llm.called

    def test_bypass_with_high_score_skips_llm(self):
        from app.bot.pipeline import _maybe_call_llm

        classification = _make_classification(matched_via="regex", score=1.5)
        cfg = _make_cfg(mode="llm_first", bypass_threshold=0.9)

        with patch("app.llm.router.route_response_generation") as mock_llm:
            mock_llm.return_value = AsyncMock(
                text='{"intent": "x", "response": "y"}'
            )()
            result = asyncio_run(_maybe_call_llm(
                text="hola", tenant_id=1, session=None,
                cfg=cfg, recent_turns=[], regex_classification=classification,
            ))
        assert result is None
        assert not mock_llm.called

    def test_bypass_with_low_score_invocates_llm(self):
        # Si el score es bajo (< threshold), se invoca al LLM.
        from app.bot.pipeline import _maybe_call_llm

        classification = _make_classification(matched_via="regex", score=0.5)
        cfg = _make_cfg(mode="llm_first", bypass_threshold=0.9)

        async def _fake_kb(tenant_id, session, recent_turns, cfg):
            return {"plans": [], "intents": [], "handoff_rules": [], "media_keys": []}

        with patch("app.bot.pipeline._check_llm_rate_limit", AsyncMock(return_value=True)):
            with patch("app.bot.pipeline._load_kb_for_llm", _fake_kb):
                with patch("app.bot.pipeline._tenant_slug", return_value="x"):
                    async def _fake_llm_call(*args, **kwargs):
                        from app.llm.base import LLMResponse
                        return LLMResponse(
                            text='{"intent": "info", "response": "OK", "confidence": 0.8}',
                            model="test", provider="test",
                        )
                    with patch("app.bot.pipeline.route_response_generation", _fake_llm_call):
                        result = asyncio_run(_maybe_call_llm(
                            text="hola", tenant_id=1, session=None,
                            cfg=cfg, recent_turns=[],
                            regex_classification=classification,
                        ))
        assert result is not None
        assert result.intent == "info"

    def test_bypass_disabled_with_high_score_invocates_llm(self):
        from app.bot.pipeline import _maybe_call_llm

        classification = _make_classification(matched_via="regex", score=1.5)
        cfg = _make_cfg(mode="llm_first", bypass_threshold=0.9)
        cfg["llm_strategy"]["bypass_llm_on_high_regex_score"] = False

        async def _fake_kb(tenant_id, session, recent_turns, cfg):
            return {"plans": [], "intents": [], "handoff_rules": [], "media_keys": []}

        with patch("app.bot.pipeline._check_llm_rate_limit", AsyncMock(return_value=True)):
            with patch("app.bot.pipeline._load_kb_for_llm", _fake_kb):
                with patch("app.bot.pipeline._tenant_slug", return_value="green-glamping"):
                    async def _fake_llm_call(*args, **kwargs):
                        from app.llm.base import LLMResponse
                        return LLMResponse(
                            text='{"intent": "info", "response": "LLM RESPONSE", "confidence": 0.8}',
                            model="test", provider="test",
                        )
                    with patch("app.bot.pipeline.route_response_generation", _fake_llm_call):
                        result = asyncio_run(_maybe_call_llm(
                            text="hola", tenant_id=1, session=None,
                            cfg=cfg, recent_turns=[],
                            regex_classification=classification,
                        ))
        assert result is not None
        assert result.intent == "info"

    def test_ambiguous_score_invocates_llm(self):
        from app.bot.pipeline import _maybe_call_llm

        classification = _make_classification(
            matched_via="regex", score=0.7, ambiguous=True
        )
        cfg = _make_cfg(mode="llm_first", bypass_threshold=0.9)

        async def _fake_kb(tenant_id, session, recent_turns, cfg):
            return {"plans": [], "intents": [], "handoff_rules": [], "media_keys": []}

        with patch("app.bot.pipeline._check_llm_rate_limit", AsyncMock(return_value=True)):
            with patch("app.bot.pipeline._load_kb_for_llm", _fake_kb):
                with patch("app.bot.pipeline._tenant_slug", return_value="x"):
                    async def _fake_llm_call(*args, **kwargs):
                        from app.llm.base import LLMResponse
                        return LLMResponse(
                            text='{"intent": "info", "response": "OK", "confidence": 0.8}',
                            model="test", provider="test",
                        )
                    with patch("app.bot.pipeline.route_response_generation", _fake_llm_call):
                        result = asyncio_run(_maybe_call_llm(
                            text="hola", tenant_id=1, session=None,
                            cfg=cfg, recent_turns=[],
                            regex_classification=classification,
                        ))
        assert result is not None
        assert result.intent == "info"


# Helpers
def asyncio_run(coro):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro)


async def _async_return(value):
    return value
