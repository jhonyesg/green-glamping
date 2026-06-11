from dataclasses import dataclass, field

from app.bot.classifier import ClassificationResult


@dataclass
class OutboundMessage:
    text: str
    handoff_rule: str | None = None
    requires_human: bool = False
    intent_name: str = "fallback"
    matched_via: str = "fallback"
    media_attachments: list[int] = field(default_factory=list)


def build_response(classification: ClassificationResult) -> OutboundMessage:
    return OutboundMessage(
        text=classification.response_text,
        handoff_rule=classification.handoff_rule,
        requires_human=classification.requires_human,
        intent_name=classification.intent_name,
        matched_via=classification.matched_via,
    )
