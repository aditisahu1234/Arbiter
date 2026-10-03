from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("duckdb")


class DuckDBManager:
    """Manages DuckDB in-process OLAP connections and Parquet analytical views."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(settings.BASE_DIR / settings.DUCKDB_PATH)
        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: duckdb.DuckDBPyConnection | None = None

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get or initialize the DuckDB connection."""
        if self._conn is None:
            # We connect in read_only=False mode
            self._conn = duckdb.connect(database=self.db_path, read_only=False)
            self._setup_views()
        return self._conn

    def _setup_views(self) -> None:
        """Create analytical views over Parquet lakehouse directories."""
        conn = self._conn
        if conn is None:
            return

        normalized_glob = str(settings.DATA_NORMALIZED_DIR / "*.parquet")
        # Check if normalized files exist
        has_parquet = len(list(settings.DATA_NORMALIZED_DIR.glob("*.parquet"))) > 0

        try:
            if has_parquet:
                conn.execute(f"""
                    CREATE OR REPLACE VIEW ohlcv_all AS
                    SELECT * FROM read_parquet('{normalized_glob}');
                """)
                logger.debug("Registered ohlcv_all view over parquet files", path=normalized_glob)
            else:
                # Create empty schema table if no files exist yet
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ohlcv_all (
                        asset_id INTEGER,
                        symbol VARCHAR,
                        timestamp TIMESTAMP,
                        open DOUBLE,
                        high DOUBLE,
                        low DOUBLE,
                        close DOUBLE,
                        adjusted_close DOUBLE,
                        volume BIGINT,
                        source VARCHAR,
                        ingested_at TIMESTAMP
                    );
                """)
        except Exception as e:
            logger.warning("Failed to setup ohlcv_all view in DuckDB", error=str(e))

    def refresh_views(self) -> None:
        """Refresh views when new Parquet files are written."""
        self._setup_views()

    def query_df(self, query: str, parameters: list[Any] | None = None) -> pd.DataFrame:
        """Execute a query and return results as a Pandas DataFrame."""
        conn = self.get_connection()
        if parameters:
            return conn.execute(query, parameters).fetchdf()
        return conn.execute(query).fetchdf()

    def get_asset_ohlcv(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Retrieve historical OHLCV data for an asset from DuckDB / Parquet lakehouse."""
        # Check asset-specific parquet file directly first for maximum speed
        asset_parquet = settings.DATA_NORMALIZED_DIR / f"{symbol}.parquet"
        if asset_parquet.exists():
            conditions = ["1=1"]
            params: list[Any] = []
            if start_date:
                conditions.append("timestamp >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("timestamp <= ?")
                params.append(end_date)

            sql = f"""
                SELECT * FROM read_parquet('{asset_parquet}')
                WHERE {' AND '.join(conditions)}
                ORDER BY timestamp ASC
            """
            return self.query_df(sql, params)

        # Fallback to querying ohlcv_all view
        conditions = ["symbol = ?"]
        params = [symbol]
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)

        sql = f"""
            SELECT * FROM ohlcv_all
            WHERE {' AND '.join(conditions)}
            ORDER BY timestamp ASC
        """
        try:
            return self.query_df(sql, params)
        except Exception as e:
            logger.warning("Error fetching OHLCV from DuckDB", symbol=symbol, error=str(e))
            return pd.DataFrame()

    def get_latest_timestamp(self, symbol: str) -> pd.Timestamp | None:
        """Get the most recent timestamp available for an asset."""
        asset_parquet = settings.DATA_NORMALIZED_DIR / f"{symbol}.parquet"
        if asset_parquet.exists():
            sql = f"SELECT MAX(timestamp) as max_ts FROM read_parquet('{asset_parquet}')"
            df = self.query_df(sql)
            if not df.empty and pd.notna(df["max_ts"].iloc[0]):
                return pd.to_datetime(df["max_ts"].iloc[0])

        try:
            df = self.query_df("SELECT MAX(timestamp) as max_ts FROM ohlcv_all WHERE symbol = ?", [symbol])
            if not df.empty and pd.notna(df["max_ts"].iloc[0]):
                return pd.to_datetime(df["max_ts"].iloc[0])
        except Exception:
            pass
        return None

    def close(self) -> None:
        """Close connection cleanly."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None


duckdb_manager = DuckDBManager()
