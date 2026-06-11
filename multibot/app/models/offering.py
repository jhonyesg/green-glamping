import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class OfferingSource(str, enum.Enum):
    seed = "seed"
    manual = "manual"
    auto_learner = "auto_learner"


class Offering(TenantBase):
    """Plan / servicio que ofrece el tenant (combo_5, solo_vuelo, etc.).
    Vive en el schema del tenant. El modelo público `Plan` (suscripción SaaS)
    es distinto y se mantiene sin cambios."""

    __tablename__ = "offering"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio_cop: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    incluye: Mapped[list] = mapped_column(JSONB, default=list)
    imagen_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[OfferingSource] = mapped_column(
        Enum(OfferingSource, name="offering_source"), default=OfferingSource.seed
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
