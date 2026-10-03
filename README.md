# Arbiter (Quant Platform)

> **Institutional-Grade Quantitative Market Analysis & Strategy Research Platform**

Arbiter is a modular, high-performance quantitative research terminal and computational engine built with Python, FastAPI, DuckDB, PostgreSQL, Redis, and React. It provides complete historical/incremental market data pipelines, mathematical indicator engines, deterministic backtesting simulation, factor risk models (CAPM, Fama-French), and a responsive financial trading terminal.

---

## Architecture Overview

```
Layer 4: User Experience (React + TypeScript + Vite + Tailwind CSS + Lightweight Charts)
   │
Layer 3: Platform / API (FastAPI, Redis Caching, Pydantic v2, Structured Logs)
   │
Layer 2: Quantitative Engine (Vectorized Indicators, Strategy, Backtester, CAPM, Fama-French)
   │
Layer 1: Data Platform (DuckDB OLAP + PostgreSQL Metadata + Parquet Lakehouse + yfinance Provider)
```

---

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Pydantic v2, Pandas, NumPy, SciPy, Statsmodels
- **Storage**: PostgreSQL 16 (metadata/OLTP), DuckDB & Apache Parquet (market analytics/OLAP), Redis 7 (caching)
- **Market Data**: Multi-provider architecture (Yahoo Finance provider initial)
- **Frontend**: React, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand, TradingView Lightweight Charts
- **Scheduler**: APScheduler with market close awareness (IST/NSE)
- **Tooling**: Ruff, Pytest, Docker Compose, GitHub Actions

---

## Quickstart

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 20+

### 2. Local Infrastructure
```bash
# Start PostgreSQL & Redis
docker-compose up -d postgres redis
```

### 3. Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pytest
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## Directory Structure

```text
Arbiter/
├── backend/                  # FastAPI & Quant Compute Engine
│   ├── app/
│   │   ├── api/v1/          # REST endpoints
│   │   ├── core/            # Database, settings, telemetry
│   │   ├── data/            # Ingestion, validation, Parquet storage
│   │   ├── quant/           # Indicators, backtest, risk models
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic validation schemas
│   │   └── jobs/            # Scheduled ingestion tasks
│   └── tests/               # Test suites
├── frontend/                 # React quantitative terminal
├── data/
│   ├── raw/                 # Raw provider payloads
│   ├── normalized/          # Parquet historical OHLCV lakehouse
│   ├── factors/             # Fama-French and benchmark factor series
│   └── quarantine/          # Rejected tick data
├── infrastructure/           # Docker Compose, DB migrations, Monitoring
└── docs/                     # Technical specifications & methodologies
```
