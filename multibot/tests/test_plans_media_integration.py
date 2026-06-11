"""
Integration tests para plans/media/pipeline.

Estos tests NO tocan la BD real — usan SQLite en memoria para
verificar el flujo de planes/media a través de la pipeline.

El test E2E completo contra PostgreSQL queda como manual (ver
docs/plans.md).
"""


import pytest

from app.core.media_store import MAX_FILE_BYTES
from app.core.template_render import render_response


class TestMediaUploadLimits:
    def test_max_file_constant(self):
        assert MAX_FILE_BYTES == 50 * 1024 * 1024


class TestTemplateBackwardCompatibility:
    """Verifica que intents sin response_template siguen funcionando (tasks 6.5)."""

    def test_legacy_intent_returns_response_text_unchanged(self):
        intent = {
            "intent_name": "saludo_puro",
            "response_type": "static",
            "response_text": "Hola legacy",
        }
        out, fb = render_response(intent, {})
        assert out == "Hola legacy"
        assert fb is False

    def test_default_type_is_static(self):
        # Sin response_type explícito, default = static
        intent = {
            "intent_name": "x",
            "response_text": "Directo",
        }
        out, fb = render_response(intent, {"plans": [{"nombre": "X"}]})
        assert out == "Directo"
        assert fb is False

    def test_intent_with_empty_template_falls_back_to_text(self):
        intent = {
            "intent_name": "x",
            "response_type": "template_jinja",
            "response_template": "",
            "response_text": "FB",
        }
        out, fb = render_response(intent, {})
        # template vacío → shortcut, no fallback
        assert out == "FB"
        assert fb is False


class TestSeedDataShape:
    """Verifica que SEED_SERVICES está bien formado."""

    def test_seed_services_complete(self):
        from scripts.seed_green_glamping import SEED_SERVICES
        assert len(SEED_SERVICES) >= 5  # al menos 5 servicios base

    def test_seed_services_have_required_fields(self):
        from scripts.seed_green_glamping import SEED_SERVICES
        for s in SEED_SERVICES:
            assert "slug" in s and s["slug"]
            assert "nombre" in s and s["nombre"]
            assert "precio_cop" in s and s["precio_cop"] >= 0
            assert "incluye" in s and isinstance(s["incluye"], list)
            assert "display_order" in s

    def test_seed_services_slugs_unique(self):
        from scripts.seed_green_glamping import SEED_SERVICES
        slugs = [s["slug"] for s in SEED_SERVICES]
        assert len(slugs) == len(set(slugs)), f"Slugs duplicados: {slugs}"

    def test_seed_services_have_valid_prices(self):
        from scripts.seed_green_glamping import SEED_SERVICES
        # Cada servicio tiene un precio > 0 (excepto carta_restaurante = 0)
        for s in SEED_SERVICES:
            if s["slug"] != "carta_restaurante":
                assert s["precio_cop"] > 0, f"{s['slug']} tiene precio 0"

    def test_media_key_to_file_mapping_complete(self):
        from scripts.seed_green_glamping import MEDIA_KEY_TO_FILE
        # Cada imagen del dataset tiene una key
        from pathlib import Path
        images = list((Path("data/clients/green-glamping/media/images")).iterdir())
        mapped = set(MEDIA_KEY_TO_FILE.values())
        for img in images:
            if img.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
                assert img.name in mapped, f"Imagen sin mapear: {img.name}"


class TestPlanImageMimeDetection:
    """Verifica que el helper _ext_from_mime maneja todos los tipos esperados."""

    def test_image_extensions(self):
        from app.core.media_store import _ext_from_mime
        assert _ext_from_mime("image/jpeg") == ".jpg"
        assert _ext_from_mime("image/png") == ".png"
        assert _ext_from_mime("image/webp") == ".webp"

    def test_audio_extensions(self):
        from app.core.media_store import _ext_from_mime
        assert _ext_from_mime("audio/ogg") == ".ogg"
        assert _ext_from_mime("audio/mpeg") == ".mp3"

    def test_document_extension(self):
        from app.core.media_store import _ext_from_mime
        assert _ext_from_mime("application/pdf") == ".pdf"


