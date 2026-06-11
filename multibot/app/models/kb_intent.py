import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IntentStatus(str, enum.Enum):
    active = "active"
    draft = "draft"
    pending_approval = "pending_approval"


class IntentSource(str, enum.Enum):
    seed = "seed"
    manual = "manual"
    client_feedback = "client_feedback"


class KBIntent(Base):
    __tablename__ = "kb_intents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.tenants.id"), nullable=False, index=True)
    intent_name: Mapped[str] = mapped_column(String(200), nullable=False)
    keywords_regex: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_type: Mapped[str] = mapped_column(String(20), nullable=False, default="static")
    response_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_data: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    response_audio_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_media_ids: Mapped[list] = mapped_column(JSONB, default=list)
    response_image_ids: Mapped[list] = mapped_column(JSONB, default=list)
    handoff_rule: Mapped[str | None] = mapped_column(String(20), nullable=True)
    requires_human: Mapped[bool] = mapped_column(Boolean, default=False)
    human_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[IntentStatus] = mapped_column(
        Enum(IntentStatus, name="intent_status"), default=IntentStatus.active
    )
    source: Mapped[IntentSource] = mapped_column(
        Enum(IntentSource, name="intent_source"), default=IntentSource.seed
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
