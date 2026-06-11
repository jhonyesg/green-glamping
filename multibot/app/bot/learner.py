"""Auto-learner: análisis batch de conversaciones + propuestas de
mejora a la KB.

Funciones principales:
- analyze_recent_conversations(tenant_id, since_hours=24):
  Recolecta mensajes que terminaron en fallback o con baja
  confianza, los agrupa por similitud n-gram, y para cada
  cluster >= min_messages_per_cluster, invoca al LLM con un
  prompt de "propuesta de intent". Persiste cada propuesta en
  public.learner_proposals.
- apply_proposal(proposal_id, edited_payload=None): Aplica
  una propuesta (admin aprobó). Crea snapshot en
  public.intent_versions si modifica un intent existente.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

# ── Tokenización simple (sin embeddings, v1) ──

_WORD_RE = re.compile(r"\w+", re.UNICODE)

# Stop words del español (no agregan señal semántica)
_STOP_WORDS = frozenset({
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "al", "a", "en", "y", "o", "u", "con", "por",
    "para", "que", "se", "es", "son", "está", "están",
    "mi", "tu", "su", "nuestro", "vuestro", "yo", "tú", "él", "ella",
    "sí", "no", "ya", "muy", "más", "menos", "todo", "nada",
})


def _tokenize(text: str) -> set[str]:
    """Tokeniza y filtra stop words. Devuelve set de palabras."""
    text = (text or "").lower()
    tokens = {m.group(0) for m in _WORD_RE.finditer(text)}
    return {t for t in tokens if t not in _STOP_WORDS and len(t) >= 3}


def _cluster_similarity(messages: list[dict], threshold: float = 0.5) -> list[list[dict]]:
    """Clustering naive por Jaccard similarity de tokens.

    Para v1, evitamos embeddings (requieren infraestructura
    adicional). Jaccard es suficiente para detectar mensajes
    que comparten palabras clave. Los clusters resultantes son
    buenos candidatos para intents nuevos.

    Returns: lista de clusters (cada cluster es una lista de
    mensajes).
    """
    clusters: list[list[dict]] = []
    tokens_per_msg = [_tokenize(m["text"]) for m in messages]

    for idx, msg in enumerate(messages):
        if not tokens_per_msg[idx]:
            continue
        placed = False
        for cluster_idx, _ in enumerate(clusters):
            cluster_tokens: set[str] = set()
            for m_idx in range(len(clusters[cluster_idx])):
                cluster_tokens |= tokens_per_msg[m_idx]
            # Jaccard: |A ∩ B| / |A ∪ B|
            intersection = len(tokens_per_msg[idx] & cluster_tokens)
            union = len(tokens_per_msg[idx] | cluster_tokens)
            sim = intersection / union if union else 0.0
            if sim >= threshold:
                clusters[cluster_idx].append(msg)
                placed = True
                break
        if not placed:
            clusters.append([msg])
    return clusters


def _message_hash(text: str) -> str:
    """Hash para identificar mensajes duplicados en la cola
    de propuestas (memoización)."""
    return hashlib.sha256(text.lower().strip().encode("utf-8")).hexdigest()[:16]


# ── LLM call (mockeable en tests) ──

async def _llm_propose_intent(
    sample_messages: list[str],
    existing_intents: list[str],
    session: AsyncSession,
    tenant_id: int,
) -> dict | None:
    """Llama al LLM con un prompt de "propuesta de intent".

    Returns: dict con keys {intent_name, keywords, response,
    confidence} o None si falla.
    """
    from app.llm.base import LLMRequest
    from app.llm.router import route_llm

    system = """Eres un analista de soporte al cliente. Tu trabajo es
analizar mensajes de clientes que el bot no supo responder, y
proponer la creación de un intent nuevo.

REGLAS:
1. Si los mensajes son ruido (greetings, "ok", "gracias"), responde
   "SKIP".
