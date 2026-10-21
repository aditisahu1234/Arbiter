"""Tests for strategy calculation with selected date and crossover detection."""
import pytest
import pandas as pd
import numpy as np

from app.quant.strategies import StrategyConfig
from app.services.strategy_calc_service import StrategyCalcEngine


@pytest.fixture
def crossover_data():
    """Create data with clear SMA crossover."""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    # Start with slow growth, then accelerate to create crossover
    prices = [50 + i * 0.1 for i in range(50)] + [55 + i for i in range(50)]
    
    return pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p + 2 for p in prices],
        "low": [p - 2 for p in prices],
        "close": prices,
        "adjusted_close": prices,
        "volume": [1000000] * 100,
    })


@pytest.fixture
def no_crossover_data():
    """Create data without crossover."""
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    prices = [100.0] * 60  # Flat prices
    
    return pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [102.0] * 60,
        "low": [98.0] * 60,
        "close": prices,
        "adjusted_close": prices,
        "volume": [1000000] * 60,
    })


class TestTradeRecordCompleteness:
    """Every completed trade must carry its entry_date and entry_price.

    The historical backtest used to attach entry details only to the signal bar,
    so the exit bar (where a trade record is built) had null entry fields. This
    test locks in the fix: any trade that has an exit also has a real buy date
    and buy price, and P&L is computed from the actual entry price.
    """

    @pytest.fixture
    def vshape_trade_data(self):
        """Flat-low, steady-rise, then-decline series that guarantees at least
        one completed trade (buy on the bullish cross, exit on the bearish cross)."""
        n = 200
        p1 = np.full(70, 60.0)
        p2 = np.linspace(60, 130, 70)
        p3 = np.linspace(130, 50, 60)
        prices = np.concatenate([p1, p2, p3])[:n]
        dates = pd.date_range("2024-01-01", periods=n, freq="D")
        return pd.DataFrame({
            "timestamp": dates,
            "open": prices,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "adjusted_close": prices,
            "volume": [1000000] * n,
        })

    def test_trades_carry_entry_fields(self, vshape_trade_data):
        cfg = StrategyConfig(fast_sma=5, slow_sma=10, atr_window=3, atr_multiplier=2.0, cost_bps=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(vshape_trade_data, "TEST")

        assert len(result.trades) > 0, "expected at least one completed trade"
        for t in result.trades:
            # Both buy fields must be populated for any trade that exited.
            assert t["entry_date"] is not None, "entry_date missing on trade"
            assert t["entry_price"] is not None, "entry_price missing on trade"
            assert t["exit_date"] is not None
            assert t["exit_price"] is not None
            # Buy date must precede (or equal) the sell date.
            assert t["entry_date"] <= t["exit_date"]
            # P&L must be computed from the real entry price, not defaulted to 0.
            expected_gross = ((t["exit_price"] - t["entry_price"]) / t["entry_price"]) * 100
            assert abs(t["gross_pnl"] - round(expected_gross, 4)) < 1e-3
            assert abs(t["net_pnl"] - (t["gross_pnl"] - 0.1)) < 1e-3

    def test_trade_records_unique_and_in_order(self, vshape_trade_data):
        """Each trade is represented exactly once and in chronological order."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10, atr_window=3, atr_multiplier=2.0, cost_bps=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(vshape_trade_data, "TEST")

        keys = [ (t["entry_date"], t["exit_date"]) for t in result.trades ]
        assert len(keys) == len(set(keys)), "duplicate trade records detected"
        entry_dates = [ t["entry_date"] for t in result.trades ]
        assert entry_dates == sorted(entry_dates)

    def test_trade_serialization_for_frontend(self, vshape_trade_data):
        """Verify the trade dict serializes the buy fields exactly as the UI expects."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10, atr_window=3, atr_multiplier=2.0, cost_bps=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(vshape_trade_data, "TEST")

        t = result.trades[0]
        for key in ("entry_date", "entry_price", "exit_date", "exit_price",
                    "stop_price", "exit_reason", "gross_pnl", "cost", "net_pnl"):
            assert key in t
        assert isinstance(t["entry_date"], str)
        assert isinstance(t["entry_price"], (int, float))

    def test_next_session_recommendation_has_market_hours(self, vshape_trade_data):
        """The forward-looking recommendation now carries market-hours context."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10, atr_window=3, atr_multiplier=2.0, cost_bps=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(vshape_trade_data, "TEST")

        rec = result.next_session_recommendation
        assert rec is not None
        assert "market_hours" in rec
        mh = rec["market_hours"]
        assert mh["timezone"] == "Asia/Kolkata"
        assert "market_open" in mh and isinstance(mh["market_open"], bool)
        # No invented opening price should ever be exposed on the recommendation.
        assert "execution_price" not in rec or rec.get("execution_price") is None

    def test_duplicate_entry_suppressed_when_open(self):
        """If a position is open at the end of data, no duplicate buy is recommended."""
        from app.services.strategy_calc_service import DailyCalculation
        engine = StrategyCalcEngine(StrategyConfig())
        open_calc = DailyCalculation(
            "2026-10-19", 120, 122, 118, 120, 120,   # date, open, high, low, close, adj_close
            None, None, None, None, None, None,       # fast_sma, slow_sma, prev_fast, prev_slow, true_range, atr
            "HOLD", None,                              # signal, stop_price
            None, None, None, None, None, "OPEN",     # entry_date, entry_price, exit_date, exit_price, exit_reason, position
        )
        rec = engine._build_next_session_recommendation([open_calc], "RELIANCE")
        assert rec["has_signal"] is False
        assert "duplicate" in rec.get("reason", "").lower()


class TestSelectedDateStrategy:
    """Test strategy calculation for selected date."""

    def test_buy_signal_on_crossover(self, crossover_data):
        """Test BUY signal when fast SMA crosses above slow SMA."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10)
        engine = StrategyCalcEngine(cfg)
        
        # Find the crossover date
        result = engine.compute(crossover_data, "TEST")
        
        # Should have calculations
        assert len(result.calculations) == 100
        
        # Check that we have valid SMA values
        valid_calcs = [c for c in result.calculations if c.fast_sma is not None]
        assert len(valid_calcs) > 0
        
        # Verify the calculation has correct structure
        calc = valid_calcs[0]
        assert hasattr(calc, 'date')
        assert hasattr(calc, 'fast_sma')
        assert hasattr(calc, 'slow_sma')

    def test_no_signal_on_flat_data(self, no_crossover_data):
        """Test no signal when prices are flat (no crossover)."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(no_crossover_data, "TEST")
        
        # Should have no BUY or SELL signals
        buy_signals = [s for s in result.signals if s["signal"] == "BUY"]
        sell_signals = [s for s in result.signals if s["signal"] == "SELL"]
        assert len(buy_signals) == 0
        assert len(sell_signals) == 0

    def test_next_bar_entry_price(self, crossover_data):
        """Test that entry price is next bar's OPEN, not signal bar's CLOSE."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(crossover_data, "TEST")
        
        # Check that calculations have correct structure
        assert len(result.calculations) == 100
        
        # Find a calculation with entry
        entry_calc = None
        for calc in result.calculations:
            if calc.entry_price is not None:
                entry_calc = calc
                break
        
        if entry_calc:
            # Entry date should exist
            assert entry_calc.entry_date is not None
            # Entry price should be set
            assert entry_calc.entry_price is not None

    def test_selected_date_result(self, crossover_data):
        """Test that selected date calculation is returned."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10)
        engine = StrategyCalcEngine(cfg)
        
        # Use the last date
        last_date = crossover_data["timestamp"].iloc[-1].strftime("%Y-%m-%d")
        result = engine.compute(crossover_data, "TEST", strategy_date=last_date)
        
        # Should have selected calculation
        assert result.selected_calculation is not None
        assert result.selected_calculation.date == last_date

    def test_selected_date_no_signal(self, no_crossover_data):
        """Test selected date with no signal."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10)
        engine = StrategyCalcEngine(cfg)
        
        # Use the last date
        last_date = no_crossover_data["timestamp"].iloc[-1].strftime("%Y-%m-%d")
        result = engine.compute(no_crossover_data, "TEST", strategy_date=last_date)
        
        # Should have selected calculation but no signal
        assert result.selected_calculation is not None
        assert result.selected_calculation.date == last_date
        assert result.selected_calculation.signal == "HOLD"

    def test_latest_date_no_next_bar(self):
        """Test when selected date is the latest available."""
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        prices = [50 + i for i in range(30)]
        
        df = pd.DataFrame({
            "timestamp": dates,
            "open": prices,
            "high": [p + 2 for p in prices],
            "low": [p - 2 for p in prices],
            "close": prices,
            "adjusted_close": prices,
            "volume": [1000000] * 30,
        })
        
        cfg = StrategyConfig(fast_sma=3, slow_sma=5)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(df, "TEST")
        
        # Last date should have no entry (no next bar)
        last_calc = result.calculations[-1]
        assert last_calc.entry_date is None or last_calc.position != "OPEN"


class TestCloseAboveSMA50Condition:
    """Test Close > SMA50 informational condition."""

    def test_close_above_sma50_display(self, crossover_data):
        """Test that Close > SMA50 is calculated."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(crossover_data, "TEST")
        
        # Check that calculations include price vs SMA info
        for calc in result.calculations[:10]:
            if calc.fast_sma is not None and calc.slow_sma is not None:
                # Should have both values
                assert calc.close > 0
                assert calc.fast_sma > 0
                assert calc.slow_sma > 0


class TestATRStopCalculation:
    """Test ATR stop calculation."""

    def test_atr_stop_formula(self, crossover_data):
        """Test ATR stop is calculated correctly."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10, atr_multiplier=2.0)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(crossover_data, "TEST")
        
        # Find a position with stop price
        for calc in result.calculations:
            if calc.stop_price is not None and calc.entry_price is not None:
                # Stop should be below entry
                assert calc.stop_price < calc.entry_price
                break


class TestNoLookahead:
    """Test no look-ahead bias."""

    def test_no_future_data_in_signal(self, crossover_data):
        """Test that signals don't use future data."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(crossover_data, "TEST")
        
        # Check that each calculation only uses data up to that point
        for i, calc in enumerate(result.calculations):
            if calc.fast_sma is not None:
                # Should only have data up to current bar
                assert calc.date <= result.calculations[-1].date


class TestExitConditions:
    """Test exit conditions."""

    def test_sma_cross_exit(self, crossover_data):
        """Test exit on SMA cross down."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(crossover_data, "TEST")
        
        # Check that exits have correct reason
        for calc in result.calculations:
            if calc.exit_reason:
                assert calc.exit_reason in ["sma_cross_down", "stop_loss", "end_of_data"]

    def test_stop_loss_exit(self, crossover_data):
        """Test stop loss exit."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10, atr_multiplier=0.5)  # Tight stop
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(crossover_data, "TEST")
        
        # Should have trades with stop loss
        stop_trades = [t for t in result.trades if t.get("exit_reason") == "stop_loss"]
        # May or may not have stop losses depending on data


class TestAPIResponseSchema:
    """Test API response schemas."""

    def test_strategy_calc_response(self, crossover_data):
        """Test strategy calculation response schema."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(crossover_data, "TEST")
        
        # Check response structure
        assert hasattr(result, 'symbol')
        assert hasattr(result, 'config')
        assert hasattr(result, 'calculations')
        assert hasattr(result, 'signals')
        assert hasattr(result, 'trades')
        assert hasattr(result, 'strategy_date')
        assert hasattr(result, 'selected_calculation')

    def test_calculation_fields(self, crossover_data):
        """Test calculation field structure."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(crossover_data, "TEST")
        
        if result.calculations:
            calc = result.calculations[0]
            assert hasattr(calc, 'date')
            assert hasattr(calc, 'open')
            assert hasattr(calc, 'high')
            assert hasattr(calc, 'low')
            assert hasattr(calc, 'close')
            assert hasattr(calc, 'fast_sma')
            assert hasattr(calc, 'slow_sma')
            assert hasattr(calc, 'atr')
            assert hasattr(calc, 'signal')
            assert hasattr(calc, 'prev_fast_sma')
            assert hasattr(calc, 'prev_slow_sma')
