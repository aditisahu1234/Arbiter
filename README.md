# Arbiter - Quantitative Market Analysis Platform

Complete quantitative trading platform with:
- Market data ingestion from Yahoo Finance
- Strategy backtesting with SMA Crossover + ATR Stop-loss
- Risk analytics (CAPM, Fama-French 3-Factor)
- Position tracking and monitoring
- Real-time market status

## Features

### Core Quant Engine
- Next-bar-open execution (no look-ahead bias)
- ATR-based stop-loss with gap handling
- Transaction cost modeling
- Full backtest metrics (Sharpe, Sortino, Max DD, Win Rate, Profit Factor)

### Data Pipeline
- 512 Indian equity assets in catalog
- ~613K OHLCV bars (2021-2026)
- Parquet lakehouse storage with DuckDB
- Daily ingestion via APScheduler

### Strategy Lab
- Configure SMA crossover parameters
- Run backtests with real historical data
- View equity curves and trade logs
- Track positions persistently

### Risk Analytics
- CAPM with RBI risk-free rate provider
- Fama-French 3-Factor with IIM Ahmedabad or synthetic factors
- Alpha, Beta, R² calculations

### Position Management
- Persistent position storage in PostgreSQL/SQLite
- Live price monitoring during market hours
- Automatic exit condition evaluation
- P&L tracking with transaction costs

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
cd frontend && npm install

# Start backend
uvicorn app.main:app --reload --port 8000

# Start frontend
cd frontend && npm run dev

# Run tests
cd backend && python -m pytest tests/unit -v
```

## API Endpoints

- `GET /api/v1/assets` - List assets
- `GET /api/v1/assets/{symbol}/ohlcv` - Get OHLCV data
- `POST /api/v1/strategies/backtest` - Run backtest
- `GET /api/v1/risk/capm` - CAPM analysis
- `GET /api/v1/risk/fama-french` - FF3 analysis
- `POST /api/v1/positions` - Create position
- `GET /api/v1/positions/open` - List open positions
- `POST /api/v1/positions/strategy-calculations` - Run strategy calculations
- `GET /api/v1/monitor/market-status` - Market status

## Testing

```bash
cd backend
python -m pytest tests/unit -v
```

All 80 tests passing with 0 skipped.
