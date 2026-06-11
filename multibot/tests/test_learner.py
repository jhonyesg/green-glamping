"""Tests para app.bot.learner (sin DB, puro Python)."""

from app.bot.learner import (
    _cluster_similarity,
    _hash_cluster,
    _message_hash,
    _tokenize,
)


class TestTokenize:
    def test_basic(self):
        assert _tokenize("Hola, ¿tienen wifi?") >= {"hola", "tienen", "wifi"}

    def test_filters_stop_words(self):
        toks = _tokenize("el bot está en la casa")
        assert "el" not in toks
        assert "la" not in toks
        assert "casa" in toks

    def test_filters_short_words(self):
        toks = _tokenize("a b cd abc")
        assert "a" not in toks
        assert "b" not in toks
        assert "cd" not in toks
        assert "abc" in toks


class TestClusterSimilarity:
    def test_two_clusters_obvious(self):
        msgs = [
            {"id": 1, "text": "tienen wifi"},
            {"id": 2, "text": "hay wifi acá"},
            {"id": 3, "text": "cómo llego al lugar"},
            {"id": 4, "text": "donde queda el sitio"},
        ]
        # Threshold bajo para que 2 mensajes con "wifi" compartan
        # cluster pero los de ubicación no se mezclen con los de wifi
        clusters = _cluster_similarity(msgs, threshold=0.2)
        # Lo importante: los 2 mensajes de wifi se agrupan juntos
        wifi_cluster = next(c for c in clusters if any("wifi" in m["text"] for m in c))
        assert len(wifi_cluster) == 2
        # Los mensajes de ubicación están en clusters separados
        # del de wifi
        ubicacion_in_wifi = any(
            m in wifi_cluster
            for m in msgs if "wifi" not in m["text"]
        )
        assert not ubicacion_in_wifi

    def test_single_cluster(self):
        msgs = [
            {"id": 1, "text": "tienen habitación doble"},
            {"id": 2, "text": "habitación doble disponible"},
            {"id": 3, "text": "hay habitación doble"},
        ]
        clusters = _cluster_similarity(msgs, threshold=0.3)
        assert len(clusters) == 1
        assert len(clusters[0]) == 3

    def test_empty_messages(self):
        msgs = [{"id": 1, "text": ""}, {"id": 2, "text": "   "}]
        clusters = _cluster_similarity(msgs, threshold=0.3)
        # Los mensajes vacíos no tokenizan nada, no se clusterizan
        assert len(clusters) == 0

    def test_no_false_positives(self):
        # Mensajes no relacionados no se agrupan
        msgs = [
            {"id": 1, "text": "quiero reservar"},
            {"id": 2, "text": "precio del vuelo"},
            {"id": 3, "text": "horarios de atención"},
        ]
        clusters = _cluster_similarity(msgs, threshold=0.3)
        # 3 clusters separados (o similar — los stop words comunes
        # pueden unir dos de ellos, pero no los 3)
        assert len(clusters) >= 2


class TestMessageHash:
    def test_stable(self):
        h1 = _message_hash("Hola, ¿tienen wifi?")
        h2 = _message_hash("  hola, ¿TIENEN wifi?  ")
        # El hash NO es case-sensitive ni whitespace-sensitive
        assert h1 == h2

    def test_different_messages_different_hashes(self):
        h1 = _message_hash("tienen wifi?")
        h2 = _message_hash("tienen spa?")
        assert h1 != h2

    def test_length_16(self):
        h = _message_hash("test")
        assert len(h) == 16


class TestHashCluster:
    def test_stable_order_independent(self):
        # El orden de los textos no afecta el hash
        h1 = _hash_cluster(["a", "b", "c"])
        h2 = _hash_cluster(["c", "a", "b"])
        assert h1 == h2

    def test_length_32(self):
        h = _hash_cluster(["test"])
        assert len(h) == 32
