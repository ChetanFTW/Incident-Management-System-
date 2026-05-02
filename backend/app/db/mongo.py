import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def init_mongo():
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongo_url)
    _db = _client[settings.mongo_db]
    # Verify connection
    await _client.admin.command("ping")
    # Indexes for fast signal queries
    await _db.signals.create_index([("work_item_id", 1)])
    await _db.signals.create_index([("component_id", 1), ("received_at", -1)])
    await _db.signals.create_index([("received_at", -1)])
    logger.info("MongoDB ready")


async def close_mongo():
    if _client:
        _client.close()


def get_db() -> AsyncIOMotorDatabase:
    return _db


async def get_mongo_status() -> bool:
    try:
        await _client.admin.command("ping")
        return True
    except Exception:
        return False
