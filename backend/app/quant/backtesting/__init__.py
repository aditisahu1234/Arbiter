"""Backtesting engine with next-bar-open execution, no look-ahead bias."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List
import numpy as np
import pandas as pd

from app.quant.indicators import SimpleMovingAverage, AverageTrueRange, ReturnsEngine
from app.quant.strategies import StrategyConfig, SMACrossoverStrategy
from app.quant.costs import get_default_cost_model


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
    """Deterministic backtest with next-bar-open execution and transaction costs."""

    def __init__(self, config: StrategyConfig | None = None):
        self.config = config or StrategyConfig()

    def run(self, df: pd.DataFrame, symbol: str) -> BacktestResult:
        cfg = self.config
        strategy = SMACrossoverStrategy(cfg)
        signals = strategy.generate_signals(df)

        cash = cfg.initial_capital
        position_shares = 0.0
        entry_price = 0.0
        entry_time = ""
        stop_loss = 0.0
        trades: List[Dict[str, Any]] = []

        eq_gross = []
        eq_net = []
        daily_rets = []

        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i - 1]
            ts = str(row["timestamp"])[:10]
            open_px = float(row["open"])
            close_px = float(row["close"])
            low_px = float(row["low"])

            sig = signals.iloc[i]
            prev_sig = signals.iloc[i - 1]
            atr = sig["atr"]

            gross_equity = cash + position_shares * close_px
            eq_gross.append({"timestamp": ts, "equity": gross_equity})

            # === BUY: next-bar-open execution ===
            if position_shares == 0 and prev_sig["signal"] == "BUY":
                one_way_bps = cfg.cost_bps / 2
                one_way_frac = one_way_bps / 10000
                position_shares = cash * (1 - one_way_frac) / open_px
                cash = 0.0
                entry_price = open_px
                entry_time = ts
                stop_loss = open_px - cfg.atr_multiplier * atr if pd.notna(atr) else 0.0

            # === SELL: next-bar-open execution (SMA cross down) ===
            elif position_shares > 0 and prev_sig["signal"] == "SELL":
                one_way_bps = cfg.cost_bps / 2
                one_way_frac = one_way_bps / 10000
                proceeds = position_shares * open_px * (1 - one_way_frac)
                gross_proceeds = position_shares * open_px
                pnl_pct = (proceeds / (gross_proceeds) - 1) * 100
                trades.append({
                    "entry_time": entry_time,
                    "entry_price": round(entry_price, 2),
                    "exit_time": ts,
                    "exit_price": round(open_px, 2),
                    "stop_loss": round(stop_loss, 2),
                    "exit_reason": "sma_cross_down",
                    "pnl_pct": round(pnl_pct, 4),
                })
                cash = proceeds
                position_shares = 0.0
                entry_price = 0.0
                entry_time = ""
                stop_loss = 0.0

            # === STOP-LOSS: intraday check ===
            if position_shares > 0 and pd.notna(stop_loss) and low_px <= stop_loss:
                one_way_bps = cfg.cost_bps / 2
                one_way_frac = one_way_bps / 10000
                exit_px = min(open_px, stop_loss)
                gross_exit = position_shares * exit_px
                proceeds = gross_exit * (1 - one_way_frac)
                gross_cost = position_shares * entry_price * one_way_frac
                pnl_pct = ((proceeds / (position_shares * entry_price)) - 1) * 100
                trades.append({
                    "entry_time": entry_time,
                    "entry_price": round(entry_price, 2),
                    "exit_time": ts,
                    "exit_price": round(exit_px, 2),
                    "stop_loss": round(stop_loss, 2),
                    "exit_reason": "stop_loss",
                    "pnl_pct": round(pnl_pct, 4),
                })
                cash = proceeds
                position_shares = 0.0
                entry_price = 0.0
                entry_time = ""
                stop_loss = 0.0

            # Daily return
            prev_close = float(prev_row["close"])
            daily_rets.append(close_px / prev_close - 1 if prev_close > 0 else 0.0)

        # Force-close at end
        if position_shares > 0:
            last_row = df.iloc[-1]
            last_close = float(last_row["close"])
            last_ts = str(last_row["timestamp"])[:10]
            one_way_bps = cfg.cost_bps / 2
            one_way_frac = one_way_bps / 10000
            proceeds = position_shares * last_close * (1 - one_way_frac)
            pnl_pct = ((proceeds / (position_shares * entry_price)) - 1) * 100
            trades.append({
                "entry_time": entry_time,
                "entry_price": round(entry_price, 2),
                "exit_time": last_ts,
                "exit_price": round(last_close, 2),
                "stop_loss": round(stop_loss, 2),
                "exit_reason": "end_of_data",
                "pnl_pct": round(pnl_pct, 4),
            })
            cash = proceeds
            position_shares = 0.0

        eq_gross_df = pd.DataFrame(eq_gross).set_index("timestamp")["equity"]
        eq_net_df = eq_gross_df.copy()  # net = gross since we deduct from cash directly
        dr = pd.Series(daily_rets)

        metrics = self._compute_metrics(eq_gross_df, eq_net_df, trades, dr)
        return BacktestResult(
            symbol=symbol, config=cfg,
            trades=trades,
            equity_curve_gross=eq_gross_df, equity_curve_net=eq_net_df,
            metrics=metrics, daily_returns=dr,
        )

    def _compute_metrics(self, eq_gross, eq_net, trades, daily_returns):
        if eq_net.empty or eq_net.iloc[0] == 0:
            return {"error": "no_equity_data"}

        total_days = len(eq_net)
        gross_ret = (eq_gross.iloc[-1] / eq_gross.iloc[0]) - 1
        net_ret = (eq_net.iloc[-1] / eq_net.iloc[0]) - 1
        gross_cagr = ((eq_gross.iloc[-1] / eq_gross.iloc[0]) ** (252 / max(total_days, 1)) - 1) if eq_gross.iloc[0] > 0 else 0.0
        net_cagr = ((eq_net.iloc[-1] / eq_net.iloc[0]) ** (252 / max(total_days, 1)) - 1) if eq_net.iloc[0] > 0 else 0.0
        daily_vol = float(daily_returns.std() * np.sqrt(252)) if len(daily_returns) > 1 else 0.0
        sharpe = net_cagr / daily_vol if daily_vol > 0 else 0.0

        peak = eq_net.cummax()
        dd = (eq_net - peak) / peak
        max_dd = float(dd.min())

        winning = [t for t in trades if t.get("pnl_pct", 0) > 0]
        losing = [t for t in trades if t.get("pnl_pct", 0) <= 0]
        gross_profit = sum(t.get("pnl_pct", 0) for t in winning)
        gross_loss = abs(sum(t.get("pnl_pct", 0) for t in losing))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        win_rate = len(winning) / len(trades) if trades else 0.0

        down_rets = daily_returns[daily_returns < 0]
        sortino = (net_cagr / (down_rets.std() * np.sqrt(252))) if len(down_rets) > 0 and down_rets.std() > 0 else 0.0

        return {
            "gross_return": round(float(gross_ret) * 100, 2),
            "net_return": round(float(net_ret) * 100, 2),
            "gross_cagr": round(float(gross_cagr) * 100, 2),
            "net_cagr": round(float(net_cagr) * 100, 2),
            "sharpe_ratio": round(float(sharpe), 4),
            "sortino_ratio": round(float(sortino), 4),
            "max_drawdown": round(float(max_dd) * 100, 2),
            "win_rate": round(float(win_rate) * 100, 2),
            "profit_factor": round(float(profit_factor), 4),
            "total_trades": len(trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
        }
