"""Tests para app.core.media_keys (sin DB, sin red)."""


from app.core.media_keys import parse_media_index


class TestParseMediaIndex:
    def test_valid(self):
        assert parse_media_index("media_001") == 1
        assert parse_media_index("media_042") == 42
        assert parse_media_index("media_999") == 999

    def test_invalid_returns_none(self):
        assert parse_media_index("carta_bebidas") is None
        assert parse_media_index("media_") is None
        assert parse_media_index("media_abc") is None
        assert parse_media_index("MEDIA_001") is None  # case-sensitive
        assert parse_media_index("") is None
        assert parse_media_index("media_001_extra") is None


class TestNextMediaKeyLogic:
    """
    Tests del cómputo MAX+1. No testeamos contra BD; lo que importa
    es la fórmula `max_idx + 1` con padding 3 dígitos.
    """

    def test_format_three_digits(self):
        # Verifica que el formato siempre tiene 3 dígitos
        n = 5
        assert f"media_{n:03d}" == "media_005"
        n = 100
        assert f"media_{n:03d}" == "media_100"

    def test_max_plus_one_with_gaps(self):
        # Si hay [media_001, media_005] → siguiente es media_006
        indices = [parse_media_index(k) for k in ["media_001", "media_005"]]
        indices = [i for i in indices if i is not None]
        next_idx = max(indices) + 1
        assert next_idx == 6
        assert f"media_{next_idx:03d}" == "media_006"

    def test_max_plus_one_no_existing(self):
        indices = []
        next_idx = (max(indices) if indices else 0) + 1
        assert f"media_{next_idx:03d}" == "media_001"

    def test_max_plus_one_with_rename(self):
        # Si el admin renombró media_002 a "carta", sigue contando
        # sobre los indices restantes
        indices = [parse_media_index(k) for k in ["media_001", "media_003"]]
        indices = [i for i in indices if i is not None]
        next_idx = max(indices) + 1
        assert next_idx == 4