2. Si el intent ya existe en la lista, responde "SKIP".
3. Si vale la pena crear un intent, devuelve JSON con:
   - intent_name (snake_case, max 50 chars)
   - keywords (lista de 3-5 strings para regex)
   - response (texto para responder al cliente)
4. confidence (0..1)
"""
    user = f"""INTENTS EXISTENTES:
{json.dumps(existing_intents, ensure_ascii=False)}

MENSAJES SIN CLASIFICAR:
{json.dumps(sample_messages, ensure_ascii=False, indent=2)}

Devuelve solo el JSON (sin texto antes ni después), o "SKIP" si
no vale la pena crear un intent."""

    try:
        resp = await route_llm(
            LLMRequest(
                system_prompt=system,
                user_prompt=user,
                temperature=0.2,
                max_tokens=400,
                response_format="json_object",
                tenant_id=tenant_id,
            ),
            session,
        )
    except Exception as e:
        logger.warning(f"llm_propose_intent_failed error={e}")
        return None

    # Si dice SKIP, retornar None
    if "SKIP" in resp.text.upper().replace(" ", ""):
        return None

    try:
        data = json.loads(resp.text)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None
    if not data.get("intent_name") or not data.get("response"):
        return None
    return data


# ── Análisis de conversaciones recientes ──


async def analyze_recent_conversations(
    tenant_id: int,
    session: AsyncSession,
    since_hours: int = 24,
    min_messages_per_cluster: int = 3,
    similarity_threshold: float = 0.4,
) -> list[int]:
    """
    Analiza las últimas `since_hours` horas de mensajes del tenant.

    Para cada cluster >= min_messages_per_cluster de mensajes
    que terminaron en fallback o con baja confianza, llama al
    LLM para generar una propuesta. Persiste las propuestas en
    public.learner_proposals.

    Returns: lista de IDs de propuestas creadas.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=since_hours)

    # 1. Recolectar mensajes que terminaron en fallback o con
    # confianza baja
    rows = (await session.execute(
        sa.text(
            "SELECT id, conversation_id, content_text, matched_via, "
            "intent_id "
            "FROM messages "
            "WHERE tenant_id=:tid AND role='user' "
            "AND created_at >= :cutoff "
            "AND (matched_via='fallback' OR matched_via='llm_low_conf') "
            "ORDER BY created_at DESC LIMIT 200"
        ),
        {"tid": tenant_id, "cutoff": cutoff},
    )).fetchall()

    if not rows:
        logger.info(f"learner_no_messages tenant={tenant_id}")
        return []

    # Filtrar por confianza: solo mensajes con confidence < 0.5
    # (o sin confidence guardada = fallback puro)
    msgs = []
    for r in rows:
        msgs.append({
            "id": r.id,
            "conversation_id": r.conversation_id,
            "text": r.content_text or "",
        })

    if not msgs:
        return []

    # 2. Cluster por similitud n-gram
    clusters = _cluster_similarity(msgs, threshold=similarity_threshold)
    big_clusters = [c for c in clusters if len(c) >= min_messages_per_cluster]
    logger.info(
        f"learner_clustered tenant={tenant_id} total={len(msgs)} "
        f"clusters={len(clusters)} big_clusters={len(big_clusters)}"
    )

    if not big_clusters:
        return []

    # 3. Cargar nombres de intents existentes (para evitar duplicados)
    intent_rows = (await session.execute(
        sa.text("SELECT intent_name FROM kb_intents WHERE status='active'")
    )).fetchall()
    existing_intents = [r[0] for r in intent_rows]

    # 4. Para cada cluster, llamar al LLM y persistir propuesta
    created_ids: list[int] = []
    for cluster in big_clusters:
        sample_texts = [m["text"] for m in cluster]

        # Memoización: si ya existe proposal con el mismo source_message_hash,
        # skip (evita duplicados al correr el learner varias veces)
        cluster_hash = _hash_cluster(sample_texts)
        existing = (await session.execute(
            sa.text(
                "SELECT 1 FROM learner_proposals "
                "WHERE source_message_hash=:h LIMIT 1"
            ),
            {"h": cluster_hash},
        )).fetchone()
        if existing:
            logger.debug(f"learner_proposal_duplicate_skip hash={cluster_hash}")
            continue

        proposal = await _llm_propose_intent(
            sample_messages=sample_texts,
            existing_intents=existing_intents,
            session=session,
            tenant_id=tenant_id,
        )
        if proposal is None:
            continue

        # Persistir
        result = await session.execute(
            sa.text(
                "INSERT INTO learner_proposals "
                "(tenant_id, kind, payload, sample_messages, status, "
                " confidence, source_message_hash) "
                "VALUES (:tid, 'create_intent', CAST(:payload AS jsonb), "
                " CAST(:samples AS jsonb), 'pending', :conf, :hash) "
                "RETURNING id"
            ),
            {
                "tid": tenant_id,
                "payload": json.dumps(proposal, ensure_ascii=False),
                "samples": json.dumps(sample_texts, ensure_ascii=False),
                "conf": proposal.get("confidence", 0.5),
                "hash": cluster_hash,
            },
        )
        new_id = result.scalar()
        created_ids.append(new_id)
        logger.info(
            f"learner_proposal_created id={new_id} tenant={tenant_id} "
            f"intent={proposal.get('intent_name')}"
        )

    await session.commit()
    return created_ids


