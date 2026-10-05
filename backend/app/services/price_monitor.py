"""Market hours price monitor for open positions."""
from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List

import pandas as pd

from app.core.config import settings
from app.core.database import db_manager
from app.core.logging import get_logger
from app.data.storage import storage_manager
from app.models.position import Position, PositionStatus
from app.quant.strategies import StrategyConfig, SMACrossoverStrategy
from sqlalchemy import select

logger = get_logger("price_monitor")

# Indian market hours (IST)
MARKET_OPEN_IST = time(9, 15)
MARKET_CLOSE_IST = time(15, 30)
IST_TZ = timezone.utc  # Will be set to Asia/Kolkata when needed

# Configurable refresh interval (seconds)
DEFAULT_REFRESH_INTERVAL = 3600  # 60 minutes


def is_market_hours() -> bool:
    """Check if current time is within Indian market hours (IST)."""
    # Use UTC+5:30 for IST
    ist_offset = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_offset).time()
    return MARKET_OPEN_IST <= now_ist <= MARKET_CLOSE_IST


def get_market_status() -> Dict[str, Any]:
    """Get current market status."""
    ist_offset = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_offset)
    current_time = now_ist.time()
    is_open = MARKET_OPEN_IST <= current_time <= MARKET_CLOSE_IST
    
    # Determine next market open/close
    if is_open:
        next_event = "Close at 15:30 IST"
    elif current_time < MARKET_OPEN_IST:
        next_event = f"Opens in {int((MARKET_OPEN_IST - current_time).total_seconds() / 60)} min"
    else:
        next_event = "Market closed"
    
    return {
        "is_open": is_open,
        "current_time_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "next_event": next_event,
    }


class PositionPriceMonitor:
    """Monitors open positions and updates prices during market hours."""

    def __init__(self, refresh_interval: int = DEFAULT_REFRESH_INTERVAL):
        self.refresh_interval = refresh_interval
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the price monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Position price monitor started")

    async def stop(self):
        """Stop the price monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Position price monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_positions()
                # Sleep for refresh interval
                await asyncio.sleep(self.refresh_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in price monitor loop", error=str(e))
                await asyncio.sleep(60)  # Backoff on error

    async def _check_positions(self):
        """Check all open positions for exit conditions."""
        if db_manager.session_maker is None:
            return

        async with db_manager.session_maker() as db:
            # Get all open positions
            stmt = select(Position).where(
                Position.status == PositionStatus.OPEN
            )
            result = await db.execute(stmt)
            positions = list(result.scalars().all())

            if not positions:
                return

            logger.debug(f"Checking {len(positions)} open positions")

            for position in positions:
                try:
                    await self._check_position(db, position)
                except Exception as e:
                    logger.error(
                        f"Error checking position {position.id} ({position.symbol})",
                        error=str(e),
                    )

    async def _check_position(self, db, position: Position):
        """Check a single position for exit conditions and update price."""
        # Load latest OHLCV data
        df = storage_manager.load_normalized_ohlcv(position.symbol)
        if df.empty:
            return

        # Get latest bar
        latest = df.iloc[-1]
        latest_close = float(latest["close"])
        latest_open = float(latest["open"])
        latest_low = float(latest["low"])
        latest_high = float(latest["high"])
        latest_date = str(latest["timestamp"])[:10]

        # Update current price
        position.current_price = latest_close

        # Check exit conditions using strategy
        cfg = StrategyConfig(
            fast_sma=position.fast_sma,
            slow_sma=position.slow_sma,
            atr_window=position.atr_window,
            atr_multiplier=position.atr_multiplier,
            cost_bps=position.cost_bps,
        )
        strategy = SMACrossoverStrategy(cfg)
        signals = strategy.generate_signals(df)

        # Get current and previous signals
        current_signal = str(signals.iloc[-1]["signal"]) if pd.notna(signals.iloc[-1]["signal"]) else "HOLD"
        prev_signal = str(signals.iloc[-2]["signal"]) if len(signals) > 1 and pd.notna(signals.iloc[-2]["signal"]) else "HOLD"
        current_atr = float(signals.iloc[-1]["atr"]) if pd.notna(signals.iloc[-1]["atr"]) else 0.0

        # Calculate stop price based on entry
        stop_price = position.entry_price - cfg.atr_multiplier * (
            float(signals.iloc[-1]["atr"]) if pd.notna(signals.iloc[-1].get("atr")) else 0.0
        )

        # Update stop price
        position.stop_price = stop_price

        # Check for stop loss
        if latest_low <= stop_price:
            exit_price = min(latest_open, stop_price)
            await self._close_position(
                db, position, latest_date, exit_price, "stop_loss"
            )
            return

        # Check for SMA exit (sell signal on previous bar means we exit next bar)
        if prev_signal == "SELL" and current_signal == "HOLD":
            exit_price = latest_open
            await self._close_position(
                db, position, latest_date, exit_price, "sma_cross_down"
            )
            return

        # Check for new sell signal (exit on next bar)
        if current_signal == "SELL":
            # Will exit on next bar's open
            pass

        # Update last_updated
        from datetime import datetime, timezone
        position.last_updated = datetime.now(timezone.utc)
        await db.commit()

    async def _close_position(
        self, db, position: Position, exit_date: str, exit_price: float, reason: str
    ):
        """Close a position and record P&L."""
        gross_pnl = ((exit_price - position.entry_price) / position.entry_price) * 100
        cost_frac = position.cost_bps / 10000
        net_pnl = gross_pnl - cost_frac * 100

        position.status = PositionStatus.CLOSED
        position.exit_date = exit_date
        position.exit_price = exit_price
        position.exit_reason = reason
        position.exit_signal = reason
        position.gross_pnl = round(gross_pnl, 4)
        position.transaction_cost = round(cost_frac * 100, 4)
        position.net_pnl = round(net_pnl, 4)
        position.current_price = exit_price
        position.last_updated = datetime.now(timezone.utc)

        await db.commit()
        logger.info(
            f"Closed position {position.id} ({position.symbol}): "
            f"exit={exit_price:.2f} reason={reason} pnl={net_pnl:.2f}%"
        )

    def get_market_status(self) -> Dict[str, Any]:
        """Get current market status."""
        return get_market_status()


# Singleton instance
price_monitor = PositionPriceMonitor()
