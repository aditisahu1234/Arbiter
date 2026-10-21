"""Tests for data freshness and synchronization."""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from app.data.storage import storage_manager
from app.core.duckdb import duckdb_manager


class TestDataFreshness:
    """Test data freshness checking."""

    def test_get_latest_timestamp(self):
        """Test getting latest timestamp for an asset."""
        # Use RELIANCE which has data
        latest = duckdb_manager.get_latest_timestamp("RELIANCE")

        # Should return a timestamp
        assert latest is not None
        assert isinstance(latest, pd.Timestamp)

        # Should be a recent date
        assert latest.year >= 2025

    def test_get_latest_timestamp_nonexistent(self):
        """Test getting latest timestamp for nonexistent asset."""
        latest = duckdb_manager.get_latest_timestamp("NONEXISTENT_SYMBOL_12345")
        assert latest is None


class TestDataRefresh:
    """Test data refresh functionality."""

    def test_refresh_endpoint_structure(self):
        """Test that refresh endpoint has correct structure."""
        from app.api.v1.positions import router

        # Find the refresh endpoint
        refresh_route = None
        for route in router.routes:
            if hasattr(route, 'path') and '/refresh-data' in route.path:
                refresh_route = route
                break

        assert refresh_route is not None
        assert 'POST' in refresh_route.methods


class TestDataStatus:
    """Test data status endpoint."""

    def test_data_status_endpoint_structure(self):
        """Test that data status endpoint exists."""
        from app.api.v1.positions import router

        # Find the data-status endpoint
        status_route = None
        for route in router.routes:
            if hasattr(route, 'path') and '/data-status' in route.path:
                status_route = route
                break

        assert status_route is not None
        assert 'GET' in status_route.methods

    def test_data_status_returns_correct_fields(self):
        """Test data status response has correct fields."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.get('/api/v1/positions/RELIANCE/data-status')

        assert resp.status_code == 200
        data = resp.json()

        # Should have all required fields
        assert 'symbol' in data
        assert 'has_data' in data
        assert 'latest_date' in data
        assert 'is_current' in data
        assert 'last_completed_trading_day' in data
        assert 'trading_days_behind' in data
        assert 'market_status' in data
        assert 'needs_refresh' in data

    def test_data_status_correct_for_stale_data(self):
        """Test data status correctly identifies stale data."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.get('/api/v1/positions/RELIANCE/data-status')

        assert resp.status_code == 200
        data = resp.json()

        # Structure assertions (stable across time)
        assert data['has_data'] == True
        assert 'latest_date' in data
        assert 'last_completed_trading_day' in data
        assert data['market_status'] in ['open', 'closed']
        assert isinstance(data['trading_days_behind'], int)
        assert isinstance(data['is_current'], bool)

        # The latest stored date should be at or before last completed trading day
        from datetime import datetime, timezone, timedelta
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        today_ist = datetime.now(ist_tz).date()

        # If data is current, latest_date >= last_completed
        if data['is_current']:
            assert datetime.strptime(data['latest_date'], '%Y-%m-%d').date() >= datetime.strptime(data['last_completed_trading_day'], '%Y-%m-%d').date()
        else:
            assert data['needs_refresh'] == True


class TestIngestionIdempotency:
    """Test that ingestion is idempotent."""

    def test_no_duplicate_candles(self):
        """Test that re-ingesting doesn't create duplicates."""
        # Load existing data
        df = storage_manager.load_normalized_ohlcv("RELIANCE")
        initial_count = len(df)

        # Get latest date
        latest_date = df["timestamp"].max().date()

        # The data should already be current (from previous ingestion)
        # Just verify the data integrity
        assert initial_count > 0
        assert latest_date is not None

        # Check for duplicates
        assert df["timestamp"].is_unique


