import re
import unicodedata
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


def _normalize(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text


@dataclass
class ClassificationResult:
    intent_name: str
    intent_id: int | None
    score: float
    matched_via: str  # "regex" | "exact" | "fallback"
    response_text: str
    handoff_rule: str | None
    requires_human: bool
    is_ambiguous: bool = False
    top_candidates: list[str] = field(default_factory=list)


FALLBACK_RESPONSE = (
    "No entendí bien tu consulta 🤔\n\n"
    "Puedes preguntarme sobre:\n"
    "• Servicios y combos disponibles\n"
    "• Precios\n"
    "• Cómo reservar\n"
    "• Horarios y ubicación\n\n"
    "¿En qué te ayudo?"
)


async def classify(
    text: str,
    tenant_id: int,
    session: AsyncSession,
) -> ClassificationResult:
    """
    Classify incoming user text against the tenant's KB intents.
    Returns the best match by regex scoring, or a fallback.
    """
    rows = (await session.execute(
        sa.text(
            "SELECT id, intent_name, keywords_regex, response_text, "
            "handoff_rule, requires_human, priority "
            "FROM kb_intents "
            "WHERE tenant_id = :tid AND status = 'active' "
            "ORDER BY priority DESC"
        ),
        {"tid": tenant_id},
    )).fetchall()

    normalized = _normalize(text)
    original_lower = text.lower()

    scores: list[tuple[float, dict]] = []

    for row in rows:
        intent_id, intent_name, keywords_regex, response_text, handoff_rule, requires_human, priority = row
        try:
            pattern = re.compile(keywords_regex, re.IGNORECASE | re.UNICODE)
        except re.error:
            continue

        match = pattern.search(normalized) or pattern.search(original_lower)
        if match:
            # Score = number of non-overlapping matches + priority bonus
            all_matches = pattern.findall(normalized)
            score = len(all_matches) + (priority / 100.0)
            scores.append((score, {
                "intent_id": intent_id,
                "intent_name": intent_name,
                "response_text": response_text,
                "handoff_rule": handoff_rule,
                "requires_human": bool(requires_human),
            }))

    if not scores:
        return ClassificationResult(
            intent_name="fallback",
            intent_id=None,
            score=0.0,
            matched_via="fallback",
            response_text=FALLBACK_RESPONSE,
            handoff_rule=None,
            requires_human=False,
        )

    scores.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scores[0]

    is_ambiguous = False
    top_candidates = [best["intent_name"]]
    if len(scores) > 1:
        second_score, second = scores[1]
        top_candidates.append(second["intent_name"])
        # Ambiguous if top two scores are within 10%
        if best_score > 0 and abs(best_score - second_score) / best_score < 0.10:
            is_ambiguous = True

    return ClassificationResult(
        intent_name=best["intent_name"],
        intent_id=best["intent_id"],
        score=best_score,
        matched_via="regex",
        response_text=best["response_text"],
        handoff_rule=best["handoff_rule"],
        requires_human=best["requires_human"],
        is_ambiguous=is_ambiguous,
        top_candidates=top_candidates,
    )
