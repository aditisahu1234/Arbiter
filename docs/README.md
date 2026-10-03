# Arbiter Quantitative Market Analysis & Strategy Research Platform

Institutional-grade quantitative analysis platform for Indian equities.

## Architecture

4-layer unidirectional dependency:
- **Layer 4**: React + TypeScript + Vite + Tailwind CSS frontend
- **Layer 3**: FastAPI REST API with Pydantic validation
- **Layer 2**: Vectorized Python quantitative engine (indicators, strategies, backtester, risk)
- **Layer 1**: DuckDB (Parquet OLAP) + PostgreSQL (metadata OLTP) + Redis (caching)

## Quick Start

```bash
# Seed database with 512 assets
python scripts/seed_universes.py

# Ingest historical data for specific assets
python scripts/ingest_historical.py RELIANCE TCS INFY

# Or full batch (512 assets, ~5 years each - takes 30-60 min)
python scripts/ingest_all_assets.py 5

# Start backend
cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# Start frontend
cd frontend && npm run dev
```

## API Endpoints

- `GET /health` - Health check
- `GET /api/v1/assets` - List assets with filtering
- `GET /api/v1/assets/{symbol}/ohlcv` - Historical OHLCV data
- `GET /api/v1/universes` - List universes
- `GET /api/v1/indicators/sma?symbol=X&window=20` - SMA indicator
- `GET /api/v1/indicators/atr?symbol=X&window=14` - ATR indicator
- `POST /api/v1/strategies/backtest?symbol=X` - Run backtest
- `GET /api/v1/risk/capm?symbol=X` - CAPM analysis
- `GET /api/v1/risk/fama-french?symbol=X` - Fama-French 3-factor
- `GET /api/v1/market-data/lakehouse` - Data lakehouse status
- `POST /api/v1/market-data/ingest/{symbol}` - Trigger ingestion

## Quant Methodology

- **ATR**: Wilder's RMA (n=14 default), configurable to SMA/EMA
- **Execution**: Next-bar-open to prevent look-ahead bias
- **Stop-loss**: Intraday low check, gap-down handled
- **Transaction costs**: Configurable bps (default 10 bps round-trip)
- **Risk-free rate**: Configurable annual rate, converted to daily
- **Market proxy**: NIFTY 50 (^NSEI)

## Testing

```bash
cd backend && .venv/bin/pytest tests/ -v
```

## Data

- **Parquet storage**: `data/normalized/*.parquet`
- **Raw data**: `data/raw/yahoo/`
- **Quarantine**: `data/quarantine/`
- **Factors**: `data/factors/` (SMB/HML computed synthetically)

## Phases Completed

- **Phase 0-3**: Foundation, Infrastructure, Data Platform, Asset/Universe Management, Yahoo Provider
- **Phase 4-6**: Historical Ingestion, Validation/Normalization, Incremental Scheduler
- **Phase 7-12**: Indicators (SMA/TR/ATR), Strategy Engine, Backtester, Costs, CAPM, Fama-French
- **Phase 13**: FastAPI Endpoints for all quant modules
