import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.core.database import init_db
from app.core.logging import get_logger, setup_logging
from app.data.ingestion import ingestion_service
from app.services.asset_service import asset_service
from sqlalchemy import select
from app.models.asset import Asset

setup_logging()
logger = get_logger("batch_ingest")


async def ingest_all_assets(years: int = 5, max_workers: int = 10) -> Dict[str, Any]:
    """Ingest 5-year OHLCV for all cataloged assets in batch with concurrency control."""
    await init_db()
    from app.core.database import db_manager
    assert db_manager.session_maker is not None
    async with db_manager.session_maker() as db:
        result = await db.execute(select(Asset).where(Asset.active == True))
        assets = result.scalars().all()

    logger.info("Starting batch ingestion", total_assets=len(assets), years=years)

    import pandas as pd
    from app.data.providers.factory import get_market_data_provider
    from app.core.duckdb import duckdb_manager
    from app.data.storage import storage_manager

    provider = get_market_data_provider()
    sem = asyncio.Semaphore(max_workers)

    from datetime import datetime, timedelta, timezone
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=years * 365 + 15)

    async def ingest_one(asset: Asset) -> Dict[str, Any]:
        async with sem:
            try:
                # Check existing data and compute missing period
                existing_df = storage_manager.load_normalized_ohlcv(asset.symbol)
                local_start = start_date
                local_end = end_date
                if not existing_df.empty:
                    last_date = pd.Timestamp(existing_df["timestamp"].max()).date()
                    today = datetime.now(timezone.utc).date()
                    if last_date >= today:
                        # Already up to date
                        return {
                            "symbol": asset.symbol,
                            "status": "up_to_date",
                            "rows": len(existing_df),
                            "first_date": str(existing_df["timestamp"].min())[:10],
                            "last_date": str(existing_df["timestamp"].max())[:10],
                        }
                    # Incremental: fetch from last_date + 1
                    local_start = max(local_start, datetime.combine(last_date, datetime.min.time()).replace(tzinfo=timezone.utc))
                
                raw_df = provider.get_historical_ohlcv(
                    provider_symbol=asset.provider_symbol,
                    start_date=local_start,
                    end_date=local_end,
                    interval="1d",
                )
                if raw_df.empty:
                    return {"symbol": asset.symbol, "status": "empty", "rows": 0}
                valid_df, invalid_df = ingestion_service.validate_ohlcv_dataframe(raw_df, asset.symbol)
                if valid_df.empty:
                    return {"symbol": asset.symbol, "status": "all_invalid", "rows": 0}
                
                # Use append to avoid duplicates
                if not existing_df.empty:
                    storage_manager.append_normalized_ohlcv(valid_df, asset.symbol, asset.id, source="yahoo")
                else:
                    storage_manager.save_normalized_ohlcv(valid_df, asset.symbol, asset.id, source="yahoo")
                
                # Reload to get full picture
                final_df = storage_manager.load_normalized_ohlcv(asset.symbol)
                return {
                    "symbol": asset.symbol,
                    "status": "success",
                    "rows": len(final_df),
                    "quarantined": len(invalid_df),
                    "first_date": str(final_df["timestamp"].min())[:10],
                    "last_date": str(final_df["timestamp"].max())[:10],
                }
            except Exception as e:
                return {"symbol": asset.symbol, "status": "error", "error": str(e)[:100]}

    tasks = [ingest_one(a) for a in assets]
    results = await asyncio.gather(*tasks)

    summary = {
        "total_requested": len(assets),
        "assets_updated": sum(1 for r in results if r["status"] == "success"),
        "assets_failed": sum(1 for r in results if r["status"] not in ("success",)),
        "total_bars_ingested": sum(r.get("rows", 0) for r in results),
        "results": results,
    }
    logger.info("Batch ingestion complete", summary=summary)
    return summary


if __name__ == "__main__":
    years = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    asyncio.run(ingest_all_assets(years=years))
