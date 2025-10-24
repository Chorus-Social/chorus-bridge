from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Tuple

from pydantic import Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BridgeSettings(BaseSettings):
    """Configuration surface for the Chorus Bridge service."""

    instance_id: str = Field(
        default="bridge-local"
    )  # IMPORTANT: Provide a unique instance ID for production
    database_url: str = Field(
        default="postgresql+psycopg://user:password@host:port/database",  # IMPORTANT: Change this to a secure, production-grade database URL
        description="SQLAlchemy-compatible database URL.",
    )
    trust_store_path: Optional[Path] = Field(
        default=None,  # IMPORTANT: Configure this path in production for secure federation
        description="Path to JSON trust store mapping instance IDs to Ed25519 public keys.",
    )
    conductor_mode: str = Field(
        default="http",  # Production should use 'http' mode
        description="Conductor integration mode: 'memory' or 'http'.",
        pattern="^(memory|http)$",
    )
    conductor_protocol: str = Field(
        default="grpc",
        description="Conductor integration protocol: 'http' or 'grpc'.",
        pattern="^(http|grpc)$",
    )
    conductor_base_url: Optional[HttpUrl] = Field(
        default=None,  # IMPORTANT: Must be configured for production when conductor_mode='http'
        description="Base URL for Conductor HTTP API when using HTTP mode.",
    )
    conductor_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retries for conductor requests.",
    )
    conductor_retry_delay: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Base delay between conductor request retries in seconds.",
    )
    conductor_timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Timeout for conductor requests in seconds.",
    )
    conductor_circuit_breaker_threshold: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of failures before opening circuit breaker.",
    )
    conductor_circuit_breaker_timeout: float = Field(
        default=60.0,
        ge=10.0,
        le=600.0,
        description="Time to wait before attempting recovery in seconds.",
    )
    conductor_cache_ttl: float = Field(
        default=300.0,
        ge=60.0,
        le=3600.0,
        description="Cache TTL for conductor responses in seconds.",
    )
    conductor_cache_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Maximum number of entries in conductor cache.",
    )
    replay_cache_ttl_seconds: int = Field(default=86_400, ge=60)
    idempotency_ttl_seconds: int = Field(default=3_600, ge=60)
    export_genesis_timestamp: int = Field(
        default=1_729_670_400
    )  # Oct 23, 2024 - Review this timestamp for production deployment
    activitypub_actor_domain: str = Field(
        default="your.activitypub.domain"
    )  # IMPORTANT: Change this to your production ActivityPub domain
    activitypub_targets: tuple[str, ...] = Field(
        default=()
    )  # IMPORTANT: Configure ActivityPub target instances in production

    federation_rate_limits_default_rps: int = Field(default=10, ge=1)
    federation_rate_limits_burst: int = Field(default=50, ge=1)

    activitypub_worker_interval_seconds: int = Field(default=60, ge=1)
    activitypub_max_retries: int = Field(default=5, ge=0)
    activitypub_retry_delay_seconds: int = Field(default=60, ge=1)

    prometheus_port: int = Field(default=9090, ge=1024, le=65535)

    jwt_enforcement_enabled: bool = Field(default=False)
    jwt_public_key: Optional[str] = Field(
        default=None, description="Public key for verifying JWTs from Stage instances."
    )
    bridge_private_key: Optional[str] = Field(
        default=None,
        description="Hex-encoded Ed25519 private key for the Bridge instance, used for signing outbound federation envelopes.",
    )
    bridge_jwt_signing_key: Optional[str] = Field(
        default=None,
        description="Hex-encoded Ed25519 private key for the Bridge instance, used for signing JWTs for outbound authentication to Stages.",
    )

    libp2p_bootstrap_peers: Tuple[str, ...] = Field(
        default=(), description="List of libp2p multiaddresses for bootstrap peers."
    )
    libp2p_listen_address: Optional[str] = Field(
        default="/ip4/0.0.0.0/tcp/0",
        description="Libp2p listen address for the Bridge.",
    )

    # Feature Flags
    federation_post_announce_enabled: bool = Field(default=True)
    federation_user_registration_enabled: bool = Field(default=False)
    federation_moderation_events_enabled: bool = Field(default=True)
    federation_day_proof_consumption_enabled: bool = Field(default=True)
    federation_community_creation_enabled: bool = Field(default=True)
    federation_user_update_enabled: bool = Field(default=True)
    federation_community_update_enabled: bool = Field(default=True)
    federation_community_membership_update_enabled: bool = Field(default=True)

    outbound_worker_interval_seconds: int = Field(
        default=1, ge=1
    )  # Aim for low latency
    outbound_max_retries: int = Field(default=5, ge=0)
    outbound_retry_delay_seconds: int = Field(default=60, ge=1)
    federation_target_stages: tuple[str, ...] = Field(
        default=(),
        description="List of base URLs for target Stage instances to push data to.",
    )

    model_config = SettingsConfigDict(
        env_prefix="bridge_",
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _validate_conductor(self) -> "BridgeSettings":
        """Validates Conductor-related settings based on the chosen mode."""
        if self.conductor_mode == "http" and self.conductor_base_url is None:
            raise ValueError("conductor_base_url required when conductor_mode='http'")
        return self

    def load_trust_store(self) -> Dict[str, str]:
        """Load trust store mapping from instance ids to hex-encoded public keys."""
        if not self.trust_store_path:
            return {}
        path = Path(self.trust_store_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"trust store file not found: {path}")
        with path.open("r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)
        instances = data.get("instances")
        if not isinstance(instances, dict):
            raise ValueError("trust store must contain an 'instances' object")
        return {str(k): str(v) for k, v in instances.items()}
