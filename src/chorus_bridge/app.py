from __future__ import annotations

from functools import lru_cache
from typing import Optional

from fastapi import FastAPI

from chorus_bridge.api import api_router
from chorus_bridge.core import BridgeSettings
from chorus_bridge.core.trust import TrustStore
from chorus_bridge.db import DatabaseSessionManager
from chorus_bridge.db.repository import BridgeRepository
from chorus_bridge.services.bridge import BridgeService
from chorus_bridge.services.conductor import HttpConductorClient, InMemoryConductorClient, MockConductor


@lru_cache(maxsize=1)
def _load_settings() -> BridgeSettings:
    return BridgeSettings()


def create_app(settings: Optional[BridgeSettings] = None) -> FastAPI:
    settings = settings or _load_settings()

    db_manager = DatabaseSessionManager(settings.database_url)
    db_manager.create_all()

    trust_mapping = settings.load_trust_store() if settings.trust_store_path else {}
    trust_store = TrustStore.from_hex_mapping(trust_mapping)
    repository = BridgeRepository(db_manager)

    if settings.conductor_mode == "http":
        assert settings.conductor_base_url is not None
        conductor = HttpConductorClient(str(settings.conductor_base_url))
    else:
        # Instantiate the Conductor class and pass it to InMemoryConductorClient
        # For now, we'll use dummy validator_id and validators
        conductor_instance = MockConductor(validator_id="bridge_validator_1", validators=["bridge_validator_1", "bridge_validator_2", "bridge_validator_3", "bridge_validator_4"])
        conductor = InMemoryConductorClient(conductor_instance)

    service = BridgeService(
        settings=settings,
        repository=repository,
        trust_store=trust_store,
        conductor=conductor,
    )

    app = FastAPI(title="Chorus Bridge", version="0.2.0")
    app.state.settings = settings
    app.state.db_manager = db_manager
    app.state.bridge_service = service
    app.state.conductor = conductor

    app.include_router(api_router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "instance_id": settings.instance_id}

    @app.on_event("shutdown")
    async def shutdown_event() -> None:  # pragma: no cover - runtime hook
        db_manager.dispose()
        if isinstance(conductor, HttpConductorClient):
            await conductor.aclose()

    return app


__all__ = ["create_app"]
