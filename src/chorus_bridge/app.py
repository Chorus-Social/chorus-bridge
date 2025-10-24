from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from fastapi import FastAPI

from chorus_bridge.api import api_router
from chorus_bridge.core import BridgeSettings
from chorus_bridge.core.trust import TrustStore
from chorus_bridge.db import DatabaseSessionManager
from chorus_bridge.db.repository import BridgeRepository
from chorus_bridge.services.bridge import BridgeService
from chorus_bridge.services.conductor import HttpConductorClient
from chorus_bridge.core.rate_limiter import RateLimiter
from chorus_bridge.core.jwt_auth import JWTAuth
from chorus_bridge.services.activitypub import ActivityPubTranslator
from chorus_bridge.services.activitypub_worker import ActivityPubDeliveryWorker
from chorus_bridge.services.outbound_federation_worker import OutboundFederationWorker

# from chorus_bridge.services.libp2p_bridge import Libp2pBridgeClient
from chorus_bridge.proto import federation_pb2 as pb2
import logging

import asyncio
from prometheus_client import start_http_server, Gauge

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_settings() -> BridgeSettings:
    """Loads Bridge settings, caching the result."""
    return BridgeSettings()


def create_app(settings: Optional[BridgeSettings] = None) -> FastAPI:
    """Creates and configures the FastAPI application for Chorus Bridge.

    Args:
        settings: Optional BridgeSettings instance. If None, settings are loaded.

    Returns:
        A configured FastAPI application instance.
    """
    settings = settings or _load_settings()

    db_manager = DatabaseSessionManager(settings.database_url)
    db_manager.create_all()  # IMPORTANT: In production, use a dedicated migration tool (e.g., Alembic) for schema management.

    trust_mapping = settings.load_trust_store() if settings.trust_store_path else {}
    trust_store = TrustStore.from_hex_mapping(trust_mapping)
    repository = BridgeRepository(db_manager)

    from chorus_bridge.services.conductor import (
        GrpcConductorClient,
        InMemoryConductorClient,
    )
    from chorus_bridge.services.conductor_cache import (
        ConductorCache,
        CachedConductorClient,
    )

    conductor: Any  # ConductorClient or CachedConductorClient
    if settings.conductor_mode == "http":
        assert settings.conductor_base_url is not None, (
            "conductor_base_url must be set when conductor_mode is 'http'"
        )

        # Create base client
        if settings.conductor_protocol == "http":
            base_client = HttpConductorClient(
                str(settings.conductor_base_url),
                max_retries=settings.conductor_max_retries,
                retry_delay=settings.conductor_retry_delay,
                timeout=settings.conductor_timeout,
                circuit_breaker_threshold=settings.conductor_circuit_breaker_threshold,
                circuit_breaker_timeout=settings.conductor_circuit_breaker_timeout,
            )
        elif settings.conductor_protocol == "grpc":
            # Create dummy metrics for gRPC client initialization
            from prometheus_client import Counter, Histogram
            dummy_requests_total = Counter(
                "bridge_conductor_requests_total_dummy",
                "Dummy counter for gRPC client initialization",
                ["method", "status"]
            )
            dummy_latency = Histogram(
                "bridge_conductor_latency_seconds_dummy",
                "Dummy histogram for gRPC client initialization",
                ["method"]
            )
            
            base_client = GrpcConductorClient(
                str(settings.conductor_base_url),
                dummy_requests_total,
                dummy_latency,
                max_retries=settings.conductor_max_retries,
                retry_delay=settings.conductor_retry_delay,
                connection_timeout=settings.conductor_timeout,
                circuit_breaker_threshold=settings.conductor_circuit_breaker_threshold,
                circuit_breaker_timeout=settings.conductor_circuit_breaker_timeout,
            )
        else:
            raise NotImplementedError(
                f"Conductor protocol '{settings.conductor_protocol}' not yet implemented."
            )

        # Add caching layer
        cache = ConductorCache(
            default_ttl=settings.conductor_cache_ttl,
            max_size=settings.conductor_cache_size,
        )
        conductor = CachedConductorClient(base_client, cache)

    else:
        conductor = InMemoryConductorClient()

    translator = ActivityPubTranslator(
        genesis_timestamp=settings.export_genesis_timestamp,
        actor_domain=settings.activitypub_actor_domain,
    )

    # libp2p_message_queue = asyncio.Queue() # Queue for messages from libp2p
    # libp2p_client = Libp2pBridgeClient(
    #     settings,
    #     libp2p_message_queue,
    #     app.state.libp2p_messages_published_total,
    #     app.state.libp2p_messages_received_total,
    # )

    service = BridgeService(
        settings=settings,
        repository=repository,
        trust_store=trust_store,
        conductor=conductor,
        activitypub_translator=translator,
        # libp2p_client=libp2p_client,
    )

    activitypub_worker = ActivityPubDeliveryWorker(
        settings=settings,
        repository=repository,
        translator=translator,
    )

    outbound_federation_worker = OutboundFederationWorker(
        settings=settings,
        repository=repository,
    )

    app = FastAPI(title="Chorus Bridge", version="0.2.0")
    app.state.settings = settings
    app.state.db_manager = db_manager
    app.state.bridge_service = service
    app.state.conductor = conductor
    app.state.activitypub_worker = activitypub_worker
    app.state.outbound_federation_worker = outbound_federation_worker
    # app.state.libp2p_client = libp2p_client

    # Initialize Prometheus metrics (skip in test mode)
    if settings.prometheus_port > 0:
        app.state.bridge_events_received_total = Counter(
            "bridge_events_received_total",
            "Total number of federation events received",
            ["event_type", "source_instance"],
        )
        app.state.bridge_events_processed_total = Counter(
            "bridge_events_processed_total",
            "Total number of federation events processed",
            ["event_type", "status"],
        )
        app.state.bridge_events_failed_total = Counter(
            "bridge_events_failed_total",
            "Total number of failed federation events",
            ["error_type"],
        )
        app.state.bridge_conductor_requests_total = Counter(
            "bridge_conductor_requests_total",
            "Total number of requests to conductor",
            ["method", "status"],
        )
        app.state.bridge_conductor_latency = Histogram(
            "bridge_conductor_latency_seconds",
            "Latency of conductor requests",
            ["method"],
        )
        app.state.bridge_conductor_cache_hits = Counter(
            "bridge_conductor_cache_hits_total",
            "Total number of cache hits for conductor requests",
            ["cache_type"],
        )
        app.state.bridge_conductor_circuit_breaker_state = Gauge(
            "bridge_conductor_circuit_breaker_state",
            "Circuit breaker state (0=CLOSED, 1=OPEN, 2=HALF_OPEN)",
            ["client_type"],
        )
        app.state.bridge_conductor_connection_pool_size = Gauge(
            "bridge_conductor_connection_pool_size",
            "Number of connections in the conductor pool",
            ["pool_type"],
        )
        app.state.bridge_peer_count = Gauge(
            "bridge_peer_count", "Number of connected peers"
        )
        app.state.bridge_blacklist_size = Gauge(
            "bridge_blacklist_size", "Number of blacklisted instances"
        )

        # Start Prometheus metrics server
        start_http_server(settings.prometheus_port)
    else:
        # Create dummy metrics for testing
        app.state.bridge_events_received_total = None
        app.state.bridge_events_processed_total = None
        app.state.bridge_events_failed_total = None
        app.state.bridge_conductor_requests_total = None
        app.state.bridge_conductor_latency = None
        app.state.bridge_peer_count = None
        app.state.bridge_blacklist_size = None

    app.state.rate_limiter_instance = RateLimiter(settings=settings)

    def get_rate_limiter_dependency() -> RateLimiter:
        return app.state.rate_limiter_instance

    app.dependency_overrides[RateLimiter] = get_rate_limiter_dependency

    app.state.jwt_auth_instance = JWTAuth(settings=settings, repository=repository)

    def get_jwt_auth_dependency() -> JWTAuth:
        return app.state.jwt_auth_instance

    app.dependency_overrides[JWTAuth] = get_jwt_auth_dependency

    # Include API router
    app.include_router(api_router)

    return app


async def process_libp2p_messages(
    bridge_service: BridgeService, message_queue: asyncio.Queue
):
    """Background task to process messages received from libp2p."""
    logger.info("Libp2p message processor started.")
    while True:
        message = await message_queue.get()
        if message:
            try:
                # Assuming message.data is a serialized FederationEnvelope
                envelope = pb2.FederationEnvelope.FromString(message.data)
                logger.info(
                    "Processing libp2p message from %s with type %s",
                    envelope.sender_instance,
                    envelope.message_type,
                )
                # Pass to bridge_service for full processing (validation, replay, dispatch)
                # Note: This path bypasses HTTP headers like idempotency-key, X-Chorus-Instance-Id
                # The BridgeService.process_federation_envelope needs to be adapted for this.
                await bridge_service.process_federation_envelope(
                    envelope=envelope,
                    idempotency_key=None,  # No idempotency key for P2P messages
                    stage_instance=envelope.sender_instance,  # Sender instance from envelope
                )
            except Exception as e:
                logger.error("Error processing libp2p message: %s", e)
        await asyncio.sleep(0.01)  # Yield control


__all__ = ["create_app"]
