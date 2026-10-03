# Arbiter API Documentation

## Base URL
```
http://localhost:8000/api/v1
```

## Endpoints

### Health
```
GET /health
```
Returns service status and version.

### Assets
```
GET /assets?limit=10&offset=0&sector=Financial%20Services
GET /assets/{symbol}/ohlcv?limit=100&start_date=2024-01-01&end_date=2024-12-31
```

### Universes
```
GET /universes
GET /universes/{name}/members
```

### Indicators
```
GET /indicators/sma?symbol=TCS&window=20
GET /indicators/atr?symbol=TCS&window=14&smoothing=rma
```

### Backtest
```
POST /strategies/backtest?symbol=TCS&fast_sma=10&slow_sma=50&atr_window=14&atr_mult=3.0&cost_bps=10
```

### Risk
```
GET /risk/capm?symbol=TCS&market_symbol=^NSEI&risk_free_annual=6.5
GET /risk/fama-french?symbol=TCS
```

### Market Data
```
GET /market-data/lakehouse
POST /market-data/ingest/{symbol}?years=5
POST /market-data/ingest-batch?symbols=["TCS","INFY"]&years=5
```

### Jobs
```
GET /jobs
GET /jobs/{job_id}
```

### Metrics
```
GET /metrics
```
Prometheus metrics endpoint.

## Authentication
Bearer token authentication via JWT. Include in request headers:
```
Authorization: Bearer <token>
```

## Error Responses
- `400`: Bad request (validation error)
- `401`: Unauthorized
- `404`: Resource not found
- `500`: Internal server error
