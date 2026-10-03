"""Test ingestion idempotency and incremental behavior."""
from datetime import datetime, timedelta, timezone
import pandas as pd
import pytest
from unittest.mock import Mock, patch

from app.data.storage import storage_manager
from app.data.ingestion import ingestion_service
from app.quant.indicators import SimpleMovingAverage, AverageTrueRange


def test_idempotent_ingestion():
    """Running ingestion twice should not create duplicates."""
    symbol = "IDEMPOTENT_TEST"
    
    # Create test data
    base_date = datetime(2024, 1, 1)
    df = pd.DataFrame({
        "timestamp": [base_date + timedelta(days=i) for i in range(10)],
        "open": [100.0] * 10,
        "high": [105.0] * 10,
        "low": [98.0] * 10,
        "close": [102.0] * 10,
        "adjusted_close": [101.5] * 10,
        "volume": [1000000] * 10,
    })
    
    # Save first time
    storage_manager.save_normalized_ohlcv(df, symbol, 9999, source="test")
    
    # Save again with same data
    storage_manager.save_normalized_ohlcv(df, symbol, 9999, source="test")
    
    # Load and verify no duplicates
    result = storage_manager.load_normalized_ohlcv(symbol)
    assert len(result) == 10, f"Expected 10 rows, got {len(result)}"
    
    # Cleanup
    import os
    os.remove(storage_manager.get_asset_parquet_path(symbol))


def test_incremental_append():
    """Appending new data should extend, not duplicate."""
    symbol = "INCREMENTAL_TEST"
    
    # First batch: days 0-4
    base_date = datetime(2024, 2, 1)
    df1 = pd.DataFrame({
        "timestamp": [base_date + timedelta(days=i) for i in range(5)],
        "open": [200.0] * 5,
        "high": [210.0] * 5,
        "low": [195.0] * 5,
        "close": [205.0] * 5,
        "adjusted_close": [205.0] * 5,
        "volume": [50000] * 5,
    })
    
    # Second batch: days 5-9 (non-overlapping)
    df2 = pd.DataFrame({
        "timestamp": [base_date + timedelta(days=i) for i in range(5, 10)],
        "open": [210.0] * 5,
        "high": [220.0] * 5,
        "low": [205.0] * 5,
        "close": [215.0] * 5,
        "adjusted_close": [215.0] * 5,
        "volume": [60000] * 5,
    })
    
    storage_manager.save_normalized_ohlcv(df1, symbol, 9998, source="test")
    storage_manager.append_normalized_ohlcv(df2, symbol, 9998, source="test")
    
    result = storage_manager.load_normalized_ohlcv(symbol)
    assert len(result) == 10, f"Expected 10 rows, got {len(result)}"
    assert result["timestamp"].min() == base_date
    assert result["timestamp"].max() == base_date + timedelta(days=9)
    
    # Cleanup
    import os
    os.remove(storage_manager.get_asset_parquet_path(symbol))


def test_incremental_overlap():
    """Appending overlapping data should update, not duplicate."""
    symbol = "OVERLAP_TEST"
    
    base_date = datetime(2024, 3, 1)
    # First batch: days 0-4
    df1 = pd.DataFrame({
        "timestamp": [base_date + timedelta(days=i) for i in range(5)],
        "open": [300.0] * 5,
        "high": [310.0] * 5,
        "low": [295.0] * 5,
        "close": [305.0] * 5,
        "adjusted_close": [305.0] * 5,
        "volume": [70000] * 5,
    })
    
    # Second batch: days 3-7 (overlap on days 3-4)
    df2 = pd.DataFrame({
        "timestamp": [base_date + timedelta(days=i) for i in range(3, 8)],
        "open": [320.0] * 5,
        "high": [330.0] * 5,
        "low": [315.0] * 5,
        "close": [325.0] * 5,
        "adjusted_close": [325.0] * 5,
        "volume": [80000] * 5,
    })
    
    storage_manager.save_normalized_ohlcv(df1, symbol, 9997, source="test")
    storage_manager.append_normalized_ohlcv(df2, symbol, 9997, source="test")
    
    result = storage_manager.load_normalized_ohlcv(symbol)
    assert len(result) == 8, f"Expected 8 rows, got {len(result)}"
    
    # Check that overlapping dates have updated values
    day3 = result[result["timestamp"] == base_date + timedelta(days=3)]
    assert len(day3) == 1
    assert day3["close"].iloc[0] == 325.0  # Updated value
    
    # Cleanup
    import os
    os.remove(storage_manager.get_asset_parquet_path(symbol))
