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
    next_session_recommendation: Optional[Dict[str, Any]] = None


class StrategyCalcEngine:
    """Computes daily strategy calculations for position tracking."""

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()

    def compute_daily(self, df: pd.DataFrame) -> List[DailyCalculation]:
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
                    # Next-bar exit (SMA cross down). Propagate entry details so the
                    # exit bar carries a complete trade record.
                    calc.entry_date = entry_date
                    calc.entry_price = entry_price
                    calc.exit_date = next_ts
                    calc.exit_price = next_open
                    calc.exit_reason = "sma_cross_down"
                    calc.position = "CLOSED"
                    position = None
                    entry_price = 0.0
                    stop_loss = 0.0

                elif position == "OPEN" and pd.notna(stop_loss) and next_low <= stop_loss:
                    # Stop loss hit. Propagate entry details onto the exit bar.
                    exit_price = min(next_open, stop_loss)
                    calc.entry_date = entry_date
                    calc.entry_price = entry_price
                    calc.exit_date = next_ts
                    calc.exit_price = exit_price
                    calc.exit_reason = "stop_loss"
                    calc.position = "CLOSED"
                    position = None
                    entry_price = 0.0
                    stop_loss = 0.0

        # Force-close at end of data. Propagate entry details onto the exit bar.
        if position == "OPEN":
            last_calc = calculations[-1]
            last_row = df.iloc[-1]
            last_close = float(last_row["close"])
            last_ts = str(last_row["timestamp"])[:10]
            last_calc.entry_date = entry_date
            last_calc.entry_price = entry_price
            last_calc.exit_date = last_ts
            last_calc.exit_price = last_close
            last_calc.exit_reason = "end_of_data"
            last_calc.position = "CLOSED"
            position = None

        return calculations

    def compute(
        self, df: pd.DataFrame, symbol: str, strategy_date: Optional[str] = None,
        start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> StrategyCalculationResult:
        """Run full strategy calculation and return result.
        
        If start_date/end_date are provided, calculations are filtered to that range
        but indicators are computed over the full dataset first (warm-up).
        """
        # Compute signals over the full dataset for correct indicator warm-up
        calculations = self.compute_daily(df)
        
        # Filter calculations to the requested date range if provided
        filtered_calculations = calculations
        if start_date:
            filtered_calculations = [c for c in filtered_calculations if c.date >= start_date]
        if end_date:
            filtered_calculations = [c for c in filtered_calculations if c.date <= end_date]

        # Extract signals and trades from the filtered range
        signals: List[Dict[str, Any]] = []
        trades: List[Dict[str, Any]] = []

        for calc in filtered_calculations:
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
            for calc in filtered_calculations:
                if calc.date == strategy_date:
                    selected_calc = calc
                    break

        # Build next-session recommendation from the latest available completed candle
        # in the FULL dataset (not the filtered range), so the forward-looking signal
        # always reflects the newest data regardless of the selected display interval.
        next_rec = self._build_next_session_recommendation(calculations, symbol)

        # Attach market-hours context so the frontend can distinguish a live BUY NOW
        # situation from a next-session PENDING situation. This does not mutate the
        # completed daily candles or historical trades.
        next_rec["market_hours"] = self._get_market_hours_context()

        return StrategyCalculationResult(
            symbol=symbol.upper(),
            config=self.config,
            calculations=filtered_calculations,
            signals=signals,
            trades=trades,
            strategy_date=strategy_date,
            selected_calculation=selected_calc,
            next_session_recommendation=next_rec,
        )

    def _build_next_session_recommendation(
        self, calculations: List[DailyCalculation], symbol: str
    ) -> Dict[str, Any]:
        """Evaluate the latest completed candle for a new entry signal for the next session."""
        if not calculations:
            return {"has_signal": False, "reason": "No data available"}

        latest = calculations[-1]
        result: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "has_signal": False,
            "signal_date": latest.date,
            "action": None,
            "expected_execution_basis": "next session opening price",
            "stop_loss": None,
            "exit_note": "Exit will be determined by configured strategy exit signal or stop-loss",
            "data_freshness": f"Latest data as of {latest.date}",
        }

        # Only recommend entry if there is no open position at the end of the data
        if latest.position == "OPEN":
            result["reason"] = "A position is already open, so the strategy does not recommend a duplicate entry"
            return result

        # A BUY signal on the last bar means the next session's open is the entry
        if latest.signal == "BUY" and latest.entry_price is not None:
            result["has_signal"] = True
            result["action"] = "Buy next eligible trading session"
            result["stop_loss"] = latest.stop_price
            return result

        # No valid entry signal
        result["reason"] = "No new buy signal"
        return result

    def _get_market_hours_context(self) -> Dict[str, Any]:
        """Return NSE market-hours context using Asia/Kolkata.

        This is a lightweight, provider-agnostic helper so the frontend can decide
        whether to render "BUY NOW" (market open) vs "NEXT SESSION PENDING"
        (market closed). It does not fetch intraday prices or modify daily data.
        """
        from datetime import datetime, timezone, timedelta

        ist = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(ist)
        open_ist = now.replace(hour=9, minute=15, second=0, microsecond=0)
        close_ist = now.replace(hour=15, minute=30, second=0, microsecond=0)
        is_open = open_ist <= now <= close_ist
        weekday = now.weekday()  # 0=Mon..5=Fri
        is_weekend = weekday >= 5
        return {
            "timezone": "Asia/Kolkata",
            "current_time_ist": now.isoformat(),
            "market_open": is_open and not is_weekend,
            "is_weekend": is_weekend,
            "session_open": "09:15 IST",
            "session_close": "15:30 IST",
        }
