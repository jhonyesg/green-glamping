"""Tests para app.bot.response_parser (pure, sin DB)."""

import json

from app.bot.response_parser import (
    CONFIDENCE_FLOOR,
    parse_llm_response,
    replace_prompt_leak,
)


class TestValidJson:
    def test_full_response(self):
        raw = json.dumps({
            "intent": "info_servicios",
            "response": "¡Hola! Te cuento sobre nuestros combos.",
            "use_media_keys": ["carta_bebidas"],
            "requires_human": False,
            "handoff_rule": None,
            "confidence": 0.85,
            "reasoning": "Cliente pregunta por combos",
        })
        r = parse_llm_response(raw)
        assert r is not None
        assert r.intent == "info_servicios"
        assert r.response == "¡Hola! Te cuento sobre nuestros combos."
        assert r.use_media_keys == ["carta_bebidas"]
        assert r.confidence == 0.85
        assert r.prompt_leak_detected is False

    def test_minimal_response(self):
        raw = json.dumps({"intent": "x", "response": "y"})
        r = parse_llm_response(raw)
        assert r is not None
        assert r.use_media_keys == []
        assert r.confidence == 0.5  # default
        assert r.requires_human is False  # confidence 0.5 > floor

    def test_confidence_clamped(self):
        raw = json.dumps({"intent": "x", "response": "y", "confidence": 5.0})
        r = parse_llm_response(raw)
        assert r.confidence == 1.0

        raw = json.dumps({"intent": "x", "response": "y", "confidence": -1.0})
        r = parse_llm_response(raw)
        assert r.confidence == 0.0


class TestInvalidJson:
    def test_free_text_returns_none(self):
        r = parse_llm_response("Hola, esto no es JSON")
        assert r is None

    def test_empty_returns_none(self):
        assert parse_llm_response("") is None
        assert parse_llm_response("   ") is None

    def test_non_dict_returns_none(self):
        r = parse_llm_response(json.dumps(["array", "not", "dict"]))
        assert r is None

    def test_missing_response_returns_none(self):
        r = parse_llm_response(json.dumps({"intent": "x"}))
        assert r is None

    def test_empty_response_returns_none(self):
        r = parse_llm_response(json.dumps({"intent": "x", "response": "   "}))
        assert r is None

    def test_missing_intent_returns_none(self):
        r = parse_llm_response(json.dumps({"response": "y"}))
        assert r is None

    def test_empty_intent_returns_none(self):
        r = parse_llm_response(json.dumps({"intent": "  ", "response": "y"}))
        assert r is None


class TestPromptLeak:
    def test_soy_bot_detected(self):
        raw = json.dumps({"intent": "x", "response": "Hola, soy un bot"})
        r = parse_llm_response(raw)
        assert r.prompt_leak_detected is True

    def test_soy_ia_detected(self):
        raw = json.dumps({"intent": "x", "response": "Soy una IA entrenada por OpenAI"})
        r = parse_llm_response(raw)
        assert r.prompt_leak_detected is True

    def test_modelo_lenguaje_detected(self):
        raw = json.dumps({
            "intent": "x",
            "response": "Como modelo de lenguaje, no tengo cuerpo físico",
        })
        r = parse_llm_response(raw)
        assert r.prompt_leak_detected is True

    def test_replace_prompt_leak(self):
        raw = json.dumps({"intent": "x", "response": "Soy un bot"})
        r = parse_llm_response(raw)
        assert r.prompt_leak_detected is True
        replaced = replace_prompt_leak(r)
        assert "bot" not in replaced.response.lower() or "asistente" in replaced.response.lower()
        assert replaced.prompt_leak_detected is True

    def test_no_leak_normal_response(self):
        raw = json.dumps({
            "intent": "info_servicios",
            "response": "¡Hola! Te cuento sobre nuestros combos",
        })
        r = parse_llm_response(raw)
        assert r.prompt_leak_detected is False


class TestConfidenceFloor:
    def test_low_confidence_sets_human(self):
        raw = json.dumps({"intent": "x", "response": "y", "confidence": 0.3})
        r = parse_llm_response(raw)
        assert r.requires_human is True

    def test_above_floor_keeps_human_false(self):
        raw = json.dumps({"intent": "x", "response": "y", "confidence": 0.5})
        r = parse_llm_response(raw)
        assert r.requires_human is False

    def test_explicit_human_preserved(self):
        raw = json.dumps({"intent": "x", "response": "y", "confidence": 0.9, "requires_human": True})
        r = parse_llm_response(raw)
        assert r.requires_human is True

    def test_floor_constant(self):
        # 0.4 = CONFIDENCE_FLOOR. Por debajo de esto, escalamos a humano.
        assert CONFIDENCE_FLOOR == 0.4
        raw = json.dumps({"intent": "x", "response": "y", "confidence": 0.4})
        r = parse_llm_response(raw)
        assert r.requires_human is False  # exactamente en el floor


class TestMediaKeys:
    def test_use_media_keys_normalized_to_list(self):
        raw = json.dumps({"intent": "x", "response": "y", "use_media_keys": ["a", "b"]})
        r = parse_llm_response(raw)
        assert r.use_media_keys == ["a", "b"]

    def test_use_media_keys_not_list(self):
        raw = json.dumps({"intent": "x", "response": "y", "use_media_keys": "single_key"})
        r = parse_llm_response(raw)
        assert r.use_media_keys == []

    def test_use_media_keys_none(self):
        raw = json.dumps({"intent": "x", "response": "y", "use_media_keys": None})
        r = parse_llm_response(raw)
        assert r.use_media_keys == []
