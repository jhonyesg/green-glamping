import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class MediaType(str, enum.Enum):
    image = "image"
    audio = "audio"
    document = "document"


class MediaSource(str, enum.Enum):
    seed = "seed"
    uploaded = "uploaded"


class Media(TenantBase):
    """Archivo multimedia del tenant. Se guarda en disco bajo
    data/uploads/<tenant_slug>/<sha256>.<ext> y se expone vía
    StaticFiles montado en /media/<tenant_slug>/."""

    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    tipo: Mapped[MediaType] = mapped_column(
        Enum(MediaType, name="media_type"), nullable=False
    )
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    original_filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    original_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    descripcion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[MediaSource] = mapped_column(
        Enum(MediaSource, name="media_source"), default=MediaSource.uploaded
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
