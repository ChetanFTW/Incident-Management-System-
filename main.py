from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise DB connections, start background workers
    from app.db.postgres import init_db
    from app.db.mongo import init_mongo
    from app.db.redis_client import init_redis
    from app.workers.signal_processor import start_workers

    await init_db()
    await init_mongo()
    await init_redis()
    await start_workers()

    yield

    # Shutdown: flush queues, close connections
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
    description="Mission-critical IMS with real-time signal processing",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics endpoint (mounted separately — no auth required for scraping)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Routers (registered in later PRs)
from app.api import health  # noqa: E402
app.include_router(health.router)


@app.get("/")
async def root():
    return {"service": "IMS", "status": "running", "version": "1.0.0"}
