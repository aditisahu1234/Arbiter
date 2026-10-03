from datetime import datetime, timedelta

import pandas as pd

from app.core.duckdb import duckdb_manager
from app.data.storage import storage_manager


def test_parquet_storage_and_duckdb_query(tmp_path):
    """Test full cycle: save Parquet, query with DuckDB, verify schema and values."""
    symbol = "TESTASSET"
    asset_id = 999

    # Generate 10 days of sample OHLCV data
    base_date = datetime(2024, 1, 1)
    dates = [base_date + timedelta(days=i) for i in range(10)]
    df = pd.DataFrame(
        {
            "timestamp": dates,
            "open": [100.0 + i for i in range(10)],
            "high": [105.0 + i for i in range(10)],
            "low": [98.0 + i for i in range(10)],
            "close": [102.0 + i for i in range(10)],
            "adjusted_close": [101.5 + i for i in range(10)],
            "volume": [1000000 + i * 1000 for i in range(10)],
        }
    )

    # Save to Parquet
    saved_path = storage_manager.save_normalized_ohlcv(df, symbol, asset_id, source="test")
    assert saved_path.exists()

    # Query via DuckDB
    res_df = duckdb_manager.get_asset_ohlcv(symbol)
    assert not res_df.empty
    assert len(res_df) == 10
    assert "close" in res_df.columns
    assert "adjusted_close" in res_df.columns
    assert res_df["close"].iloc[0] == 102.0
    assert res_df["symbol"].iloc[0] == symbol
    assert res_df["asset_id"].iloc[0] == asset_id

    # Test latest timestamp
    latest_ts = duckdb_manager.get_latest_timestamp(symbol)
    assert latest_ts is not None
    assert latest_ts.day == 10


def test_parquet_append_and_deduplication():
    """Test that appending overlapping timestamps updates rather than duplicates rows."""
    symbol = "TESTDEDUP"
    asset_id = 888

    # First batch: days 1 to 5
    base_date = datetime(2024, 2, 1)
    df1 = pd.DataFrame(
        {
            "timestamp": [base_date + timedelta(days=i) for i in range(5)],
            "open": [200.0] * 5,
            "high": [210.0] * 5,
            "low": [195.0] * 5,
            "close": [205.0] * 5,
            "adjusted_close": [205.0] * 5,
            "volume": [50000] * 5,
        }
    )
    storage_manager.save_normalized_ohlcv(df1, symbol, asset_id)

    # Second batch: days 3 to 7 (days 3 and 4 overlap, with updated close)
    df2 = pd.DataFrame(
        {
            "timestamp": [base_date + timedelta(days=i) for i in range(3, 8)],
            "open": [200.0] * 5,
            "high": [210.0] * 5,
            "low": [195.0] * 5,
            "close": [222.0] * 5,  # updated price for overlapping dates
            "adjusted_close": [222.0] * 5,
            "volume": [60000] * 5,
        }
    )
    storage_manager.append_normalized_ohlcv(df2, symbol, asset_id)

    # Result should have exactly 8 unique dates (days 0 to 7)
    res_df = duckdb_manager.get_asset_ohlcv(symbol)
    assert len(res_df) == 8
    # Overwritten row should have the updated close 222.0
    overlapping_row = res_df[res_df["timestamp"] == pd.Timestamp(base_date + timedelta(days=3))]
    assert not overlapping_row.empty
    assert overlapping_row["close"].iloc[0] == 222.0

    # Cleanup test files
    path1 = storage_manager.get_asset_parquet_path(symbol)
    if path1.exists():
        path1.unlink()
    path2 = storage_manager.get_asset_parquet_path("TESTASSET")
    if path2.exists():
        path2.unlink()
