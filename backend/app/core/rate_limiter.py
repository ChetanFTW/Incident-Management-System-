"""
Token-bucket rate limiter using Redis.
- Signal ingestion: 10,000 signals/sec burst capacity
- General API: 1,000 req/min per IP
"""
import time
from fastapi import HTTPException, Request, status
from app.db.redis_client import get_redis
from app.core.config import get_settings

settings = get_settings()


async def check_signal_rate_limit(request: Request) -> None:
    """Allow up to RATE_LIMIT_SIGNALS_PER_SECOND signals per second globally."""
    redis = get_redis()
    key = "rl:signals:global"
    now = int(time.time())

    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 1)
    results = await pipe.execute()
    count = results[0]

    if count > settings.rate_limit_signals_per_second:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Signal rate limit exceeded: max {settings.rate_limit_signals_per_second}/sec",
        )


async def check_api_rate_limit(request: Request) -> None:
    """Per-IP rate limit for general API endpoints."""
    redis = get_redis()
    client_ip = request.client.host if request.client else "unknown"
    key = f"rl:api:{client_ip}:{int(time.time() // 60)}"

    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 60)
    results = await pipe.execute()
    count = results[0]

    if count > settings.rate_limit_api_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"API rate limit exceeded: max {settings.rate_limit_api_per_minute}/min",
        )
