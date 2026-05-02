import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.core.config import get_settings
from app.core.metrics import http_requests_total, http_request_duration_seconds

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────
    from app.db.postgres import init_db
    from app.db.mongo import init_mongo
    from app.db.redis_client import init_redis
    from app.workers.signal_processor import start_workers

    await init_db()
    await init_mongo()
    await init_redis()
    await start_workers()

    yield

    # ── Shutdown ──────────────────────────────────────────────
    from app.workers.signal_processor import stop_workers
    from app.db.postgres import close_db
    from app.db.mongo import close_mongo
    from app.db.redis_client import close_redis

    await stop_workers()
    await close_db()
    await close_mongo()
    await close_redis()


app = FastAPI(
    title="Incident Management System",
    version="1.0.0",
    description="Mission-critical IMS — signal ingestion, workflow engine, real-time dashboard",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── HTTP metrics middleware ───────────────────────────────────────────────────
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response: Response = await call_next(request)
    duration = time.time() - start
    endpoint = request.url.path
    http_requests_total.labels(
        method=request.method, endpoint=endpoint, status_code=response.status_code
    ).inc()
    http_request_duration_seconds.labels(method=request.method, endpoint=endpoint).observe(duration)
    return response


# ── Prometheus metrics (no auth — scraped by Prometheus server) ───────────────
app.mount("/metrics", make_asgi_app())

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api import health, auth, signals, incidents, rca, websocket  # noqa: E402

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(signals.router)
app.include_router(incidents.router)
app.include_router(rca.router)
app.include_router(websocket.router)


@app.get("/")
async def root():
    return {"service": "IMS", "version": "1.0.0", "docs": "/docs"}
