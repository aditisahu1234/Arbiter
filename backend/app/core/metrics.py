"""Prometheus metrics exporter."""
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge, generate_latest


class ArbiterMetrics:
    """Application metrics for Prometheus."""

    def __init__(self):
        self.registry = CollectorRegistry()

        # Request metrics
        self.request_count = Counter(
            'arbiter_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry,
        )

        self.request_latency = Histogram(
            'arbiter_request_latency_seconds',
            'HTTP request latency',
            ['method', 'endpoint'],
            registry=self.registry,
        )

        # Ingestion metrics
        self.ingestion_total = Counter(
            'arbiter_ingestion_total',
            'Total ingestion jobs',
            ['status'],
            registry=self.registry,
        )

        self.ingestion_assets = Counter(
            'arbiter_ingestion_assets_total',
            'Assets ingested',
            ['status'],
            registry=self.registry,
        )

        # Data metrics
        self.parquet_files = Gauge(
            'arbiter_parquet_files',
            'Number of Parquet files in lakehouse',
            registry=self.registry,
        )

        self.parquet_rows = Gauge(
            'arbiter_parquet_rows',
            'Total rows in Parquet lakehouse',
            registry=self.registry,
        )

    def record_request(self, method: str, endpoint: str, status: int, duration: float):
        self.request_count.labels(method=method, endpoint=endpoint, status=status).inc()
        self.request_latency.labels(method=method, endpoint=endpoint).observe(duration)

    def record_ingestion(self, status: str, assets: int):
        self.ingestion_total.labels(status=status).inc()
        self.ingestion_assets.labels(status=status).inc(assets)

    def update_data_metrics(self, file_count: int, row_count: int):
        self.parquet_files.set(file_count)
        self.parquet_rows.set(row_count)


metrics = ArbiterMetrics()
