"""Backtesting engine with next-bar-open execution, no look-ahead bias."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List
import numpy as np
import pandas as pd

from app.quant.indicators import SimpleMovingAverage, AverageTrueRange, ReturnsEngine
from app.quant.strategies import StrategyConfig, SMACrossoverStrategy


@dataclass
class BacktestResult:
    symbol: str
    config: StrategyConfig
    trades: List[Dict[str, Any]]
    equity_curve_gross: pd.Series
    equity_curve_net: pd.Series
    metrics: Dict[str, Any]
    daily_returns: pd.Series


class BacktestEngine:
    """Deterministic backtest with next-bar-open execution, transaction costs, and full metrics."""

    def __init__(self, config: StrategyConfig | None = None):
        self.config = config or StrategyConfig()

    def run(
        self,
        df: pd.DataFrame,
        symbol: str,
    ) -> BacktestResult:
        """Run backtest on OHLCV data. df must have: timestamp, open, high, low, close, volume."""
        cfg = self.config
        strategy = SMACrossoverStrategy(cfg)
        signals = strategy.generate_signals(df)
        trades: List[Dict[str, Any]] = []

        cash = cfg.initial_capital
        position = 0.0  # shares held
        equity_gross = []
        equity_net = []
        prev_equity = cash
        daily_returns = []

        for i in range(1, len(df)):
            price_row = df.iloc[i]
            ts = str(price_row["timestamp"])[:10]
            open_price = float(price_row["open"])
            close_price = float(price_row["close"])
            low_price = float(price_row["low"])

            signal = signals.iloc[i]["signal"]
            atr = signals.iloc[i]["atr"]
            prev_signal = signals.iloc[i - 1]["signal"]
            entry_price = float(df.iloc[i]["open"]) if i + 1 < len(df) else close_price

            # Execute on bar i using signals from bar i-1 (next-bar-open)
            if position == 0 and prev_signal == "BUY":
                # Enter at open of bar i
                cost_bps = cfg.cost_bps / 10000
                position = cash * (1 - cost_bps) / entry_price
                cash = 0.0
            elif position > 0 and prev_signal == "SELL":
                # Exit at open of bar i
                cost_bps = cfg.cost_bps / 10000
                proceeds = position * entry_price * (1 - cost_bps)
                pnl = proceeds - (position * (cash / (position * (1 - cost_bps)))) if position > 0 else 0
                trades.append({
                    "entry_time": None,
                    "entry_price": None,
                    "exit_time": ts,
                    "exit_price": entry_price,
                    "exit_reason": "sma_cross_down",
                    "pnl_pct": 0.0,
                })
                cash = proceeds
                position = 0.0

            # Check stop-loss intraday
            if position > 0:
                stop_price = signals.iloc[i - 1].get("stop_loss", 0)
                if pd.notna(stop_price) and low_price <= stop_price:
                    cost_bps = cfg.cost_bps / 10000
                    exit_px = min(entry_price, stop_price)
                    proceeds = position * exit_px * (1 - cost_bps)
                    pnl_pct = (proceeds / (position * entry_price * (1 + cost_bps)) - 1) * 100 if position > 0 else 0
                    trades.append({
                        "entry_time": str(df.iloc[i - 1]["timestamp"])[:10],
                        "entry_price": entry_price,
                        "exit_time": ts,
                        "exit_price": exit_px,
                        "exit_reason": "stop_loss",
                        "pnl_pct": round(pnl_pct, 4),
                    })
                    cash = proceeds
                    position = 0.0

            equity = cash + position * close_price
            gross_equity = cash + position * close_price
            equity_gross.append({"timestamp": ts, "equity": gross_equity})
            equity_net.append({"timestamp": ts, "equity": equity})
            daily_ret = (close_price / df.iloc[i - 1]["close"] - 1) if df.iloc[i - 1]["close"] > 0 else 0
            daily_returns.append(daily_ret)

        # Close position at end
        if position > 0:
            last_close = float(df.iloc[-1]["close"])
            cost_bps = cfg.cost_bps / 10000
            proceeds = position * last_close * (1 - cost_bps)
            trades.append({
                "entry_time": str(df.iloc[1]["timestamp"])[:10] if len(df) > 1 else None,
                "entry_price": float(df.iloc[1]["open"]) if len(df) > 1 else None,
                "exit_time": str(df.iloc[-1]["timestamp"])[:10],
                "exit_price": last_close,
                "exit_reason": "end_of_data",
                "pnl_pct": round((proceeds / (position * float(df.iloc[1]["open"]) * (1 + cost_bps)) - 1) * 100, 4) if position > 0 else 0,
            })
            cash = proceeds
            position = 0.0

        eq_gross = pd.DataFrame(equity_gross).set_index("timestamp")["equity"]
        eq_net = pd.DataFrame(equity_net).set_index("timestamp")["equity"]
        dr = pd.Series(daily_returns)

        metrics = self._compute_metrics(eq_gross, eq_net, trades, dr)
        return BacktestResult(
            symbol=symbol, config=cfg,
            trades=trades,
            equity_curve_gross=eq_gross, equity_curve_net=eq_net,
            metrics=metrics, daily_returns=dr,
        )

    def _compute_metrics(
        self,
        eq_gross: pd.Series,
        eq_net: pd.Series,
        trades: List[Dict],
        daily_returns: pd.Series,
    ) -> Dict[str, Any]:
        if eq_net.empty or eq_net.iloc[0] == 0:
            return {"error": "no_equity_data"}

        cfg = self.config
        total_days = len(eq_net)
        gross_ret = (eq_gross.iloc[-1] / eq_gross.iloc[0]) - 1
        net_eq_start = eq_net.iloc[0]
        net_ret = (eq_net.iloc[-1] / net_eq_start) - 1
        gross_cagr = ((eq_gross.iloc[-1] / eq_gross.iloc[0]) ** (252 / max(total_days, 1)) - 1) if eq_gross.iloc[0] > 0 else 0
        net_cagr = ((eq_net.iloc[-1] / eq_net.iloc[0]) ** (252 / max(total_days, 1)) - 1) if eq_net.iloc[0] > 0 else 0
        daily_vol = float(daily_returns.std() * np.sqrt(252)) if len(daily_returns) > 1 else 0.0
        sharpe = (net_cagr - cfg.initial_capital * 0) / daily_vol if daily_vol > 0 else 0

        # Max drawdown
        peak = eq_net.cummax()
        dd = (eq_net - peak) / peak
        max_dd = float(dd.min())

        # Win rate, profit factor
        winning = [t for t in trades if t.get("pnl_pct", 0) > 0]
        losing = [t for t in trades if t.get("pnl_pct", 0) <= 0]
        gross_profit = sum(t.get("pnl_pct", 0) for t in winning)
        gross_loss = abs(sum(t.get("pnl_pct", 0) for t in losing))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        win_rate = len(winning) / len(trades) if trades else 0

        return {
            "gross_return": round(float(gross_ret) * 100, 2),
            "net_return": round(float(net_ret) * 100, 2),
            "gross_cagr": round(float(gross_cagr) * 100, 2),
            "net_cagr": round(float(net_cagr) * 100, 2),
            "sharpe_ratio": round(float(sharpe), 4),
            "sortino_ratio": round(
                (float(net_cagr) / (float(daily_returns[daily_returns < 0].std() * np.sqrt(252)))
                 if daily_returns[daily_returns < 0].std() > 0 else 0), 4
            ),
            "max_drawdown": round(float(max_dd) * 100, 2),
            "win_rate": round(float(win_rate) * 100, 2),
            "profit_factor": round(float(profit_factor), 4),
            "total_trades": len(trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
        }
