from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.duckdb import duckdb_manager
from app.data.ingestion import ingestion_service
from app.models.asset import Asset

router = APIRouter(prefix="/market-data", tags=["Market Data"])


@router.get("/lakehouse", response_model=dict[str, Any])
async def get_lakehouse_status():
    """Returns analytics status of the Parquet lakehouse and DuckDB database."""
    normalized_dir = settings.DATA_NORMALIZED_DIR
    parquet_files = list(normalized_dir.glob("*.parquet"))

    total_size_bytes = sum(f.stat().st_size for f in parquet_files)
    file_stats = []
    total_bars = 0

    for f in sorted(parquet_files):
        sym = f.stem
        latest_ts = duckdb_manager.get_latest_timestamp(sym)
        try:
            cnt_df = duckdb_manager.query_df(f"SELECT COUNT(*) as cnt FROM read_parquet('{f}')")
            cnt = int(cnt_df["cnt"].iloc[0]) if not cnt_df.empty else 0
        except Exception:
            cnt = 0
        total_bars += cnt
        file_stats.append(
            {
                "symbol": sym,
                "filename": f.name,
                "size_kb": round(f.stat().st_size / 1024, 2),
                "rows": cnt,
                "latest_date": latest_ts.strftime("%Y-%m-%d") if latest_ts is not None else None,
            }
        )

    return {
        "lakehouse_dir": str(normalized_dir),
        "total_files": len(parquet_files),
        "total_bars_ingested": total_bars,
        "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
        "assets": file_stats,
    }


@router.post("/ingest/{symbol}")
async def trigger_asset_ingest(
    symbol: str,
    years: int = 5,
    db: AsyncSession = Depends(get_db),
):
    """Dynamically trigger market data ingestion for an individual asset from Yahoo Finance."""
    res = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = res.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset '{symbol}' not found in catalog")

    result = await ingestion_service.ingest_asset_historical(
        symbol=asset.symbol,
        asset_id=asset.id,
        provider_symbol=asset.provider_symbol,
        years=years,
    )
    return result


@router.post("/ingest-batch")
async def trigger_batch_ingest(
    symbols: list[str],
    years: int = 5,
):
    """Trigger ingestion for a batch of symbols."""
    result = await ingestion_service.ingest_symbols_batch(symbols=symbols, years=years)
    return result
