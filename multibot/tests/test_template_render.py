"""Tests for app.core.template_render (pure, no DB)."""

import pytest

from app.core.template_render import render_response, render_str


class TestStaticPassthrough:
    def test_response_type_static_returns_text(self):
        intent = {"intent_name": "x", "response_type": "static", "response_text": "Hola"}
        out, fb = render_response(intent, {})
        assert out == "Hola"
        assert fb is False

    def test_no_response_type_defaults_static(self):
        intent = {"intent_name": "x", "response_text": "Hola"}
        out, fb = render_response(intent, {})
        assert out == "Hola"
        assert fb is False

    def test_empty_template_falls_back(self):
        intent = {"intent_name": "x", "response_type": "template_jinja", "response_template": "", "response_text": "fb"}
        out, fb = render_response(intent, {"plans": []})
        assert out == "fb"
        assert fb is False  # no es fallback, es shortcut


class TestJinjaRender:
    def test_simple_substitution(self):
        out = render_str("Hola {{ name }}", {"name": "Mundo"})
        assert out == "Hola Mundo"

    def test_iteration_over_plans(self):
        ctx = {
            "plans": [
                {"nombre": "Combo 5", "precio_cop": 290000},
                {"nombre": "Solo vuelo", "precio_cop": 30000},
            ]
        }
        out = render_str(
            "{% for p in plans %}{{ p.nombre }} {% endfor %}",
            ctx,
        )
        assert out == "Combo 5 Solo vuelo "

    def test_plans_length(self):
        ctx = {"plans": [{"nombre": "A"}, {"nombre": "B"}, {"nombre": "C"}]}
        assert render_str("{{ plans | length }}", ctx) == "3"


class TestFilters:
    def test_currency_cop_format(self):
        assert render_str("{{ 290000 | currency_cop }}", {}) == "$290.000"
        assert render_str("{{ 30000 | currency_cop }}", {}) == "$30.000"
        assert render_str("{{ 1234567 | currency_cop }}", {}) == "$1.234.567"

    def test_currency_cop_invalid_input(self):
        # No se rompe, devuelve string vacío del valor
        assert render_str("{{ 'abc' | currency_cop }}", {}) == "abc"

    def test_media_url_present(self):
        ctx = {"_media_map": {"carta": "/media/green-glamping/abc.jpg"}}
        assert render_str("{{ 'carta' | media_url }}", ctx) == "/media/green-glamping/abc.jpg"

    def test_media_url_absent(self):
        out = render_str("{{ 'no_existe' | media_url }}", {"_media_map": {}})
        assert out == ""

    def test_today_es_format(self):
        out = render_str("{{ today_es() }}", {})
        # Cualquier día de cualquier mes en español
        assert " de " in out
        assert any(m in out for m in [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        ])


class TestSandboxSecurity:
    def test_sa_instance_state_blocked(self):
        # El sandbox bloquea acceso a atributos con "_" o "__"
        from jinja2.sandbox import SecurityError

        class FakeModel:
            _sa_instance_state = "leaked"

        with pytest.raises(SecurityError):
            render_str("{{ x._sa_instance_state }}", {"x": FakeModel()})

    def test_import_blocked(self):
        # El sandbox bloquea acceso a atributos que empiezan con "_" o "__"
        from jinja2.sandbox import SecurityError
        with pytest.raises(SecurityError):
            render_str("{{ ''.__class__.__bases__ }}", {})

    def test_dunder_access_blocked(self):
        from jinja2.sandbox import SecurityError
        with pytest.raises(SecurityError):
            render_str("{{ ''.__class__ }}", {})

    def test_unsafe_attr_blocked_via_response(self):
        intent = {
            "intent_name": "x",
            "response_type": "template_jinja",
            "response_template": "{{ x.__class__ }}",
            "response_text": "FB",
        }
        out, fb = render_response(intent, {"x": "hello"})
        assert out == "FB"
        assert fb is True


class TestFallbackBehavior:
    def test_undefined_variable_falls_back(self):
        intent = {
            "intent_name": "saludo_puro",
            "response_type": "template_jinja",
            "response_template": "Hola {{ user.nombre }}",
            "response_text": "RESPUESTA_FB",
        }
        out, fb = render_response(intent, {})
        assert out == "RESPUESTA_FB"
        assert fb is True

    def test_syntax_error_falls_back(self):
        intent = {
            "intent_name": "x",
            "response_type": "template_jinja",
            "response_template": "{% for p in plans %}{{ p.nombre }}",  # sin endfor
            "response_text": "FB_SYNTAX",
        }
        out, fb = render_response(intent, {"plans": []})
        assert out == "FB_SYNTAX"
        assert fb is True

    def test_data_driven_missing_required_falls_back(self):
        intent = {
            "intent_name": "precios",
            "response_type": "data_driven",
            "response_template": "{% for p in plans %}{{ p.nombre }}{% endfor %}",
            "response_text": "FB_MISSING_DATA",
            "requires_data": ["plans", "media"],
        }
        # Falta "media" en el contexto
        out, fb = render_response(intent, {"plans": []})
        assert out == "FB_MISSING_DATA"
        assert fb is True

    def test_data_driven_with_all_required_renders(self):
        intent = {
            "intent_name": "precios",
            "response_type": "data_driven",
            "response_template": "OK: {{ plans | length }}",
            "response_text": "FB",
            "requires_data": ["plans", "_media_map"],
        }
        out, fb = render_response(intent, {"plans": [1, 2], "_media_map": {}})
        assert out == "OK: 2"
        assert fb is False
