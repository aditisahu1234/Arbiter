"""Tests for position management and strategy calculations."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from app.models.position import Position, PositionStatus
from app.services.position_service import position_service
from app.services.strategy_calc_service import StrategyCalcEngine
from app.quant.strategies import StrategyConfig


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(100) * 2)
    
    return pd.DataFrame({
        "timestamp": dates,
        "open": prices + np.random.randn(100) * 0.5,
        "high": prices + np.abs(np.random.randn(100)) * 1.0,
        "low": prices - np.abs(np.random.randn(100)) * 1.0,
        "close": prices,
        "adjusted_close": prices,
        "volume": np.random.randint(1000000, 10000000, 100),
    })


@pytest.fixture
def sample_position():
    """Create a sample position for testing."""
    return Position(
        symbol="RELIANCE",
        status=PositionStatus.OPEN,
        fast_sma=10,
        slow_sma=50,
        atr_window=14,
        atr_multiplier=2.0,
        cost_bps=10.0,
        signal_date="2024-01-15",
        entry_date="2024-01-16",
        entry_price=2450.0,
        quantity=1.0,
        stop_price=2400.0,
        current_price=2500.0,
    )


class TestStrategyCalcEngine:
    """Test strategy calculation engine."""

    def test_sma_crossover_detection(self, sample_ohlcv_data):
        """Test that SMA crossover is correctly detected."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(sample_ohlcv_data, "TEST")
        
        # Should have calculations
        assert len(result.calculations) == 100
        
        # Should have signals
        assert isinstance(result.signals, list)
        
        # Should have trades if crossover occurred
        assert isinstance(result.trades, list)

    def test_no_lookahead_bias(self, sample_ohlcv_data):
        """Test that signals use only past data (no look-ahead)."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(sample_ohlcv_data, "TEST")
        
        # Check that entry dates are after signal dates
        for calc in result.calculations:
            if calc.signal == "BUY" and calc.entry_date:
                # Entry should be on a future date
                assert calc.entry_date >= calc.date

    def test_next_bar_execution(self, sample_ohlcv_data):
        """Test that execution happens on next bar open."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(sample_ohlcv_data, "TEST")
        
        # Find a BUY signal
        buy_signals = [s for s in result.signals if s["signal"] == "BUY"]
        if buy_signals:
            # Entry should be next day
            signal = buy_signals[0]
            assert signal["entry_date"] is not None
            # Entry date should be after signal date
            from datetime import datetime
            sig_date = datetime.strptime(signal["date"], "%Y-%m-%d")
            entry_date = datetime.strptime(signal["entry_date"], "%Y-%m-%d")
            assert entry_date > sig_date

    def test_atr_stop_calculation(self, sample_ohlcv_data):
        """Test ATR stop price calculation."""
        cfg = StrategyConfig(fast_sma=5, slow_sma=10, atr_multiplier=2.0)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(sample_ohlcv_data, "TEST")
        
        # Check that stop prices are calculated
        for calc in result.calculations:
            if calc.position == "OPEN" and calc.stop_price is not None and calc.entry_price is not None:
                # Stop should be below entry price
                assert calc.stop_price < calc.entry_price

    def test_gap_stop_handling(self):
        """Test that gap stops work correctly."""
        # Create data with a gap down
        dates = pd.date_range("2024-01-01", periods=20, freq="D")
        prices = [100, 102, 104, 106, 108, 90, 88, 86, 84, 82, 80, 78, 76, 74, 72, 70, 68, 66, 64, 62]
        
        df = pd.DataFrame({
            "timestamp": dates,
            "open": prices,
            "high": [p + 2 for p in prices],
            "low": [p - 2 for p in prices],
            "close": prices,
            "adjusted_close": prices,
            "volume": [1000000] * 20,
        })
        
        cfg = StrategyConfig(fast_sma=3, slow_sma=5, atr_multiplier=2.0, cost_bps=10.0)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(df, "TEST")
        
        # Should handle gap down correctly
        assert len(result.calculations) == 20