def _hash_cluster(texts: list[str]) -> str:
    """Hash estable para un cluster (concat sorted texts)."""
    return hashlib.sha256(
        "||".join(sorted(t.lower().strip() for t in texts)).encode("utf-8")
    ).hexdigest()[:32]


# ── Aplicar una propuesta (admin aprobó) ──


async def apply_proposal(
    proposal_id: int,
    session: AsyncSession,
    edited_payload: dict | None = None,
    editor: str = "admin",
) -> bool:
    """
    Aplica una propuesta aprobada por el admin.

    Args:
        proposal_id: id del learner_proposal
        edited_payload: si el admin editó la propuesta antes
            de aprobar, usar este payload en vez del original
        editor: username del admin que aprobó

    Returns: True si se aplicó, False si el proposal no
    existe o ya fue procesado.
    """
    row = (await session.execute(
        sa.text(
            "SELECT id, tenant_id, kind, payload, status "
            "FROM learner_proposals WHERE id=:id"
        ),
        {"id": proposal_id},
    )).fetchone()
    if not row:
        return False
    if row.status not in ("pending", "accepted"):
        logger.warning(f"learner_apply_skipped id={proposal_id} status={row.status}")
        return False

    payload = edited_payload or row.payload or {}
    kind = row.kind
    tenant_id = row.tenant_id

    schema = f"tenant_{tenant_id}"
    await session.execute(sa.text(f'SET search_path TO "{schema}", public'))

    if kind == "create_intent":
        intent_name = payload.get("intent_name", "").strip()
        if not intent_name:
            return False
        # Verificar que no exista
        existing = (await session.execute(
            sa.text("SELECT id FROM kb_intents WHERE intent_name=:n"),
            {"n": intent_name},
        )).fetchone()
        if existing:
            logger.info(f"learner_intent_exists id={proposal_id} name={intent_name}")
            await session.execute(
                sa.text(
                    "UPDATE learner_proposals SET status='rejected', "
                    "reviewed_at=NOW(), reviewed_by=:u WHERE id=:id"
                ),
                {"u": editor, "id": proposal_id},
            )
            await session.commit()
            return False

        # Crear intent
        keywords = payload.get("keywords", [])
        if isinstance(keywords, list):
            keywords_regex = "|".join(str(k) for k in keywords)
        else:
            keywords_regex = str(keywords)

        await session.execute(
            sa.text(
                "INSERT INTO kb_intents "
                "(tenant_id, intent_name, keywords_regex, response_text, "
                " priority, status, source) "
                "VALUES (:tid, :name, :kw, :resp, 5, 'active', 'auto_learner')"
            ),
            {
                "tid": tenant_id, "name": intent_name,
                "kw": keywords_regex, "resp": payload.get("response", ""),
            },
        )
        logger.info(f"learner_intent_created tenant={tenant_id} name={intent_name}")

    elif kind == "update_intent":
        intent_name = payload.get("intent_name", "").strip()
        if not intent_name:
            return False
        # Snapshot del estado actual antes de modificar
        await _snapshot_intent(session, tenant_id, intent_name, source="auto_learner")
        # Update
        if "response" in payload:
            await session.execute(
                sa.text("UPDATE kb_intents SET response_text=:r "
                        "WHERE intent_name=:n"),
                {"r": payload["response"], "n": intent_name},
            )
        if "keywords" in payload:
            keywords = payload["keywords"]
            if isinstance(keywords, list):
                keywords_regex = "|".join(str(k) for k in keywords)
                await session.execute(
                    sa.text("UPDATE kb_intents SET keywords_regex=:kw "
                            "WHERE intent_name=:n"),
                    {"kw": keywords_regex, "n": intent_name},
                )
        logger.info(f"learner_intent_updated tenant={tenant_id} name={intent_name}")

    elif kind == "deprecate_intent":
        intent_name = payload.get("to_remove", "").strip()
        if not intent_name:
            return False
        await _snapshot_intent(session, tenant_id, intent_name, source="auto_learner")
        await session.execute(
            sa.text("UPDATE kb_intents SET is_active=false "
                    "WHERE intent_name=:n"),
            {"n": intent_name},
        )
        logger.info(f"learner_intent_deprecated tenant={tenant_id} name={intent_name}")

    # Marcar proposal como applied
    await session.execute(
        sa.text(
            "UPDATE learner_proposals SET "
            "status='applied_edited' WHERE id=:id"
            if edited_payload and edited_payload != row.payload
            else "status='applied' WHERE id=:id"
        ),
        {"id": proposal_id},
    )
    await session.execute(
        sa.text(
            "UPDATE learner_proposals SET "
            "reviewed_at=NOW(), reviewed_by=:u WHERE id=:id"
        ),
        {"u": editor, "id": proposal_id},
    )
    await session.commit()
    return True


