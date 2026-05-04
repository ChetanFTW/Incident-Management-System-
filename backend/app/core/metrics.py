"""
All Prometheus metrics for the IMS backend.
Import from here — never create metrics inline in route handlers.

"""
from prometheus_client import Counter, Gauge, Histogram

# Signal ingestion
signals_ingested_total = Counter(
    "ims_signals_ingested_total",
    "Total number of signals received",
    ["component_type", "severity"],
)

signals_debounced_total = Counter(
    "ims_signals_debounced_total",
    "Signals collapsed into existing work items via debounce",
)

queue_depth_gauge = Gauge(
    "ims_queue_depth",
    "Current number of signals waiting in the async queue",
)

# Work items
active_incidents_gauge = Gauge(
    "ims_active_incidents",
    "Number of incidents not yet CLOSED",
    ["priority"],
)

incidents_created_total = Counter(
    "ims_incidents_created_total",
    "Total work items ever created",
    ["priority"],
)

incidents_closed_total = Counter(
    "ims_incidents_closed_total",
    "Total work items moved to CLOSED",
)

# MTTR
mttr_seconds_histogram = Histogram(
    "ims_mttr_seconds",
    "Mean time to repair distribution in seconds",
    buckets=[60, 300, 600, 1800, 3600, 7200, 14400, 86400],
)

# Throughput (updated every METRICS_INTERVAL_SECONDS)
throughput_gauge = Gauge(
    "ims_signals_per_second",
    "Rolling signals-per-second throughput",
)

# HTTP
http_requests_total = Counter(
    "ims_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "ims_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)
