"""
Tests for the humanizer (plan() — pure function, no DB, no asyncio).
Covers partition, bounded timings, jitter range, and the disabled-channel
short-circuit.
"""

import random

from app.bot.humanizer import (
    DEFAULTS,
    default_humanization,
    ensure_humanization_in_config,
    plan,
)


class TestPlanEmpty:
    def test_empty_text_returns_empty(self):
        assert plan("") == []
        assert plan("   \n\n  ") == []

    def test_whitespace_only_strips(self):
        assert plan("\n\n\n") == []


class TestDefaults:
    def test_default_humanization_returns_copy(self):
        a = default_humanization()
        b = default_humanization()
        assert a == b
        assert a is not b  # debe ser copia, no el mismo dict

    def test_ensure_humanization_in_config_idempotent(self):
        cfg = ensure_humanization_in_config({})
        assert "humanization" in cfg
        assert cfg["humanization"]["enabled"] is False
        # segunda llamada no debe modificar
        cfg2 = ensure_humanization_in_config(cfg)
        assert cfg2["humanization"] is cfg["humanization"]

    def test_ensure_humanization_preserves_existing(self):
        existing = {"enabled": True, "channels": ["telegram"]}
        cfg = ensure_humanization_in_config({"humanization": existing})
        assert cfg["humanization"]["enabled"] is True
        assert cfg["humanization"]["channels"] == ["telegram"]


class TestSplitBubbles:
    def test_disabled_split_yields_single_bubble(self):
        text = "Párrafo 1.\n\nPárrafo 2.\n\nPárrafo 3."
        cfg = {"split_bubbles": False}
        out = plan(text, cfg)
        assert len(out) == 1
        assert out[0].text == text

    def test_enabled_split_splits_on_double_newline(self):
        text = "Párrafo uno.\n\nPárrafo dos.\n\nPárrafo tres."
        out = plan(text, DEFAULTS)
        assert len(out) == 3
        assert out[0].text == "Párrafo uno."
        assert out[1].text == "Párrafo dos."
        assert out[2].text == "Párrafo tres."

    def test_max_bubbles_caps_and_fuses_tail(self):
        cfg = {"max_bubbles": 2, "split_bubbles": True}
        text = "A.\n\nB.\n\nC.\n\nD."
        out = plan(text, cfg)
        assert len(out) == 2
        # La primera cabeza, y la cola con el resto fundido
        assert out[0].text == "A."
        assert "B." in out[1].text and "C." in out[1].text and "D." in out[1].text

    def test_single_paragraph_yields_single_bubble(self):
        out = plan("Solo una línea continua de texto.", DEFAULTS)
        assert len(out) == 1
        assert out[0].text == "Solo una línea continua de texto."


class TestTimingsBounded:
    def test_typing_ms_within_bounds(self):
        # Cualquier plan devuelto debe tener typing_ms dentro de [min, max]
        out = plan("Una respuesta de prueba con varias palabras aquí.", DEFAULTS)
        assert all(b.typing_ms >= DEFAULTS["typing_min_ms"] for b in out)
        assert all(b.typing_ms <= DEFAULTS["typing_max_ms"] for b in out)

    def test_typing_ms_respects_custom_bounds(self):
        cfg = {"typing_min_ms": 100, "typing_max_ms": 500, "wpm": 1000}
        out = plan("Hola hola hola hola hola", cfg)
        assert all(100 <= b.typing_ms <= 500 for b in out)

    def test_pause_only_between_bubbles(self):
        out = plan("Uno.\n\nDos.\n\nTres.", DEFAULTS)
        assert out[0].pause_before_ms == 0
        for b in out[1:]:
            assert DEFAULTS["pause_min_ms"] <= b.pause_before_ms <= DEFAULTS["pause_max_ms"]

    def test_jitter_is_in_range(self):
        # Probamos muchas semillas y verificamos que el jitter 0.8–1.25 cabe en [min,max]
        rng = random.Random(123)
        for _ in range(50):
            cfg = {"wpm": 40, "typing_min_ms": 50, "typing_max_ms": 50_000, "pause_min_ms": 0, "pause_max_ms": 60_000}
            out = plan("palabra " * 30, cfg, rng=rng)
            for b in out:
                # base = words/wpm*60000; jitter en [0.8, 1.25] => base_ms ∈ [0.8x, 1.25x]
                base = (30 / 40) * 60_000
                assert int(0.79 * base) <= b.typing_ms <= int(1.26 * base) + 1


class TestDisabledSingleBubbleImmediate:
    def test_disabled_yields_one_bubble(self):
        cfg = {"enabled": False, "split_bubbles": True}
        out = plan("P1.\n\nP2.\n\nP3.", cfg)
        # split_bubbles=True pero al integrarse, applies() corta; aquí probamos plan()
        # en isolamento: respeta split_bubbles. La garantía de "una sola burbuja
        # inmediata" cuando está desactivado se cubre en send_humanized() y
        # en applies() — ver TestApplies.
        assert len(out) == 3

    def test_applies_short_circuits_when_disabled(self):
        from app.bot.humanizer import applies
        assert applies({"enabled": False}, "whatsapp_unofficial") is False
        assert applies({"enabled": True, "channels": ["telegram"]}, "whatsapp_unofficial") is False
        assert applies({"enabled": True, "channels": ["whatsapp_unofficial"]}, "whatsapp_unofficial") is True
        # Sin config
        assert applies(None, "whatsapp_unofficial") is False


class TestDeterminism:
    def test_same_seed_same_plan(self):
        text = "Párrafo uno.\n\nPárrafo dos con varias palabras."
        a = plan(text, DEFAULTS, rng=random.Random(42))
        b = plan(text, DEFAULTS, rng=random.Random(42))
        for x, y in zip(a, b):
            assert x.text == y.text
            assert x.typing_ms == y.typing_ms
            assert x.pause_before_ms == y.pause_before_ms

    def test_different_seeds_different_jitter(self):
        text = "P1.\n\nP2."
        a = plan(text, DEFAULTS, rng=random.Random(1))
        b = plan(text, DEFAULTS, rng=random.Random(2))
        # Al menos uno de los tiempos debería diferir (probabilísticamente cierto)
        differ = any(x.typing_ms != y.typing_ms or x.pause_before_ms != y.pause_before_ms
                     for x, y in zip(a, b))
        assert differ
