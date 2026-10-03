# Arbiter Deployment Guide

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker (optional, for PostgreSQL/Redis)

### Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Seed database
python ../scripts/seed_universes.py

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Access
- Backend: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Frontend: http://localhost:5173

## Production Deployment

### Docker Compose
```bash
docker-compose -f infrastructure/docker/docker-compose.prod.yml up -d
```

### Environment Variables
Create `.env` file:
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/arbiter_db
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key
```

### Health Checks
```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

## Monitoring

### Prometheus
Access metrics at `/metrics` endpoint.

### Grafana
Configure Prometheus as data source and import dashboards from `infrastructure/monitoring/grafana/`.

## Backup
```bash
# Backup PostgreSQL
pg_dump -U arbiter_user arbiter_db > backup.sql

# Backup Parquet data
tar czf data-backup.tar.gz data/normalized/ data/raw/
```

## Scaling
- Backend: Horizontal scaling with multiple uvicorn workers
- Database: PostgreSQL read replicas for analytical queries
- Cache: Redis cluster for distributed caching
