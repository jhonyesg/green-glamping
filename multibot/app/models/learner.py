"""Modelos del auto-learner y versionado de intents."""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProposalKind(str, enum.Enum):
    create_intent = "create_intent"
    update_intent = "update_intent"
    deprecate_intent = "deprecate_intent"


class ProposalStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    applied = "applied"
    applied_edited = "applied_edited"


class VersionSource(str, enum.Enum):
    seed = "seed"
    manual = "manual"
    auto_learner = "auto_learner"
    revert = "revert"


class LearnerProposal(Base):
    """Propuesta del auto-learner para mejorar la KB del tenant.

    El admin revisa y aprueba/rechaza desde /admin/learner.
    """

    __tablename__ = "learner_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ProposalKind] = mapped_column(
        Enum(ProposalKind, name="proposal_kind"), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sample_messages: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ProposalStatus] = mapped_column(
        Enum(ProposalStatus, name="proposal_status"),
        nullable=False, default=ProposalStatus.pending,
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_message_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.utcnow()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)


class IntentVersion(Base):
    """Snapshot del estado completo de un intent en un momento dado.

    Se crea cada vez que un intent se modifica (manual o auto-learner).
    Permite rollback y auditoría.
    """

    __tablename__ = "intent_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False
    )
    intent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[VersionSource] = mapped_column(
        Enum(VersionSource, name="version_source"),
        nullable=False, default=VersionSource.manual,
    )
    reverted_from: Mapped[int | None] = mapped_column(
        ForeignKey(
            "public.intent_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_intent_version_reverted_from",
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.utcnow()
    )
