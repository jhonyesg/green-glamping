# Datasets

Conjuntos de entrenamiento y evaluación en formato JSONL (una
conversación o un par `(input, expected_intent)` por línea).

- `dataset_completo.jsonl` → versión base, curada a mano.
- `dataset_expandido.jsonl` → versión augmentada (variaciones de typos,
  sinónimos, reformulaciones).

Estos datasets **no** se cargan en runtime; se usan para:
1. Evaluar el clasificador en CI (`tests/test_classifier.py` carga un subset).
2. Reentrenar / re-ajustar el clasificador cuando cambian los intents.
3. Exportar fixtures de pytest (`/admin/simulate/export-test`).
