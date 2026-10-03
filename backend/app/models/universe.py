from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.asset import Asset


class Universe(Base):
    """Universe model representing a group of tradable assets (e.g. NIFTY50, NIFTY_BANK)."""

    __tablename__ = "universes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    members: Mapped[list["UniverseMember"]] = relationship(
        "UniverseMember",
        back_populates="universe",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Universe(id={self.id}, name='{self.name}', display_name='{self.display_name}')>"


class UniverseMember(Base):
    """Junction table linking Assets to Universes with optional weightings."""

    __tablename__ = "universe_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    universe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("universes.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    universe: Mapped["Universe"] = relationship("Universe", back_populates="members")
    asset: Mapped["Asset"] = relationship("Asset", back_populates="universe_memberships")

    __table_args__ = (Index("ix_universe_member_unique", "universe_id", "asset_id", unique=True),)

    def __repr__(self) -> str:
        return f"<UniverseMember(universe_id={self.universe_id}, asset_id={self.asset_id})>"
