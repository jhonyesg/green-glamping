import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OperationMode(str, enum.Enum):
    autonomous = "autonomous"
    assisted = "assisted"
    hybrid = "hybrid"


class TenantStatus(str, enum.Enum):
    provisioning = "provisioning"
    active = "active"
    suspended = "suspended"
    archived = "archived"


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    operation_mode: Mapped[OperationMode] = mapped_column(
        Enum(OperationMode, schema="public"), default=OperationMode.hybrid
    )
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, schema="public"), default=TenantStatus.provisioning
    )
    plan_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("public.plans.id"), nullable=True
    )
    retention_days: Mapped[int] = mapped_column(Integer, default=90)
    payment_message_template: Mapped[dict] = mapped_column(JSONB, default=dict)
    welcome_variant: Mapped[str] = mapped_column(String(50), default="default")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    contact_info: Mapped[dict] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def schema_name(self) -> str:
        return f"tenant_{self.slug}"

    def is_active(self) -> bool:
        return self.status == TenantStatus.active

    def set_schema_search_path(self, session) -> None:
        import sqlalchemy as sa
        session.execute(sa.text(f"SET search_path TO {self.schema_name}, public"))
