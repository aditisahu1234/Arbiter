"""APScheduler daily market data ingestion job."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.config import settings
from app.core.database import db_manager
from app.core.logging import get_logger
from app.data.ingestion import ingestion_service
from app.data.storage import storage_manager
from app.models.job import JobRun
from sqlalchemy import select

logger = get_logger("scheduler")


async def run_daily_ingestion_job() -> Dict[str, Any]:
    """Main daily ingestion job: fetch delta data for all assets."""
    logger.info("Starting daily market data ingestion job")

    import pandas as pd
    from app.models.asset import Asset

    assert db_manager.session_maker is not None
    async with db_manager.session_maker() as db:
        job = JobRun(
            job_id=f"daily_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            job_type="daily_ingestion",
            status="RUNNING",
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.flush()
        job_id = job.id

        assets_result = await db.execute(select(Asset).where(Asset.active == True))
        assets = assets_result.scalars().all()

    logger.info("Processing daily ingestion for %d assets", len(assets))

    results: List[Dict[str, Any]] = []
    success_count = 0
    fail_count = 0

    for asset in assets:
        try:
            last_df = storage_manager.load_normalized_ohlcv(asset.symbol)
            if not last_df.empty:
                last_date = pd.Timestamp(last_df["timestamp"].max()).date()
                today = datetime.now(timezone.utc).date()
                if last_date >= today:
                    continue

            ingest_res = await ingestion_service.ingest_asset_historical(
                symbol=asset.symbol,
                asset_id=asset.id,
                provider_symbol=asset.provider_symbol,
                years=1,
            )
            if ingest_res["status"] == "success":
                success_count += 1
            else:
                fail_count += 1
            results.append(ingest_res)
        except Exception as e:
            logger.error("Failed to ingest %s", asset.symbol, error=str(e))
            fail_count += 1
            results.append({"symbol": asset.symbol, "status": "error", "error": str(e)})

    async with db_manager.session_maker() as db:
        job_record = await db.get(JobRun, job_id)
        if job_record:
            job_record.status = "COMPLETED" if fail_count == 0 else "FAILED"
            job_record.completed_at = datetime.now(timezone.utc)
            job_record.assets_requested = len(assets)
            job_record.assets_updated = success_count
            job_record.assets_failed = fail_count
            await db.commit()

    logger.info("Daily ingestion job completed: %d success, %d failed", success_count, fail_count)
    return {
        "job_id": job_id,
        "total": len(assets),
        "success": success_count,
        "failed": fail_count,
    }
