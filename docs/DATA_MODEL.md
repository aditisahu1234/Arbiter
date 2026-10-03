# Arbiter Data Model

## Core Entities

### Asset
- `id`: Primary key
- `symbol`: NSE symbol (e.g., RELIANCE)
- `name`: Company name
- `exchange`: Exchange code (NSE/BSE)
- `sector`: Industry sector
- `industry`: Sub-industry
- `provider_symbol`: Yahoo Finance symbol (e.g., RELIANCE.NS)
- `active`: Whether asset is currently tradable
- `created_at`, `updated_at`

### Universe
- `id`: Primary key
- `name`: Unique identifier (e.g., NIFTY50)
- `display_name`: Human-readable name
- `description`: Universe description
- `is_active`: Whether universe is active
- `member_count`: Number of constituents

### UniverseMember
- `id`: Primary key
- `universe_id`: Foreign key to Universe
- `asset_id`: Foreign key to Asset
- `weight`: Portfolio weight (optional)
- `added_at`: Membership timestamp

### JobRun
- `id`: Primary key
- `job_id`: Unique job identifier
- `job_type`: Job category (daily_ingestion, etc.)
- `status`: PENDING, RUNNING, COMPLETED, FAILED
- `started_at`, `completed_at`
- `assets_requested`, `assets_updated`, `assets_failed`
- `metadata`: JSON payload with results

## Data Storage

### Parquet Lakehouse
- **Location**: `data/normalized/{symbol}.parquet`
- **Schema**:
  - asset_id: INT64
  - symbol: STRING
  - timestamp: TIMESTAMP
  - open, high, low, close: FLOAT64
  - adjusted_close: FLOAT64
  - volume: INT64
  - source: STRING
  - ingested_at: TIMESTAMP

### Raw Data
- **Location**: `data/raw/yahoo/{date}/{symbol}.json`
- **Format**: Raw Yahoo Finance API response
- **Purpose**: Data provenance and audit trail

### Quarantine
- **Location**: `data/quarantine/{symbol}_{timestamp}.csv`
- **Purpose**: Rejected records with error reasons

### Factors
- **Location**: `data/factors/`
- **Purpose**: Fama-French factors (SMB, HML) when available
