import logging
import json
from typing import Any
import redis.asyncio as aioredis
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis: aioredis.Redis | None = None

DASHBOARD_CACHE_KEY = "ims:dashboard:incidents"
CACHE_TTL = 30  # seconds


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def init_redis():
    global _redis
    _redis = await aioredis.from_url(
        settings.redis_url, encoding="utf-8", decode_responses=True
    )
    await _redis.ping()
    logger.info("Redis ready")


async def close_redis():
    if _redis:
        await _redis.aclose()


def get_redis() -> aioredis.Redis:
    return _redis


async def get_redis_status() -> bool:
    try:
        return await _redis.ping()
    except Exception:
        return False


# ── Cache helpers ─────────────────────────────────────────────────────────────

async def cache_set(key: str, value: Any, ttl: int = CACHE_TTL) -> None:
    await _redis.setex(key, ttl, json.dumps(value, default=str))


async def cache_get(key: str) -> Any | None:
    raw = await _redis.get(key)
    return json.loads(raw) if raw else None


async def cache_delete(key: str) -> None:
    await _redis.delete(key)


async def cache_invalidate_dashboard() -> None:
    """Call this whenever a work item is created or its status changes."""
    await cache_delete(DASHBOARD_CACHE_KEY)
