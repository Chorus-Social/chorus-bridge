from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

from chorus_bridge.db import DatabaseSessionManager
from chorus_bridge.services.conductor import ConductorClient

router = APIRouter(prefix="/health", tags=["health"])


def get_db_manager(request) -> DatabaseSessionManager:
    """Dependency to get the database manager from the FastAPI app state."""
    return request.app.state.db_manager


def get_conductor(request) -> ConductorClient:
    """Dependency to get the conductor client from the FastAPI app state."""
    return request.app.state.conductor


@router.get("/live")
async def liveness_check():
    """Liveness probe - indicates if the service is running."""
    return {"status": "alive", "service": "chorus-bridge"}


@router.get("/ready")
async def readiness_check(
    db_manager: DatabaseSessionManager = Depends(get_db_manager),
    conductor: ConductorClient = Depends(get_conductor),
):
    """Readiness probe - indicates if the service is ready to accept requests."""
    checks = {
        "database": False,
        "conductor": False,
    }

    # Check database connectivity
    try:
        async with db_manager.session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database check failed: {str(e)}",
        )

    # Check conductor connectivity
    try:
        # Try to get a day proof (this will fail gracefully if conductor is down)
        await conductor.get_day_proof(1)
        checks["conductor"] = True
    except Exception:
        # Conductor might be down, but that's not necessarily a failure
        # for readiness (depending on configuration)
        pass

    if not checks["database"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready: database unavailable",
        )

    return {"status": "ready", "service": "chorus-bridge", "checks": checks}