async def reject_proposal(
    proposal_id: int, session: AsyncSession, editor: str = "admin"
) -> bool:
    """Marca una propuesta como rejected."""
    await session.execute(
        sa.text(
            "UPDATE learner_proposals SET status='rejected', "
            "reviewed_at=NOW(), reviewed_by=:u WHERE id=:id"
        ),
        {"u": editor, "id": proposal_id},
    )
    await session.commit()
    return True


async def _snapshot_intent(
    session: AsyncSession, tenant_id: int, intent_name: str, source: str
) -> None:
    """Guarda el estado actual de un intent en intent_versions."""
    row = (await session.execute(
        sa.text(
            "SELECT id, intent_name, keywords_regex, response_text, "
            "response_type, response_template, requires_data, "
            "response_media_ids, priority, status, source "
            "FROM kb_intents WHERE intent_name=:n"
        ),
        {"n": intent_name},
    )).fetchone()
    if row is None:
        return
    snapshot = {
        "intent_id": row.id,
        "intent_name": row.intent_name,
        "keywords_regex": row.keywords_regex,
        "response_text": row.response_text,
        "response_type": row.response_type,
        "response_template": row.response_template,
        "requires_data": row.requires_data,
        "response_media_ids": row.response_media_ids,
        "priority": row.priority,
        "status": row.status,
        "source": row.source,
    }
    # Buscar intent_id (no name) en el schema public para FK
    await session.execute(
        sa.text(
            "INSERT INTO public.intent_versions "
            "(tenant_id, intent_id, intent_name, snapshot, source) "
            "VALUES (:tid, :iid, :n, CAST(:snap AS jsonb), :src)"
        ),
        {
            "tid": tenant_id, "iid": row.id, "n": row.intent_name,
            "snap": __import__("json").dumps(snapshot, ensure_ascii=False, default=str),
            "src": source,
        },
    )
