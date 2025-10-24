"""
Connection pool manager for Conductor clients to optimize resource usage.
"""

import asyncio
import logging
import time
from typing import List, Optional, Dict, Any

from chorus_bridge.services.conductor import (
    ConductorClient,
    ConductorEvent,
    ConductorReceipt,
)
from chorus_bridge.schemas import DayProofResponse

logger = logging.getLogger(__name__)


class ConductorConnectionPool:
    """Manages a pool of Conductor connections for load balancing and fault tolerance."""

    def __init__(
        self,
        clients: List[ConductorClient],
        health_check_interval: float = 30.0,
        max_retries: int = 3,
    ):
        """Initialize the connection pool.

        Args:
            clients: List of ConductorClient instances.
            health_check_interval: Interval between health checks in seconds.
            max_retries: Maximum number of retries when all clients fail.
        """
        self.clients = clients
        self.health_check_interval = health_check_interval
        self.max_retries = max_retries

        # Track client health and usage
        self._client_health: Dict[int, bool] = {i: True for i in range(len(clients))}
        self._client_last_check: Dict[int, float] = {
            i: 0.0 for i in range(len(clients))
        }
        self._client_usage_count: Dict[int, int] = {i: 0 for i in range(len(clients))}
        self._round_robin_index = 0
        self._lock = asyncio.Lock()

        # Start background health checking
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self):
        """Background task to periodically check client health."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._check_all_clients_health()
            except Exception as e:
                logger.error("Error in health check loop: %s", e)

    async def _check_all_clients_health(self):
        """Check health of all clients."""
        current_time = time.time()

        for i, client in enumerate(self.clients):
            try:
                # Only check if enough time has passed
                if (
                    current_time - self._client_last_check[i]
                    < self.health_check_interval
                ):
                    continue

                is_healthy = await client.health_check()
                self._client_health[i] = is_healthy
                self._client_last_check[i] = current_time

                if is_healthy:
                    logger.debug("Client %s is healthy", i)
                else:
                    logger.warning("Client %s is unhealthy", i)

            except Exception as e:
                logger.warning("Health check failed for client %s: %s", i, e)
                self._client_health[i] = False
                self._client_last_check[i] = current_time

    async def _get_healthy_client(self) -> Optional[ConductorClient]:
        """Get a healthy client using round-robin with health awareness."""
        async with self._lock:
            healthy_clients = [
                (i, client)
                for i, client in enumerate(self.clients)
                if self._client_health[i]
            ]

            if not healthy_clients:
                return None

            # Use round-robin among healthy clients
            client_index, client = healthy_clients[
                self._round_robin_index % len(healthy_clients)
            ]
            self._round_robin_index += 1
            self._client_usage_count[client_index] += 1

            return client

    async def get_day_proof(self, day_number: int) -> Optional[DayProofResponse]:
        """Get day proof using the healthiest available client."""
        for attempt in range(self.max_retries):
            client = await self._get_healthy_client()
            if client is None:
                logger.error("No healthy clients available")
                return None

            try:
                result = await client.get_day_proof(day_number)
                return result
            except Exception as e:
                logger.warning(
                    "Client failed to get day proof (attempt %s): %s", attempt + 1, e
                )
                # Mark this client as unhealthy for a short time
                client_index = self.clients.index(client)
                self._client_health[client_index] = False

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.1 * (2**attempt))  # Exponential backoff

        logger.error("All clients failed to get day proof")
        return None

    async def submit_event(self, event: ConductorEvent) -> ConductorReceipt:
        """Submit event using the healthiest available client."""
        for attempt in range(self.max_retries):
            client = await self._get_healthy_client()
            if client is None:
                raise Exception("No healthy clients available")

            try:
                result = await client.submit_event(event)
                return result
            except Exception as e:
                logger.warning(
                    "Client failed to submit event (attempt %s): %s", attempt + 1, e
                )
                # Mark this client as unhealthy for a short time
                client_index = self.clients.index(client)
                self._client_health[client_index] = False

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.1 * (2**attempt))  # Exponential backoff

        raise Exception("All clients failed to submit event")

    async def submit_events_batch(
        self, events: List[ConductorEvent]
    ) -> List[ConductorReceipt]:
        """Submit events batch using the healthiest available client."""
        for attempt in range(self.max_retries):
            client = await self._get_healthy_client()
            if client is None:
                raise Exception("No healthy clients available")

            try:
                result = await client.submit_events_batch(events)
                return result
            except Exception as e:
                logger.warning(
                    "Client failed to submit events batch (attempt %s): %s",
                    attempt + 1,
                    e,
                )
                # Mark this client as unhealthy for a short time
                client_index = self.clients.index(client)
                self._client_health[client_index] = False

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.1 * (2**attempt))  # Exponential backoff

        raise Exception("All clients failed to submit events batch")

    async def health_check(self) -> bool:
        """Check if any client is healthy."""
        return any(self._client_health.values())

    async def get_pool_stats(self) -> Dict[str, Any]:
        """Get statistics about the connection pool."""
        healthy_count = sum(1 for health in self._client_health.values() if health)
        total_usage = sum(self._client_usage_count.values())

        return {
            "total_clients": len(self.clients),
            "healthy_clients": healthy_count,
            "total_usage": total_usage,
            "client_usage": dict(self._client_usage_count),
            "client_health": dict(self._client_health),
        }

    async def aclose(self) -> None:
        """Close all clients in the pool."""
        # Cancel health check task
        if hasattr(self, "_health_check_task"):
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all clients
        for client in self.clients:
            try:
                await client.aclose()
            except Exception as e:
                logger.warning("Error closing client: %s", e)

        logger.info("Connection pool closed")


class ConductorLoadBalancer:
    """Load balancer for multiple Conductor endpoints."""

    def __init__(self, endpoints: List[str], client_factory, **client_kwargs):
        """Initialize the load balancer.

        Args:
            endpoints: List of Conductor endpoint URLs.
            client_factory: Factory function to create client instances.
            **client_kwargs: Additional arguments for client creation.
        """
        self.endpoints = endpoints
        self.client_factory = client_factory
        self.client_kwargs = client_kwargs

        # Create clients for each endpoint
        self.clients = [
            client_factory(endpoint, **client_kwargs) for endpoint in endpoints
        ]

        # Create connection pool
        self.pool = ConductorConnectionPool(self.clients)

    async def get_day_proof(self, day_number: int) -> Optional[DayProofResponse]:
        """Get day proof with load balancing."""
        return await self.pool.get_day_proof(day_number)

    async def submit_event(self, event: ConductorEvent) -> ConductorReceipt:
        """Submit event with load balancing."""
        return await self.pool.submit_event(event)

    async def submit_events_batch(
        self, events: List[ConductorEvent]
    ) -> List[ConductorReceipt]:
        """Submit events batch with load balancing."""
        return await self.pool.submit_events_batch(events)

    async def health_check(self) -> bool:
        """Check if any endpoint is healthy."""
        return await self.pool.health_check()

    async def get_stats(self) -> Dict[str, Any]:
        """Get load balancer statistics."""
        pool_stats = await self.pool.get_pool_stats()
        return {"endpoints": self.endpoints, "pool_stats": pool_stats}

    async def aclose(self) -> None:
        """Close the load balancer and all connections."""
        await self.pool.aclose()
