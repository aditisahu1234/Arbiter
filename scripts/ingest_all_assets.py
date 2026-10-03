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
    assert ingestion_service.db_manager.session_maker is not None
    async with ingestion_service.db_manager.session_maker() as db:
        result = await db.execute(select(Asset).where(Asset.active == True))
        assets = result.scalars().all()

    logger.info("Starting batch ingestion", total_assets=len(assets), years=years)

    import aiohttp
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
                raw_df = provider.get_historical_ohlcv(
                    provider_symbol=asset.provider_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval="1d",
                )
                if raw_df.empty:
                    return {"symbol": asset.symbol, "status": "empty", "rows": 0}
                valid_df, invalid_df = ingestion_service.validate_ohlcv_dataframe(raw_df, asset.symbol)
                if valid_df.empty:
                    return {"symbol": asset.symbol, "status": "all_invalid", "rows": 0}
                storage_manager.save_normalized_ohlcv(valid_df, asset.symbol, asset.id, source="yahoo")
                return {
                    "symbol": asset.symbol,
                    "status": "success",
                    "rows": len(valid_df),
                    "quarantined": len(invalid_df),
                    "first_date": str(valid_df["timestamp"].min())[:10],
                    "last_date": str(valid_df["timestamp"].max())[:10],
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
