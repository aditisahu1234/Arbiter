"""Position management service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.position import Position, PositionStatus

logger = get_logger("position_service")


class PositionService:
    """Manages persistent position lifecycle."""

    async def create_position(
        self,
        db: AsyncSession,
        symbol: str,
        signal_date: str,
        entry_date: str,
        entry_price: float,
        fast_sma: int,
        slow_sma: int,
        atr_window: int,
        atr_multiplier: float,
        cost_bps: float,
    ) -> Position:
        """Create a new tracked position."""
        position = Position(
            symbol=symbol.upper(),
            status=PositionStatus.OPEN,
            fast_sma=fast_sma,
            slow_sma=slow_sma,
            atr_window=atr_window,
            atr_multiplier=atr_multiplier,
            cost_bps=cost_bps,
            signal_date=signal_date,
            entry_date=entry_date,
            entry_price=entry_price,
            quantity=1.0,
            stop_price=0.0,
        )
        db.add(position)
        await db.flush()
        await db.refresh(position)
        logger.info(
            "Created position: symbol=%s entry=%s @ %.2f",
            position.symbol, position.entry_date, position.entry_price,
        )
        return position

    async def get_open_positions(
        self, db: AsyncSession, symbol: Optional[str] = None
    ) -> List[Position]:
        """Get all open positions, optionally filtered by symbol."""
        stmt = select(Position).options(selectinload(Position.asset))
        if symbol:
            stmt = stmt.where(Position.symbol == symbol.upper())
        stmt = stmt.where(Position.status == PositionStatus.OPEN)
        stmt = stmt.order_by(Position.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_position(self, db: AsyncSession, position_id: int) -> Optional[Position]:
        """Get a single position by ID."""
        stmt = (
            select(Position)
            .options(selectinload(Position.asset))
            .where(Position.id == position_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_closed_positions(
        self, db: AsyncSession, symbol: Optional[str] = None
    ) -> List[Position]:
        """Get closed/exited positions."""
        stmt = select(Position).options(selectinload(Position.asset))
        if symbol:
            stmt = stmt.where(Position.symbol == symbol.upper())
        stmt = stmt.where(
            Position.status.in_([PositionStatus.CLOSED, PositionStatus.EXITED])
        )
        stmt = stmt.order_by(Position.exit_date.desc().nulls_last())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_position(
        self, db: AsyncSession, position_id: int, updates: Dict[str, Any]
    ) -> Optional[Position]:
        """Update position fields."""
        position = await self.get_position(db, position_id)
        if not position:
            return None
        for key, value in updates.items():
            if hasattr(position, key):
                setattr(position, key, value)
        position.last_updated = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(position)
        return position

    async def close_position(
        self,
        db: AsyncSession,
        position_id: int,
        exit_date: str,
        exit_price: float,
        exit_reason: str,
    ) -> Optional[Position]:
        """Close a position with exit details."""
        position = await self.get_position(db, position_id)
        if not position or position.status != PositionStatus.OPEN:
            return None

        # Calculate P&L
        gross_pnl = ((exit_price - position.entry_price) / position.entry_price) * 100
        cost_frac = position.cost_bps / 10000
        net_pnl = gross_pnl - cost_frac * 100

        await self.update_position(
            db,
            position_id,
            {
                "status": PositionStatus.CLOSED,
                "exit_date": exit_date,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "exit_signal": exit_reason,
                "gross_pnl": round(gross_pnl, 4),
                "transaction_cost": round(cost_frac * 100, 4),
                "net_pnl": round(net_pnl, 4),
                "current_price": exit_price,
            },
        )
        logger.info(
            "Closed position %d: exit=%.2f reason=%s pnl=%.2f%%",
            position_id, exit_price, exit_reason, net_pnl,
        )
        return position

    async def refresh_position_price(
        self, db: AsyncSession, position_id: int, current_price: float
    ) -> Optional[Position]:
        """Update position with latest market price."""
        position = await self.get_position(db, position_id)
        if not position or position.status != PositionStatus.OPEN:
            return None

        await self.update_position(
            db, position_id, {"current_price": current_price}
        )
        return position


position_service = PositionService()
