"""
Conductor response caching for improved efficiency and reduced load.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

from chorus_bridge.schemas import DayProofResponse

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached entry with metadata."""

    value: Any
    timestamp: float
    ttl: float


class ConductorCache:
    """Intelligent caching layer for Conductor responses."""

    def __init__(self, default_ttl: float = 300.0, max_size: int = 1000):
        """Initialize the cache.

        Args:
            default_ttl: Default time-to-live for cache entries in seconds.
            max_size: Maximum number of entries in the cache.
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        async with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            current_time = time.time()

            # Check if entry has expired
            if current_time - entry.timestamp > entry.ttl:
                del self._cache[key]
                if key in self._access_times:
                    del self._access_times[key]
                return None

            # Update access time for LRU
            self._access_times[key] = current_time
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set a value in the cache."""
        async with self._lock:
            current_time = time.time()
            ttl = ttl or self.default_ttl

            # Remove oldest entries if cache is full
            if len(self._cache) >= self.max_size:
                await self._evict_oldest()

            self._cache[key] = CacheEntry(value=value, timestamp=current_time, ttl=ttl)
            self._access_times[key] = current_time

    async def _evict_oldest(self) -> None:
        """Evict the least recently used entry."""
        if not self._access_times:
            return

        oldest_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        del self._cache[oldest_key]
        del self._access_times[oldest_key]

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._access_times.clear()

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            current_time = time.time()
            active_entries = sum(
                1
                for entry in self._cache.values()
                if current_time - entry.timestamp <= entry.ttl
            )

            return {
                "total_entries": len(self._cache),
                "active_entries": active_entries,
                "max_size": self.max_size,
                "default_ttl": self.default_ttl,
            }


class CachedConductorClient:
    """Wrapper that adds caching to any ConductorClient."""

    def __init__(self, client, cache: Optional[ConductorCache] = None):
        """Initialize the cached client.

        Args:
            client: The underlying ConductorClient.
            cache: Optional cache instance. If None, creates a default cache.
        """
        self.client = client
        self.cache = cache or ConductorCache()

    async def get_day_proof(self, day_number: int) -> Optional[DayProofResponse]:
        """Get day proof with caching."""
        cache_key = f"day_proof:{day_number}"

        # Try to get from cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result is not None:
            logger.debug("Cache hit for day proof %s", day_number)
            return cached_result

        # Get from conductor and cache result
        result = await self.client.get_day_proof(day_number)
        if result is not None:
            # Cache for 1 hour (day proofs don't change frequently)
            await self.cache.set(cache_key, result, ttl=3600.0)
            logger.debug("Cached day proof %s", day_number)

        return result

    async def submit_event(self, event) -> Any:
        """Submit event (no caching for events)."""
        return await self.client.submit_event(event)

    async def submit_events_batch(self, events) -> Any:
        """Submit events batch (no caching for events)."""
        return await self.client.submit_events_batch(events)

    async def health_check(self) -> bool:
        """Health check (no caching)."""
        return await self.client.health_check()

    async def aclose(self) -> None:
        """Close the underlying client."""
        await self.client.aclose()
