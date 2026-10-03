"""Trading strategies: SMA Crossover with ATR Stop-loss."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd

from app.quant.indicators import SimpleMovingAverage, AverageTrueRange


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Trade:
    symbol: str
    entry_time: str
    entry_price: float
    exit_time: str
    exit_price: float
    stop_loss: float
    exit_reason: str
    pnl_pct: float


@dataclass
class StrategyConfig:
    fast_sma: int = 10
    slow_sma: int = 50
    atr_window: int = 14
    atr_multiplier: float = 3.0
    initial_capital: float = 1_000_000.0
    cost_bps: float = 10.0  # round-trip transaction cost in basis points


class BaseStrategy(ABC := object):
    pass


class SMACrossoverStrategy:
    """Long entry when SMA_fast crosses above SMA_slow; exit on reverse or ATR stop."""

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """df must have columns: open, high, low, close, adjusted_close, volume, timestamp.

        Returns a DataFrame with columns: timestamp, signal (BUY/SELL/HOLD),
        fast_sma, slow_sma, atr, stop_loss.
        """
        cfg = self.config
        sma_fast = SimpleMovingAverage(cfg.fast_sma).compute(df)
        sma_slow = SimpleMovingAverage(cfg.slow_sma).compute(df)
        atr = AverageTrueRange(cfg.atr_window, "rma").compute(df)

        out = pd.DataFrame({
            "timestamp": df["timestamp"],
            "fast_sma": sma_fast,
            "slow_sma": sma_slow,
            "atr": atr,
        })

        # Signal: BUY when fast crosses above slow (prev fast <= slow, now fast > slow)
        cross_up = (sma_fast > sma_slow) & (sma_fast.shift(1) <= sma_slow.shift(1))
        cross_down = (sma_fast < sma_slow) & (sma_fast.shift(1) >= sma_slow.shift(1))

        out["signal"] = "HOLD"
        out.loc[cross_up.fillna(False), "signal"] = "BUY"
        out.loc[cross_down.fillna(False), "signal"] = "SELL"

        # Stop-loss price per bar = close - k * ATR
        out["stop_loss"] = out["fast_sma"] - cfg.atr_multiplier * out["atr"]

        return out

    def generate_positions(self, df: pd.DataFrame, prices: pd.DataFrame) -> List[Trade]:
        """Vectorized trade simulation with next-bar-open execution and stop-loss.

        Args:
            df: OHLCV dataframe
            prices: same dataframe (alias for clarity)

        Returns:
            List of completed trade objects
        """
        cfg = self.config
        sig = self.generate_signals(df)
        trades: List[Trade] = []

        position_open = False
        entry_price = 0.0
        entry_time = ""
        stop_loss = 0.0

        for i in range(1, len(sig)):
            row = sig.iloc[i]
            price_row = df.iloc[i]

            if row["signal"] == "BUY" and not position_open:
                # Execute next bar open
                if i + 1 < len(df):
                    entry_price = float(df.iloc[i + 1]["open"])
                    entry_time = str(df.iloc[i + 1]["timestamp"])[:10]
                    stop_loss = entry_price - cfg.atr_multiplier * row["atr"]
                    position_open = True

            if position_open:
                # Check stop-loss intraday
                low_i = float(price_row["low"])
                if low_i <= stop_loss:
                    exit_price = min(float(price_row["open"]), stop_loss)
                    exit_time = str(price_row["timestamp"])[:10]
                    pnl_pct = ((exit_price - entry_price) / entry_price * 100)
                    trades.append(Trade(
                        symbol="*",
                        entry_time=entry_time,
                        entry_price=entry_price,
                        exit_time=exit_time,
                        exit_price=exit_price,
                        stop_loss=stop_loss,
                        exit_reason="stop_loss",
                        pnl_pct=pnl_pct,
                    ))
                    position_open = False
                    continue

                # Check exit signal
                if row["signal"] == "SELL":
                    exit_price = float(price_row["close"])
                    exit_time = str(price_row["timestamp"])[:10]
                    pnl_pct = ((exit_price - entry_price) / entry_price * 100)
                    trades.append(Trade(
                        symbol="*",
                        entry_time=entry_time,
                        entry_price=entry_price,
                        exit_time=exit_time,
                        exit_price=exit_price,
                        stop_loss=stop_loss,
                        exit_reason="sma_cross_down",
                        pnl_pct=pnl_pct,
                    ))
                    position_open = False

        # Force-close open position at last close
        if position_open:
            exit_price = float(df.iloc[-1]["close"])
            exit_time = str(df.iloc[-1]["timestamp"])[:10]
            pnl_pct = ((exit_price - entry_price) / entry_price * 100)
            trades.append(Trade(
                symbol="*",
                entry_time=entry_time,
                entry_price=entry_price,
                exit_time=exit_time,
                exit_price=exit_price,
                stop_loss=stop_loss,
                exit_reason="end_of_data",
                pnl_pct=pnl_pct,
            ))

        return trades
