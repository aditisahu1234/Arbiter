from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import db_manager
from app.core.duckdb import duckdb_manager
from app.core.logging import get_logger
from app.core.cache import invalidate_cache
from app.data.providers.factory import get_market_data_provider
from app.data.storage import storage_manager
from app.models.asset import Asset
from app.models.job import JobRun

logger = get_logger("ingestion")


class DataIngestionService:
    """Orchestrates historical and incremental market data downloads, validation, and storage."""

    def __init__(self, provider_name: Optional[str] = None):
        self.provider = get_market_data_provider(provider_name or settings.MARKET_DATA_PROVIDER)

    def validate_ohlcv_dataframe(self, df: pd.DataFrame, symbol: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Strict validation of OHLCV data.

        Invariants:
        1. High >= Low
        2. High >= Open and High >= Close
        3. Low <= Open and Low <= Close
        4. Prices > 0
        5. Volume >= 0
        6. No duplicate timestamps
        7. No missing/null values in key columns

        Returns (valid_df, invalid_df).
        """
        if df.empty:
            return df, pd.DataFrame()

        clean_df = df.copy()

        # Check required columns
        req_cols = ["timestamp", "open", "high", "low", "close", "volume"]
        for col in req_cols:
            if col not in clean_df.columns:
                raise ValueError(f"Missing required column '{col}' in OHLCV DataFrame for {symbol}")

        # Drop rows with nulls in OHLC
        null_mask = clean_df[["open", "high", "low", "close"]].isnull().any(axis=1)

        # Mathematical price invariants
        valid_math = (
            (clean_df["high"] >= clean_df["low"])
            & (clean_df["high"] >= clean_df["open"] - 1e-4)
            & (clean_df["high"] >= clean_df["close"] - 1e-4)
            & (clean_df["low"] <= clean_df["open"] + 1e-4)
            & (clean_df["low"] <= clean_df["close"] + 1e-4)
            & (clean_df["open"] > 0)
            & (clean_df["high"] > 0)
            & (clean_df["low"] > 0)
            & (clean_df["close"] > 0)
            & (clean_df["volume"] >= 0)
        )

        valid_mask = (~null_mask) & valid_math

        valid_df = clean_df[valid_mask].copy()
        invalid_df = clean_df[~valid_mask].copy()

        # Deduplicate valid_df on timestamp
        valid_df = valid_df.drop_duplicates(subset=["timestamp"], keep="last")

        if not invalid_df.empty:
            storage_manager.quarantine_records(
                invalid_df, symbol=symbol, reason="Violated OHLC price bounds or contained nulls"
            )

        return valid_df, invalid_df

    async def ingest_asset_historical(
        self,
        symbol: str,
        asset_id: int,
        provider_symbol: str,
        years: int = 5,
    ) -> Dict[str, Any]:
        """Download historical OHLCV data for an individual asset, validate, and persist to Parquet."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=years * 365 + 15)

        logger.info(
            "Fetching historical market data from provider",
            symbol=symbol,
            provider_symbol=provider_symbol,
            provider=self.provider.name,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
        )

        raw_df = self.provider.get_historical_ohlcv(
            provider_symbol=provider_symbol,
            start_date=start_date,
            end_date=end_date,
            interval="1d",
        )

        if raw_df.empty:
            logger.warning("No data returned by provider", symbol=symbol, provider_symbol=provider_symbol)
            return {
                "symbol": symbol,
                "status": "empty",
                "rows_ingested": 0,
                "first_date": None,
                "last_date": None,
            }

        valid_df, invalid_df = self.validate_ohlcv_dataframe(raw_df, symbol=symbol)

        if valid_df.empty:
            logger.error("All records for symbol were quarantined as invalid", symbol=symbol)
            return {
                "symbol": symbol,
                "status": "all_invalid",
                "rows_ingested": 0,
                "first_date": None,
                "last_date": None,
            }

        saved_path = storage_manager.save_normalized_ohlcv(
            df=valid_df,
            symbol=symbol,
            asset_id=asset_id,
            source=self.provider.name,
        )

        # Invalidate cache for this asset
        await invalidate_cache(pattern=symbol)

        first_ts = valid_df["timestamp"].min()
        last_ts = valid_df["timestamp"].max()

        logger.info(
            "Successfully ingested asset market data",
            symbol=symbol,
            valid_bars=len(valid_df),
            quarantined_bars=len(invalid_df),
            first_date=str(first_ts),
            last_date=str(last_ts),
            parquet_path=str(saved_path),
        )

        return {
            "symbol": symbol,
            "status": "success",
            "rows_ingested": len(valid_df),
            "quarantined_rows": len(invalid_df),
            "first_date": first_ts.strftime("%Y-%m-%d") if pd.notna(first_ts) else None,
            "last_date": last_ts.strftime("%Y-%m-%d") if pd.notna(last_ts) else None,
            "parquet_file": saved_path.name,
        }

    async def ingest_symbols_batch(
        self,
        symbols: List[str],
        years: int = 5,
    ) -> Dict[str, Any]:
        """Ingest a list of symbols in batch."""
        assert db_manager.session_maker is not None
        results = []
        updated_count = 0
        failed_count = 0

        async with db_manager.session_maker() as db:
            for symbol in symbols:
                res = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
                asset = res.scalar_one_or_none()
                if not asset:
                    logger.warning("Asset not found in catalog", symbol=symbol)
                    failed_count += 1
                    continue

                try:
                    ingest_res = await self.ingest_asset_historical(
                        symbol=asset.symbol,
                        asset_id=asset.id,
                        provider_symbol=asset.provider_symbol,
                        years=years,
                    )
                    results.append(ingest_res)
                    if ingest_res["status"] == "success":
                        updated_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error("Failed to ingest asset", symbol=symbol, error=str(e))
                    failed_count += 1
                    results.append({"symbol": symbol, "status": "error", "error": str(e)})

        return {
            "total_requested": len(symbols),
            "assets_updated": updated_count,
            "assets_failed": failed_count,
            "results": results,
        }


ingestion_service = DataIngestionService()