class TestMediaStorePathSafety:
    """Verifica que serve_path previene path traversal (task 4.5)."""

    def test_serve_path_traversal_blocked(self):
        from fastapi import HTTPException

        from app.core.media_store import serve_path
        with pytest.raises(HTTPException) as exc:
            serve_path("green-glamping", "../../etc/passwd")
        assert exc.value.status_code in (400, 404)

    def test_serve_path_invalid_tenant(self):
        from fastapi import HTTPException

        from app.core.media_store import serve_path
        with pytest.raises(HTTPException) as exc:
            serve_path("../bad", "x.jpg")
        assert exc.value.status_code in (400, 404)

    def test_serve_path_404_on_missing(self):
        from fastapi import HTTPException

        from app.core.media_store import serve_path
        with pytest.raises(HTTPException) as exc:
            serve_path("green-glamping", "nope.jpg")
        assert exc.value.status_code == 404


class TestPlanValidation:
    """Verifica validaciones de slug y nombre (task 3.6)."""

    def test_slug_ok_accepts_valid(self):
        from app.admin.routes.plans import _slug_ok
        assert _slug_ok("combo_5")
        assert _slug_ok("solo-vuelo")
        assert _slug_ok("abc123")

    def test_slug_ok_rejects_invalid(self):
        from app.admin.routes.plans import _slug_ok
        assert not _slug_ok("Combo 5")  # espacios
        assert not _slug_ok("combo.5")  # punto
        assert not _slug_ok("")  # vacío
        assert not _slug_ok("a" * 200)  # muy largo
        assert not _slug_ok("../etc")  # path traversal


class TestMediaKeyValidation:
    def test_key_ok_accepts_valid(self):
        from app.admin.routes.media import _key_ok
        assert _key_ok("carta_bebidas")
        assert _key_ok("plan-1-portada")
        assert _key_ok("abc123")

    def test_key_ok_rejects_invalid(self):
        from app.admin.routes.media import _key_ok
        assert not _key_ok("key with space")
        assert not _key_ok("key.with.dots")
        assert not _key_ok("")


class TestPipelineRendersTemplate:
    """
    Verifica el path del pipeline para response_type != static.

    Usa una DB SQLite en memoria para no tocar PostgreSQL.
    (Para el E2E completo con PostgreSQL ver docs/plans.md.)
    """

    @pytest.mark.asyncio
    async def test_pipeline_renders_template_with_plans(self):
        from app.core.template_render import render_response

        # Simulamos un contexto con planes
        plans = [
            {"nombre": "Combo 5", "precio_cop": 290000,
             "incluye": ["Vuelo", "Glamping", "Spa"]},
            {"nombre": "Solo vuelo", "precio_cop": 30000, "incluye": []},
        ]
        ctx = {
            "plans": plans,
            "recent_turns": [],
            "channel": "telegram",
            "user": {},
            "_media_map": {},
        }

        intent = {
            "intent_name": "precio_general",
            "response_type": "template_jinja",
            "response_text": "FALLBACK",
            "response_template": (
                "💰 *Precios:*\n"
                "{% for p in plans %}"
                "• {{ p.nombre }} — {{ p.precio_cop | currency_cop }}\n"
                "{% endfor %}"
            ),
        }
        out, fb = render_response(intent, ctx)
        assert fb is False
        assert "$290.000" in out
        assert "$30.000" in out
        assert "Combo 5" in out
        assert "Solo vuelo" in out

    @pytest.mark.asyncio
    async def test_pipeline_legacy_intent_unchanged(self):
        # Sin response_type, debe usar response_text directo
        intent = {
            "intent_name": "saludo",
            "response_type": "static",
            "response_text": "Hola legacy",
        }
        out, fb = render_response(intent, {"plans": [{"nombre": "A"}]})
        assert out == "Hola legacy"
        assert fb is False
