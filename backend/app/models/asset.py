from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.universe import UniverseMember


class Asset(Base):
    """Canonical Asset Model representing a tradable financial instrument."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False, default="NSE", index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False, default="EQUITY")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    country: Mapped[str] = mapped_column(String(8), nullable=False, default="IN")
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    provider_symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    universe_memberships: Mapped[list["UniverseMember"]] = relationship(
        "UniverseMember",
        back_populates="asset",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_asset_symbol_exchange", "symbol", "exchange", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Asset(id={self.id}, symbol='{self.symbol}', exchange='{self.exchange}', provider_symbol='{self.provider_symbol}')>"
