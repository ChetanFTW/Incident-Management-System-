# Incident Management System (IMS)

> Mission-critical distributed incident tracking system with real-time signal ingestion, workflow engine, and observability stack.

## Quick Start

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd ims

# 2. Set up environment
cp .env.example .env

# 3. Launch everything
docker compose up --build

# 4. Open the UI
open http://localhost:3000

# 5. Check health
curl http://localhost:8000/health

# 6. View metrics (Prometheus)
open http://localhost:9090

# 7. View dashboards (Grafana)
open http://localhost:3001   # admin / admin
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend (React) | 3000 | Incident dashboard UI |
| Backend (FastAPI) | 8000 | REST API + WebSocket |
| PostgreSQL / TimescaleDB | 5432 | Work items, RCA, timeseries |
| MongoDB | 27017 | Raw signal audit log |
| Redis | 6379 | Hot-path dashboard cache |
| Prometheus | 9090 | Metrics scraping |
| Grafana | 3001 | Metrics dashboards |

## Architecture

> Full architecture diagram and design decisions documented in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — added in PR #8.

## PR History

| PR | Branch | What shipped |
|----|--------|--------------|
| #1 | `feat/scaffold` | Repo structure, Docker Compose, all services wired |
| #2 | `feat/db-models` | PG models, Mongo schema, Redis helpers, migrations |
| #3 | `feat/ingestion-engine` | Signal queue, debounce, workers, rate limiter, metrics |
| #4 | `feat/workflow-patterns` | State machine, Strategy pattern, MTTR, RCA validation |
| #5 | `feat/api-layer` | REST endpoints, JWT auth, WebSocket feed |
| #6 | `feat/frontend` | Full React UI — dashboard, detail, RCA form |
| #7 | `feat/testing-seed` | Unit tests, seed script, retry logic |
| #8 | `feat/docs-observability` | Full README, architecture docs, Grafana dashboards |

## Backpressure Handling

> Detailed in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Summary:
> - Signals land in an in-process `asyncio.Queue(maxsize=50000)` before any DB write
> - If the queue is full, the ingestion endpoint returns `HTTP 429` immediately — the DB being slow never crashes the ingestor
> - Background workers drain the queue at their own pace with retry logic

## Bonus Features

- **JWT Authentication** — all non-health endpoints require a Bearer token
- **Prometheus metrics** — `/metrics` exposes `signals_ingested_total`, `active_incidents_gauge`, `mttr_seconds_histogram`
- **Grafana dashboards** — pre-provisioned dashboards auto-load on startup
- **Auto-escalation** — P2 incidents with >500 signals/60s automatically escalate to P1
- **Incident timeline** — full state transition history per incident
