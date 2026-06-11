from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    max_concurrent_chats: Mapped[int] = mapped_column(Integer, default=50)
    channels_included: Mapped[dict] = mapped_column(JSONB, default=dict)
    monthly_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    llm_tokens_included: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