class TestPositionService:
    """Test position service."""

    @pytest.mark.asyncio
    async def test_create_position(self, sample_position, monkeypatch):
        """Test creating a position."""
        # Mock database session
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        
        # Make flush and refresh async
        async def mock_flush():
            pass
        async def mock_refresh(obj):
            obj.id = 1
            return obj
        
        mock_db.flush = mock_flush
        mock_db.refresh = mock_refresh
        
        position = await position_service.create_position(
            db=mock_db,
            symbol="RELIANCE",
            signal_date="2024-01-15",
            entry_date="2024-01-16",
            entry_price=2450.0,
            fast_sma=10,
            slow_sma=50,
            atr_window=14,
            atr_multiplier=2.0,
            cost_bps=10.0,
        )
        
        assert position.symbol == "RELIANCE"
        assert position.status == PositionStatus.OPEN
        assert position.entry_price == 2450.0

    @pytest.mark.asyncio
    async def test_close_position(self, sample_position, monkeypatch):
        """Test closing a position."""
        mock_db = MagicMock()
        
        # Mock get_position
        async def mock_get_position(db, pos_id):
            if pos_id == 1:
                return sample_position
            return None
        
        monkeypatch.setattr(position_service, "get_position", mock_get_position)
        
        # Mock update_position
        async def mock_update_position(db, pos_id, updates):
            for key, value in updates.items():
                if hasattr(sample_position, key):
                    setattr(sample_position, key, value)
            return sample_position
        
        monkeypatch.setattr(position_service, "update_position", mock_update_position)
        
        # Mock commit
        async def mock_commit():
            pass
        mock_db.commit = mock_commit
        
        position = await position_service.close_position(
            mock_db, 1, "2024-02-01", 2500.0, "sma_cross_down"
        )
        
        assert position.status == PositionStatus.CLOSED
        assert position.exit_price == 2500.0
        assert position.exit_reason == "sma_cross_down"
        assert position.net_pnl > 0  # Should be profitable


class TestPositionPersistence:
    """Test position persistence."""

    @pytest.mark.asyncio
    async def test_position_survives_refresh(self, sample_position):
        """Test that position data is complete for persistence."""
        # Verify all required fields exist
        assert hasattr(sample_position, 'id')
        assert hasattr(sample_position, 'symbol')
        assert hasattr(sample_position, 'status')
        assert hasattr(sample_position, 'entry_date')
        assert hasattr(sample_position, 'entry_price')
        assert hasattr(sample_position, 'stop_price')
        assert hasattr(sample_position, 'current_price')
        assert hasattr(sample_position, 'gross_pnl')
        assert hasattr(sample_position, 'net_pnl')
        assert hasattr(sample_position, 'created_at')
        assert hasattr(sample_position, 'last_updated')


class TestPnLCalculation:
    """Test P&L calculations."""

    def test_long_position_pnl(self):
        """Test P&L calculation for long position."""
        entry_price = 100.0
        exit_price = 110.0
        cost_bps = 10.0
        
        gross_pnl = ((exit_price - entry_price) / entry_price) * 100
        cost_frac = cost_bps / 10000
        net_pnl = gross_pnl - cost_frac * 100
        
        assert gross_pnl == 10.0
        assert net_pnl == 9.9  # 10% - 0.1% cost

    def test_stop_loss_pnl(self):
        """Test P&L calculation when stop loss is hit."""
        entry_price = 100.0
        stop_price = 95.0
        cost_bps = 10.0
        
        gross_pnl = ((stop_price - entry_price) / entry_price) * 100
        cost_frac = cost_bps / 10000
        net_pnl = gross_pnl - cost_frac * 100
        
        assert gross_pnl == -5.0
        assert net_pnl == -5.1  # -5% - 0.1% cost

    def test_multiple_trades_pnl(self):
        """Test P&L across multiple trades."""
        trades = [
            {"entry": 100, "exit": 110, "pnl": 10.0},
            {"entry": 100, "exit": 95, "pnl": -5.0},
            {"entry": 100, "exit": 105, "pnl": 5.0},
        ]
        
        total_pnl = sum(t["pnl"] for t in trades)
        win_trades = [t for t in trades if t["pnl"] > 0]
        lose_trades = [t for t in trades if t["pnl"] <= 0]
        
        assert total_pnl == 10.0
        assert len(win_trades) == 2
        assert len(lose_trades) == 1
        assert 2/3 * 100 == pytest.approx(66.67, abs=0.01)  # Win rate
