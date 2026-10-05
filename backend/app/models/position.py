from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.asset import Asset


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    EXITED = "EXITED"


class ExitReason(str, Enum):
    SMA_CROSS_DOWN = "sma_cross_down"
    STOP_LOSS = "stop_loss"
    END_OF_DATA = "end_of_data"
    MANUAL = "manual"


class Position(Base):
    """Persistent position tracking for strategy trades."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), ForeignKey("assets.symbol"), nullable=False, index=True)
    status: Mapped[PositionStatus] = mapped_column(
        SAEnum(PositionStatus), default=PositionStatus.OPEN, nullable=False
    )
    # Strategy config
    fast_sma: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    slow_sma: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    atr_window: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    atr_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    cost_bps: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    # Position details
    signal_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entry_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entry_price: Mapped[float] = mapped_column(Float, nullable=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=True, default=1.0)
    # Stop and exit
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_signal: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exit_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # P&L
    gross_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    transaction_cost: Mapped[float] = mapped_column(Float, default=0.0)
    net_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    # Tracking
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    asset: Mapped["Asset"] = relationship("Asset", back_populates="positions")

    def __repr__(self) -> str:
        return (
            f"<Position(id={self.id}, symbol={self.symbol}, "
            f"status={self.status.value}, entry_price={self.entry_price})>"
        )
