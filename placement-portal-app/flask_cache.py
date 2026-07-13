"""
Shared Flask-Caching instance, Redis-backed. Imported by app.py (for
cache.init_app) and by any route module that needs to cache a response
or invalidate the cache after a write.

Uses Redis DB index 1, separate from Celery's broker/result-backend
(DB index 0), so `redis-cli -n 1 keys "*"` shows only cache entries
during verification/debugging.
"""
from flask_caching import Cache

cache = Cache(
    config={
        "CACHE_TYPE": "RedisCache",
        "CACHE_REDIS_URL": "redis://localhost:6379/1",
        "CACHE_DEFAULT_TIMEOUT": 60,
    }
)


def invalidate_cache():
    """
    Blunt but simple: clear the whole cache. Given this app's scale
    (course project, not production traffic), a targeted per-key
    invalidation scheme isn't worth the complexity — every write that
    could affect a cached listing just clears everything and lets the
    next read repopulate it.
    """
    cache.clear()

