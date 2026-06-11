import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MessageRole(str, enum.Enum):
    user = "user"
    bot = "bot"
    human = "human"


class MessageContentType(str, enum.Enum):
    text = "text"
    audio = "audio"
    image = "image"
    video = "video"
    document = "document"
    mixed = "mixed"


class MatchedVia(str, enum.Enum):
    regex = "regex"
    llm = "llm"
    exact = "exact"
    fallback = "fallback"
    anti_injection = "anti_injection"


class MessageFeedback(str, enum.Enum):
    none = "none"
    good = "good"
    bad = "bad"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, name="message_role"), nullable=False)
    content_type: Mapped[MessageContentType] = mapped_column(
        Enum(MessageContentType, name="message_content_type"), default=MessageContentType.text
    )
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matched_via: Mapped[MatchedVia] = mapped_column(
        Enum(MatchedVia, name="matched_via"), default=MatchedVia.fallback
    )
    llm_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    feedback: Mapped[MessageFeedback] = mapped_column(
        Enum(MessageFeedback, name="message_feedback"), default=MessageFeedback.none
    )
    feedback_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
