from fastapi import APIRouter
from app.db.postgres import get_pg_status
from app.db.mongo import get_mongo_status
from app.db.redis_client import get_redis_status
from app.workers.signal_processor import signal_queue

router = APIRouter(tags=["observability"])


@router.get("/health")
async def health():
    pg = await get_pg_status()
    mongo = await get_mongo_status()
    redis = await get_redis_status()
    healthy = all([pg, mongo, redis])
    return {
        "status": "healthy" if healthy else "degraded",
        "components": {
            "postgres": "up" if pg else "down",
            "mongo":    "up" if mongo else "down",
            "redis":    "up" if redis else "down",
        },
        "queue_depth": signal_queue.qsize(),
    }
