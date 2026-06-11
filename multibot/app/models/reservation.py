"""Reservation model (tenant-scoped)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class Reservation(TenantBase):
    __tablename__ = "reservations"
    __table_args__ = {"schema": "public"}  # overridden per tenant at runtime

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(Integer)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    guest_name: Mapped[str | None] = mapped_column(String(200))
    guest_id_number: Mapped[str | None] = mapped_column(String(50))
    check_in: Mapped[date | None] = mapped_column(Date)
    check_out: Mapped[date | None] = mapped_column(Date)
    combo: Mapped[str | None] = mapped_column(String(100))
    guests_count: Mapped[int] = mapped_column(Integer, default=1)
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    state: Mapped[str] = mapped_column(String(40), default="tentative")
    payment_proof_path: Mapped[str | None] = mapped_column(String(500))
    confirmed_by: Mapped[str | None] = mapped_column(String(200))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