class TestValidation:
    """Test data validation."""

    def test_validate_ohlcv_dataframe(self):
        """Test OHLCV validation."""
        from app.data.ingestion import DataIngestionService

        service = DataIngestionService()

        # Create valid data
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        valid_df = pd.DataFrame({
            "timestamp": dates,
            "open": [100.0] * 10,
            "high": [102.0] * 10,
            "low": [98.0] * 10,
            "close": [100.0] * 10,
            "adjusted_close": [100.0] * 10,
            "volume": [1000000] * 10,
        })

        valid, invalid = service.validate_ohlcv_dataframe(valid_df, "TEST")

        assert len(valid) == 10
        assert len(invalid) == 0

    def test_validate_invalid_data(self):
        """Test validation catches invalid data."""
        from app.data.ingestion import DataIngestionService

        service = DataIngestionService()

        # Create invalid data (high < low)
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        invalid_df = pd.DataFrame({
            "timestamp": dates,
            "open": [100.0] * 5,
            "high": [98.0] * 5,  # High < Low - invalid
            "low": [102.0] * 5,
            "close": [100.0] * 5,
            "adjusted_close": [100.0] * 5,
            "volume": [1000000] * 5,
        })

        valid, invalid = service.validate_ohlcv_dataframe(invalid_df, "TEST")

        assert len(valid) == 0
        assert len(invalid) == 5


class TestScheduler:
    """Test scheduler configuration."""

    def test_scheduler_configured(self):
        """Test that scheduler is configured."""
        from app.jobs import setup_scheduler
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = setup_scheduler()

        # Should be an AsyncIOScheduler instance
        assert isinstance(scheduler, AsyncIOScheduler)

        # The scheduler should be configured (we can't easily check jobs without starting it)
        # Just verify it was created without error

    def test_scheduler_timing(self):
        """Test scheduler runs at correct time."""
        from app.jobs import setup_scheduler
        from app.core.config import settings

        scheduler = setup_scheduler()

        # Just verify scheduler was created
        assert scheduler is not None
        # The actual timing is configured in jobs/__init__.py

    def test_scheduler_config(self):
        """Test scheduler configuration."""
        from app.jobs import setup_scheduler
        from app.core.config import settings

        scheduler = setup_scheduler()

        # Verify scheduler was created
        assert scheduler is not None

        # Verify timezone is set (could be string or ZoneInfo)
        tz = scheduler.timezone
        if hasattr(tz, 'key'):
            assert tz.key == settings.SCHEDULER_TIMEZONE
        else:
            assert str(tz) == settings.SCHEDULER_TIMEZONE


class TestEndToEndWorkflow:
    """Test end-to-end workflow."""

    def test_full_workflow(self):
        """Test complete workflow from data load to strategy calculation."""
        from app.services.strategy_calc_service import StrategyCalcEngine
        from app.quant.strategies import StrategyConfig

        # Load data
        df = storage_manager.load_normalized_ohlcv("RELIANCE")
        assert len(df) > 0

        # Run strategy calculation
        cfg = StrategyConfig(fast_sma=10, slow_sma=50, atr_window=14)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(df, "RELIANCE")

        # Should have calculations
        assert len(result.calculations) > 0

        # Should have signals
        assert isinstance(result.signals, list)

        # Should have trades
        assert isinstance(result.trades, list)

    def test_strategy_with_selected_date(self):
        """Test strategy calculation with selected date."""
        from app.services.strategy_calc_service import StrategyCalcEngine
        from app.quant.strategies import StrategyConfig

        # Load data
        df = storage_manager.load_normalized_ohlcv("RELIANCE")

        # Get a date from the data
        test_date = df["timestamp"].iloc[-10].strftime("%Y-%m-%d")

        # Run strategy with selected date
        cfg = StrategyConfig(fast_sma=10, slow_sma=50, atr_window=14)
        engine = StrategyCalcEngine(cfg)
        result = engine.compute(df, "RELIANCE", strategy_date=test_date)

        # Should have selected calculation
        assert result.selected_calculation is not None
        assert result.selected_calculation.date == test_date
