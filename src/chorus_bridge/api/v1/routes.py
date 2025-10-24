from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from chorus_bridge.schemas import ActivityPubExportRequest, ModerationEventRequest
from chorus_bridge.services import (
    BridgeService,
    DuplicateEnvelopeError,
    DuplicateIdempotencyKeyError,
)
from chorus_bridge.core.rate_limiter import RateLimiter
from chorus_bridge.core.jwt_auth import JWTAuth
from chorus_bridge.proto import federation_pb2 as pb2


router = APIRouter(prefix="/api/bridge", tags=["bridge", "v1"])


def get_bridge_service(request: Request) -> BridgeService:
    """Dependency to get the BridgeService instance from the FastAPI app state."""
    service: BridgeService = request.app.state.bridge_service
    return service


@router.get("/day-proof/{day_number}")
async def get_day_proof(
    day_number: int,
    service: BridgeService = Depends(get_bridge_service),
):
    """Retrieves the canonical day proof for a given day number.

    Args:
        day_number: The day number for which to retrieve the proof.
        service: The BridgeService instance.

    Returns:
        The DayProofResponse containing the canonical proof.

    Raises:
        HTTPException: If day_number is negative, or if the proof is not found.
    """
    if day_number < 0:
        raise HTTPException(status_code=400, detail="day_number must be non-negative")
    proof = await service.get_day_proof(day_number)
    if not proof:
        raise HTTPException(status_code=404, detail="canonical day proof unavailable")
    return proof


@router.get("/federation/peers")
async def get_federation_peers(
    service: BridgeService = Depends(get_bridge_service),
) -> dict[str, str]:
    """Returns a list of trusted federation peers and their public keys.

    Args:
        service: The BridgeService instance.

    Returns:
        A dictionary mapping instance IDs to their hex-encoded public keys.
    """
    return service.get_trusted_peers_info()


@router.post("/federation/send", status_code=status.HTTP_202_ACCEPTED)
async def federation_send(
    request: Request,
    service: BridgeService = Depends(get_bridge_service),
    stage_instance: Optional[str] = Header(default=None, alias="X-Chorus-Instance-Id"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    rate_limit: None = Depends(RateLimiter),  # Rate limiting enforced by dependency
    jwt_auth_dep: None = Depends(JWTAuth),  # JWT auth enforced by dependency
):
    """Receives and processes a signed FederationEnvelope from a Chorus Stage instance.

    This endpoint is protected by rate limiting and JWT authentication.

    Args:
        request: The incoming FastAPI request object.
        service: The BridgeService instance.
        idempotency_key: Optional header for idempotency protection.
        stage_instance: The ID of the sending Chorus Stage instance.
        rate_limit: Dependency for rate limiting enforcement.
        jwt_auth_dep: Dependency for JWT authentication enforcement.

    Returns:
        A dictionary indicating the acceptance status and event details.

    Raises:
        HTTPException: For various errors such as missing headers, duplicate envelopes,
                       duplicate idempotency keys, permission errors, or invalid data.
    """
    if not stage_instance:
        raise HTTPException(
            status_code=400, detail="missing X-Chorus-Instance-Id header"
        )
    raw = await request.body()
    try:
        envelope = pb2.FederationEnvelope.FromString(raw)
        receipt, fingerprint = await service.process_federation_envelope(
            envelope=envelope,
            idempotency_key=idempotency_key,
            stage_instance=stage_instance,
        )
    except DuplicateEnvelopeError:
        raise HTTPException(
            status_code=409, detail="duplicate federation envelope"
        ) from None
    except DuplicateIdempotencyKeyError:
        raise HTTPException(
            status_code=409, detail="duplicate idempotency key"
        ) from None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {
        "status": "accepted",
        "event_hash": receipt.event_hash,
        "epoch": receipt.epoch,
        "fingerprint": fingerprint,
    }


@router.post("/export", status_code=status.HTTP_202_ACCEPTED)
async def activitypub_export(
    payload: ActivityPubExportRequest,
    service: BridgeService = Depends(get_bridge_service),
    stage_instance: Optional[str] = Header(default=None, alias="X-Chorus-Instance-Id"),
    rate_limit: None = Depends(RateLimiter),  # Rate limiting enforced by dependency
    jwt_auth_dep: None = Depends(JWTAuth),  # JWT auth enforced by dependency
):
    """Receives a request to export Chorus content to ActivityPub.

    This endpoint is protected by rate limiting and JWT authentication.

    Args:
        payload: The ActivityPubExportRequest containing the Chorus content to export.
        service: The BridgeService instance.
        stage_instance: The ID of the sending Chorus Stage instance.
        rate_limit: Dependency for rate limiting enforcement.
        jwt_auth_dep: Dependency for JWT authentication enforcement.

    Returns:
        A dictionary indicating the queuing status and job ID.

    Raises:
        HTTPException: For various errors such as missing headers, permission errors,
                       or invalid data.
    """
    if not stage_instance:
        raise HTTPException(
            status_code=400, detail="missing X-Chorus-Instance-Id header"
        )
    try:
        job_id = await service.queue_activitypub_export(
            request=payload, stage_instance=stage_instance
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"status": "queued", "job_id": job_id}


@router.post("/moderation/event", status_code=status.HTTP_202_ACCEPTED)
async def moderation_event(
    payload: ModerationEventRequest,
    service: BridgeService = Depends(get_bridge_service),
    stage_instance: Optional[str] = Header(default=None, alias="X-Chorus-Instance-Id"),
    rate_limit: None = Depends(RateLimiter),  # Rate limiting enforced by dependency
    jwt_auth_dep: None = Depends(JWTAuth),  # JWT auth enforced by dependency
):
    """Receives and records a moderation event from a Chorus Stage instance.

    This endpoint is protected by rate limiting and JWT authentication.

    Args:
        payload: The ModerationEventRequest containing the moderation event details.
        service: The BridgeService instance.
        stage_instance: The ID of the sending Chorus Stage instance.
        rate_limit: Dependency for rate limiting enforcement.
        jwt_auth_dep: Dependency for JWT authentication enforcement.

    Returns:
        A dictionary indicating the acceptance status and event details.

    Raises:
        HTTPException: For various errors such as missing headers, permission errors,
                       or invalid data.
    """
    if not stage_instance:
        raise HTTPException(
            status_code=400, detail="missing X-Chorus-Instance-Id header"
        )
    try:
        event_id, receipt = await service.record_moderation_event(
            request=payload,
            stage_instance=stage_instance,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {
        "status": "accepted",
        "event_id": event_id,
        "epoch": receipt.epoch,
        "event_hash": receipt.event_hash,
    }
