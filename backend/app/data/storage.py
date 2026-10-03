from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from app.core.config import settings
from app.core.duckdb import duckdb_manager
from app.core.logging import get_logger

logger = get_logger("storage")

# Canonical PyArrow Schema for Normalized OHLCV Parquet files
NORMALIZED_OHLCV_SCHEMA = pa.schema([
    ("asset_id", pa.int64()),
    ("symbol", pa.string()),
    ("timestamp", pa.timestamp("ns")),
    ("open", pa.float64()),
    ("high", pa.float64()),
    ("low", pa.float64()),
    ("close", pa.float64()),
    ("adjusted_close", pa.float64()),
    ("volume", pa.int64()),
    ("source", pa.string()),
    ("ingested_at", pa.timestamp("ns")),
])


class ParquetStorageManager:
    """Manages raw and normalized Parquet lakehouse storage."""

    def __init__(
        self,
        raw_dir: Optional[Path] = None,
        normalized_dir: Optional[Path] = None,
        quarantine_dir: Optional[Path] = None,
    ):
        self.raw_dir = raw_dir or settings.DATA_RAW_DIR
        self.normalized_dir = normalized_dir or settings.DATA_NORMALIZED_DIR
        self.quarantine_dir = quarantine_dir or settings.DATA_QUARANTINE_DIR

        # Ensure directories exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def get_asset_parquet_path(self, symbol: str) -> Path:
        """Get the file path for an asset's normalized Parquet file."""
        return self.normalized_dir / f"{symbol}.parquet"

    def save_normalized_ohlcv(
        self,
        df: pd.DataFrame,
        symbol: str,
        asset_id: int,
        source: str = "yahoo",
    ) -> Path:
        """Save or overwrite normalized OHLCV data for an asset."""
        if df.empty:
            raise ValueError(f"Cannot save empty DataFrame for asset {symbol}")

        # Ensure canonical columns and types
        df_norm = df.copy()
        df_norm["asset_id"] = int(asset_id)
        df_norm["symbol"] = str(symbol)
        df_norm["source"] = str(source)
        df_norm["ingested_at"] = pd.Timestamp.now(tz=timezone.utc).tz_localize(None)

        # Standardize timestamp to naive UTC timestamp
        df_norm["timestamp"] = pd.to_datetime(df_norm["timestamp"]).dt.tz_localize(None)
        df_norm = df_norm.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")

        for col in ["open", "high", "low", "close", "adjusted_close"]:
            df_norm[col] = df_norm[col].astype(float)
        df_norm["volume"] = df_norm["volume"].fillna(0).astype("int64")

        ordered_cols = [
            "asset_id",
            "symbol",
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "adjusted_close",
            "volume",
            "source",
            "ingested_at",
        ]
        df_norm = df_norm[ordered_cols]

        file_path = self.get_asset_parquet_path(symbol)
        table = pa.Table.from_pandas(df_norm, schema=NORMALIZED_OHLCV_SCHEMA, preserve_index=False)
        pq.write_table(table, file_path, compression="zstd")

        # Refresh DuckDB view
        duckdb_manager.refresh_views()
        logger.info("Saved normalized OHLCV Parquet", symbol=symbol, rows=len(df_norm), path=str(file_path))
        return file_path

    def append_normalized_ohlcv(
        self,
        new_df: pd.DataFrame,
        symbol: str,
        asset_id: int,
        source: str = "yahoo",
    ) -> Path:
        """Append incremental rows to existing Parquet file, deduplicating on timestamp."""
        file_path = self.get_asset_parquet_path(symbol)
        if not file_path.exists():
            return self.save_normalized_ohlcv(new_df, symbol, asset_id, source)

        # Read existing data
        existing_table = pq.read_table(file_path)
        existing_df = existing_table.to_pandas()

        # Prepare new data
        incoming = new_df.copy()
        incoming["asset_id"] = int(asset_id)
        incoming["symbol"] = str(symbol)
        incoming["source"] = str(source)
        incoming["ingested_at"] = pd.Timestamp.now(tz=timezone.utc).tz_localize(None)
        incoming["timestamp"] = pd.to_datetime(incoming["timestamp"]).dt.tz_localize(None)

        for col in ["open", "high", "low", "close", "adjusted_close"]:
            incoming[col] = incoming[col].astype(float)
        incoming["volume"] = incoming["volume"].fillna(0).astype("int64")

        # Merge and deduplicate
        combined = pd.concat([existing_df, incoming], ignore_index=True)
        combined = combined.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")

        ordered_cols = [
            "asset_id",
            "symbol",
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "adjusted_close",
            "volume",
            "source",
            "ingested_at",
        ]
        combined = combined[ordered_cols]

        table = pa.Table.from_pandas(combined, schema=NORMALIZED_OHLCV_SCHEMA, preserve_index=False)
        pq.write_table(table, file_path, compression="zstd")

        duckdb_manager.refresh_views()
        logger.info(
            "Appended normalized OHLCV Parquet",
            symbol=symbol,
            new_rows=len(incoming),
            total_rows=len(combined),
        )
        return file_path

    def load_normalized_ohlcv(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Load normalized OHLCV data using DuckDB for high-speed predicate pushdown."""
        return duckdb_manager.get_asset_ohlcv(symbol, start_date, end_date)

    def quarantine_records(
        self,
        records: pd.DataFrame,
        symbol: str,
        reason: str,
    ) -> Path:
        """Save rejected or invalid records to quarantine for auditing."""
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        quarantine_file = self.quarantine_dir / f"{symbol}_{timestamp_str}.csv"
        records_copy = records.copy()
        records_copy["quarantine_reason"] = reason
        records_copy["quarantined_at"] = datetime.now(timezone.utc).isoformat()
        records_copy.to_csv(quarantine_file, index=False)
        logger.warning(
            "Quarantined invalid market data records",
            symbol=symbol,
            rows=len(records),
            reason=reason,
            path=str(quarantine_file),
        )
        return quarantine_file


storage_manager = ParquetStorageManager()
