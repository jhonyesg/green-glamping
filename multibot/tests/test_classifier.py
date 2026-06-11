"""
Classifier tests using a mock DB session against Green Glamping KB.
These tests load the seed JSON directly so they don't need a live database.
"""

import json
import re
import unicodedata
from pathlib import Path

import pytest

SEED_FILE = Path(__file__).parent.parent / "data" / "seeds" / "green_glamping_kb.json"
SEED = json.loads(SEED_FILE.read_text())
INTENTS = SEED["intents"]


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text


def classify_offline(text: str) -> str | None:
    """Mini classifier replicating the logic, using seed JSON."""
    normalized = _normalize(text)
    original_lower = text.lower()
    scores: list[tuple[float, str]] = []

    for intent in INTENTS:
        try:
            pattern = re.compile(intent["keywords_regex"], re.IGNORECASE | re.UNICODE)
        except re.error:
            continue
        match = pattern.search(normalized) or pattern.search(original_lower)
        if match:
            all_matches = pattern.findall(normalized)
            score = len(all_matches) + (intent.get("priority", 5) / 100.0)
            scores.append((score, intent["intent_name"]))

    if not scores:
        return None
    scores.sort(reverse=True)
    return scores[0][1]


# (input_text, expected_intent)
CLASSIFIER_CASES = [
    # Saludos
    ("hola", "saludo_puro"),
    ("buenos días", "saludo_puro"),
    ("buenas tardes", "saludo_puro"),
    ("Hola!", "saludo_puro"),
    # Precios
    ("cuánto cuesta", "precio_general"),
    ("cuánto vale el combo 5", "precio_general"),
    ("lista de precios", "precio_general"),
    ("cuánto es el parapente", "precio_general"),
    # Mascotas
    ("puedo llevar mi mascota", "mascotas"),
    ("hay pet friendly", "mascotas"),
    ("llevar a mi perro", "mascotas"),
    # Reservar
    ("cómo reservo", "como_reservar"),
    ("komo reservo", "como_reservar"),      # typo
    ("quiero apartar una fecha", "como_reservar"),
    # Servicios
    ("qué servicios tienen", "info_servicios"),
    ("muéstrame los combos", "info_servicios"),
    ("qué planes hay", "info_servicios"),
    # Ubicación
    ("dónde están", "ubicacion"),
    ("cómo llego", "ubicacion"),
    ("dirección", "ubicacion"),
    # Datos de pago
    ("me pasas los datos de pago", "datos_pago"),
    ("cuál es el nequi", "datos_pago"),
    # Horarios
    ("horarios", "horarios"),
    ("a qué hora cierran", "horarios"),
    ("check-in", "horarios"),
    # Clima
    ("y si llueve", "clima_lluvia"),
    ("qué pasa con el clima", "clima_lluvia"),
    # Combos
    ("combo 5", "seleccion_combo"),
    ("glamping montaña", "seleccion_combo"),
    ("quiero el combo aniversario", "seleccion_combo"),
    # Menores
    ("puedo ir con mi bebé", "menores_bebes"),
    ("niños pueden ir", "menores_bebes"),
    # Typos / abreviaciones
    ("glampin", "seleccion_combo"),
    ("penti", "seleccion_combo"),
    ("kars", "seleccion_combo"),
    ("wifi", "wifi"),
    # Handoff intents
    ("quiero hablar con una persona", "hablar_humano"),
    ("me comunicas con un asesor", "hablar_humano"),
    ("pésimo servicio", "queja"),
    # Descuento (objecion)
    ("me puedes dar descuento", "objecion_descuento"),
    ("tienen promo", "objecion_descuento"),
    # Despedida
    ("gracias", "despedida"),
    ("chao", "despedida"),
]


@pytest.mark.parametrize("text, expected", CLASSIFIER_CASES)
def test_classifier(text: str, expected: str):
    result = classify_offline(text)
    assert result == expected, (
        f"classify_offline({text!r}) → {result!r}, expected {expected!r}"
    )
