from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from pydantic import Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BridgeSettings(BaseSettings):
    """Configuration surface for the Chorus Bridge service."""

    instance_id: str = Field(default="bridge-local")
    database_url: str = Field(
        default="postgresql+psycopg://chorus:chorus@localhost:5432/chorus_bridge",
        description="SQLAlchemy-compatible database URL.",
    )
    trust_store_path: Optional[Path] = Field(
        default=None,
        description="Path to JSON trust store mapping instance IDs to Ed25519 public keys.",
    )
    conductor_mode: str = Field(
        default="memory",
        description="Conductor integration mode: 'memory' or 'http'.",
        pattern="^(memory|http)$",
    )
    conductor_base_url: Optional[HttpUrl] = Field(
        default=None,
        description="Base URL for Conductor HTTP API when using HTTP mode.",
    )
    replay_cache_ttl_seconds: int = Field(default=86_400, ge=60)
    idempotency_ttl_seconds: int = Field(default=3_600, ge=60)
    export_genesis_timestamp: int = Field(default=1_729_670_400)  # Oct 23, 2024
    activitypub_actor_domain: str = Field(default="bridge.local")
    activitypub_targets: tuple[str, ...] = Field(default=())

    model_config = SettingsConfigDict(
        env_prefix="bridge_",
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _validate_conductor(self) -> "BridgeSettings":
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
