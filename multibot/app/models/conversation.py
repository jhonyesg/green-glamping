import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConversationState(str, enum.Enum):
    active = "active"
    in_handoff = "in_handoff"
    ready_for_payment = "ready_for_payment"
    awaiting_proof = "awaiting_proof"
    confirmed = "confirmed"
    closed = "closed"
    cancelled_by_user = "cancelled_by_user"
    cancelled_by_admin = "cancelled_by_admin"


class LastResponder(str, enum.Enum):
    bot = "bot"
    human = "human"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.tenants.id"), nullable=False, index=True)
    channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_thread_id: Mapped[str] = mapped_column(String(200), nullable=False)
    user_external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    push_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    operation_mode_snapshot: Mapped[str] = mapped_column(String(20), default="hybrid")
    state: Mapped[ConversationState] = mapped_column(
        Enum(ConversationState, name="conversation_state"), default=ConversationState.active
    )
    in_handoff: Mapped[bool] = mapped_column(Boolean, default=False)
    handoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handoff_rule: Mapped[str | None] = mapped_column(String(20), nullable=True)
    handoff_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_responder: Mapped[LastResponder] = mapped_column(
        Enum(LastResponder, name="last_responder"), default=LastResponder.bot
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
