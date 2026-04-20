"""
VenueFlow – Application-level caches.
Centralises TTL cache instances to avoid duplication across services.
"""
from __future__ import annotations
from cachetools import TTLCache

# Translation cache: 1 hour TTL, max 1024 entries
translation_cache: TTLCache = TTLCache(maxsize=1024, ttl=3600)

# Route cache: 5 minute TTL, max 256 entries  
route_cache: TTLCache = TTLCache(maxsize=256, ttl=300)

# Heatmap cache: 30 second TTL, max 32 entries
heatmap_cache: TTLCache = TTLCache(maxsize=32, ttl=30)


def get_cache_stats() -> dict[str, dict]:
    """
    Return current cache utilisation statistics.

    Returns:
        Dict mapping cache name to size and max_size.
    """
    return {
        "translation": {
            "size": len(translation_cache),
            "max_size": translation_cache.maxsize,
            "ttl_seconds": 3600,
        },
        "route": {
            "size": len(route_cache),
            "max_size": route_cache.maxsize,
            "ttl_seconds": 300,
        },
        "heatmap": {
            "size": len(heatmap_cache),
            "max_size": heatmap_cache.maxsize,
            "ttl_seconds": 30,
        },
    }
