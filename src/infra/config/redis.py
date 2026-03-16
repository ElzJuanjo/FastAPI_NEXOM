"""
Cliente Redis compartido para rate limiting, caché y sesiones.
"""

from redis.asyncio import from_url as redis_from_url

from .database import settings

redis_client = redis_from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)


async def check_redis_health() -> bool:
    """Verifica que Redis esté disponible."""
    try:
        return await redis_client.ping()
    except Exception:
        return False