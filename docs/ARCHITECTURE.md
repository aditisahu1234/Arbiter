# Arbiter Architecture

## Layer 1: Data Platform

### Storage
- **PostgreSQL** (or SQLite fallback): Metadata - assets, universes, job runs, users
- **Parquet** (data/normalized/): Canonical OHLCV data with ZSTD compression
- **DuckDB**: In-process OLAP engine reading directly from Parquet files
- **Redis** (fallback: in-memory cache): Session management, computed result caching

### Provider Abstraction
- `MarketDataProvider` abstract base class
- `YahooFinanceProvider`: Resilient batching with exponential backoff
- `MockMarketDataProvider`: Deterministic testing

### Validation Pipeline
- Mathematical invariants: H≥L, H≥O, H≥C, L≤O, L≤C, V≥0, P>0
- Duplicate timestamp detection
- Null value rejection
- Quarantine workflow for invalid records

## Layer 2: Quantitative Engine

### Indicators
- SMA (Simple Moving Average) - configurable window
- EMA (Exponential Moving Average) - configurable span
- TR (True Range) - max(H-L, |H-C_prev|, |L-C_prev|)
- ATR (Average True Range) - Wilder's RMA default, SMA/EMA optional
- Returns: simple, log, cumulative, annualized, volatility

### Strategy Engine
- SMA Crossover + ATR Stop-loss
- Signal generation: BUY on fast>slow cross-up, SELL on cross-down
- Stop-loss: entry_price - k*ATR, checked intraday

### Backtester
- Next-bar-open execution (no look-ahead bias)
- Position tracking: cash, shares, equity
- Trade log with entry/exit details
- Metrics: CAGR, Sharpe, Sortino, Max DD, Win Rate, Profit Factor

### Risk Engine
- CAPM: OLS regression of excess asset returns on excess market returns
- Fama-French 3-Factor: Multi-variable regression with SMB/HML

## Layer 3: Platform API

- FastAPI with Pydantic v2 validation
- Request ID middleware
- Latency logging
- CORS configuration
- Exception handling

## Layer 4: Frontend Terminal

- React 18 + TypeScript + Vite + Tailwind CSS
- TradingView Lightweight Charts
- TanStack Query for data fetching
- Zustand for state management
- Dark terminal aesthetic
