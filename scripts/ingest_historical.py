import asyncio
import sys
from pathlib import Path

# Add backend directory to path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.core.database import init_db
from app.core.logging import get_logger, setup_logging
from app.data.ingestion import ingestion_service

setup_logging()
logger = get_logger("historical_ingest_script")

# Core liquid Indian assets to ingest immediately for verification
INITIAL_INGEST_SYMBOLS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "BHARTIARTL",
    "ITC",
    "LT",
    "MARUTI",
    "TATAMOTORS",
    "SUNPHARMA",
]


async def main():
    logger.info("Starting historical market data ingestion for flagship equities...")
    await init_db()

    symbols = sys.argv[1:] if len(sys.argv) > 1 else INITIAL_INGEST_SYMBOLS
    logger.info("Target symbols for ingestion", symbols=symbols)

    summary = await ingestion_service.ingest_symbols_batch(symbols=symbols, years=5)

    print("\n" + "=" * 60)
    print("ARBITER HISTORICAL INGESTION SUMMARY")
    print("=" * 60)
    print(f"Total Requested : {summary['total_requested']}")
    print(f"Assets Ingested : {summary['assets_updated']}")
    print(f"Assets Failed   : {summary['assets_failed']}")
    print("-" * 60)
    for res in summary["results"]:
        status = res.get("status")
        sym = res.get("symbol")
        rows = res.get("rows_ingested", 0)
        d_start = res.get("first_date", "N/A")
        d_end = res.get("last_date", "N/A")
        p_file = res.get("parquet_file", "N/A")
        print(f"[{sym:12}] {status.upper():10} | {rows:5} bars | {d_start} to {d_end} | {p_file}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
