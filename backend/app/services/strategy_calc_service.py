"""Strategy calculation engine for position tracking."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.quant.indicators import SimpleMovingAverage, AverageTrueRange, TrueRange
from app.quant.strategies import StrategyConfig, SMACrossoverStrategy


@dataclass
class DailyCalculation:
    """Single bar's strategy calculation result."""
    date: str
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    fast_sma: Optional[float]
    slow_sma: Optional[float]
    prev_fast_sma: Optional[float]
    prev_slow_sma: Optional[float]
    true_range: Optional[float]
    atr: Optional[float]
    signal: str  # BUY, SELL, HOLD
    stop_price: Optional[float]
    # Execution details (filled during backtest)
    entry_date: Optional[str] = None
    entry_price: Optional[float] = None
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    position: Optional[str] = None  # OPEN, CLOSED


@dataclass
class StrategyCalculationResult:
    """Full strategy calculation results."""
    symbol: str
    config: StrategyConfig
    calculations: List[DailyCalculation]
    signals: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]
    strategy_date: Optional[str] = None
    selected_calculation: Optional[DailyCalculation] = None


class StrategyCalcEngine:
    """Computes daily strategy calculations for position tracking."""

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()

    def compute_daily(self, df: pd.DataFrame, strategy_date: Optional[str] = None) -> List[DailyCalculation]:
        """Compute strategy signals for each bar with next-bar execution."""
        cfg = self.config
        strategy = SMACrossoverStrategy(cfg)
        signals_df = strategy.generate_signals(df)

        # Add True Range column
        tr = TrueRange().compute(df)
        signals_df["true_range"] = tr

        calculations: List[DailyCalculation] = []
        position = None
        entry_price = 0.0
        stop_loss = 0.0
        entry_date = ""
        signal_date = ""

        for i in range(len(df)):
            row = df.iloc[i]
            ts = str(row["timestamp"])[:10]
            sig = signals_df.iloc[i]

            fast_sma = float(sig["fast_sma"]) if pd.notna(sig["fast_sma"]) else None
            slow_sma = float(sig["slow_sma"]) if pd.notna(sig["slow_sma"]) else None
            atr = float(sig["atr"]) if pd.notna(sig["atr"]) else None
            signal = str(sig["signal"]) if pd.notna(sig["signal"]) else "HOLD"
            true_range = float(sig["true_range"]) if pd.notna(sig.get("true_range")) else None

            calc = DailyCalculation(
                date=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                adjusted_close=float(row["adjusted_close"]),
                fast_sma=fast_sma,
                slow_sma=slow_sma,
                prev_fast_sma=None,
                prev_slow_sma=None,
                true_range=true_range,
                atr=atr,
                signal=signal,
                stop_price=None,
                position=position,
            )

            # Calculate previous SMA values
            if i > 0:
                prev_sig = signals_df.iloc[i - 1]
                calc.prev_fast_sma = float(prev_sig["fast_sma"]) if pd.notna(prev_sig["fast_sma"]) else None
                calc.prev_slow_sma = float(prev_sig["slow_sma"]) if pd.notna(prev_sig["slow_sma"]) else None

            # Store stop price for current position
            if position == "OPEN" and pd.notna(atr):
                calc.stop_price = entry_price - cfg.atr_multiplier * atr

            calculations.append(calc)

            # Execute signals with next-bar logic
            if i < len(df) - 1:
                next_row = df.iloc[i + 1]
                next_ts = str(next_row["timestamp"])[:10]
                next_open = float(next_row["open"])
                next_low = float(next_row["low"])

                if signal == "BUY" and position is None:
                    # Next-bar entry
                    signal_date = ts
                    entry_date = next_ts
                    entry_price = next_open
                    stop_loss = next_open - cfg.atr_multiplier * atr if pd.notna(atr) else 0.0
                    position = "OPEN"
                    calc.entry_date = entry_date
                    calc.entry_price = entry_price
                    calc.stop_price = stop_loss
                    calc.position = "OPEN"

                elif signal == "SELL" and position == "OPEN":
                    # Next-bar exit (SMA cross down)
                    calc.exit_date = next_ts
                    calc.exit_price = next_open
                    calc.exit_reason = "sma_cross_down"
                    calc.position = "CLOSED"
                    position = None
                    entry_price = 0.0
                    stop_loss = 0.0

                elif position == "OPEN" and pd.notna(stop_loss) and next_low <= stop_loss:
                    # Stop loss hit
                    exit_price = min(next_open, stop_loss)
                    calc.exit_date = next_ts
                    calc.exit_price = exit_price
                    calc.exit_reason = "stop_loss"
                    calc.position = "CLOSED"
                    position = None
                    entry_price = 0.0
                    stop_loss = 0.0

        # Force-close at end of data
        if position == "OPEN":
            last_calc = calculations[-1]
            last_row = df.iloc[-1]
            last_close = float(last_row["close"])
            last_ts = str(last_row["timestamp"])[:10]
            last_calc.exit_date = last_ts
            last_calc.exit_price = last_close
            last_calc.exit_reason = "end_of_data"
            last_calc.position = "CLOSED"
            position = None

        return calculations

    def compute(
        self, df: pd.DataFrame, symbol: str, strategy_date: Optional[str] = None
    ) -> StrategyCalculationResult:
        """Run full strategy calculation and return result."""
        calculations = self.compute_daily(df, strategy_date)

        # Extract signals and trades
        signals: List[Dict[str, Any]] = []
        trades: List[Dict[str, Any]] = []

        for calc in calculations:
            if calc.signal in ("BUY", "SELL"):
                signals.append({
                    "date": calc.date,
                    "signal": calc.signal,
                    "fast_sma": calc.fast_sma,
                    "slow_sma": calc.slow_sma,
                    "prev_fast_sma": calc.prev_fast_sma,
                    "prev_slow_sma": calc.prev_slow_sma,
                    "atr": calc.atr,
                    "entry_date": calc.entry_date,
                    "entry_price": calc.entry_price,
                    "stop_price": calc.stop_price,
                })
            if calc.exit_date and calc.exit_price is not None:
                gross_pnl = ((calc.exit_price - calc.entry_price) / calc.entry_price) * 100 if calc.entry_price else 0
                cost_frac = self.config.cost_bps / 10000
                net_pnl = gross_pnl - cost_frac * 100
                trades.append({
                    "entry_date": calc.entry_date,
                    "entry_price": calc.entry_price,
                    "exit_date": calc.exit_date,
                    "exit_price": calc.exit_price,
                    "stop_price": calc.stop_price,
                    "exit_reason": calc.exit_reason,
                    "gross_pnl": round(gross_pnl, 4),
                    "cost": round(cost_frac * 100, 4),
                    "net_pnl": round(net_pnl, 4),
                })

        # Find selected date calculation if provided
        selected_calc = None
        if strategy_date:
            for calc in calculations:
                if calc.date == strategy_date:
                    selected_calc = calc
                    break

        return StrategyCalculationResult(
            symbol=symbol.upper(),
            config=self.config,
            calculations=calculations,
            signals=signals,
            trades=trades,
            strategy_date=strategy_date,
            selected_calculation=selected_calc,
        )
