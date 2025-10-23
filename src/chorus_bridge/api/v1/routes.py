from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from chorus_bridge.schemas import ActivityPubExportRequest, ModerationEventRequest
from chorus_bridge.services import (
    BridgeService,
    DuplicateEnvelopeError,
    DuplicateIdempotencyKeyError,
)


router = APIRouter(prefix="/api/bridge", tags=["bridge", "v1"])


def get_bridge_service(request: Request) -> BridgeService:
    service: BridgeService = request.app.state.bridge_service
    return service


@router.get("/day-proof/{day_number}")
async def get_day_proof(
    day_number: int,
    service: BridgeService = Depends(get_bridge_service),
):
    if day_number < 0:
        raise HTTPException(status_code=400, detail="day_number must be non-negative")
    proof = await service.get_day_proof(day_number)
    if not proof:
        raise HTTPException(status_code=404, detail="canonical day proof unavailable")
    return proof


@router.post("/federation/send", status_code=status.HTTP_202_ACCEPTED)
async def federation_send(
    request: Request,
    service: BridgeService = Depends(get_bridge_service),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    stage_instance: Optional[str] = Header(default=None, alias="X-Chorus-Instance-Id"),
):
    if not stage_instance:
        raise HTTPException(status_code=400, detail="missing X-Chorus-Instance-Id header")
    raw = await request.body()
    try:
        receipt, fingerprint = await service.process_federation_envelope(
            raw_bytes=raw,
            idempotency_key=idempotency_key,
            stage_instance=stage_instance,
        )
    except DuplicateEnvelopeError:
        raise HTTPException(status_code=409, detail="duplicate federation envelope") from None
    except DuplicateIdempotencyKeyError:
        raise HTTPException(status_code=409, detail="duplicate idempotency key") from None
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
):
    if not stage_instance:
        raise HTTPException(status_code=400, detail="missing X-Chorus-Instance-Id header")
    try:
        job_id = await service.queue_activitypub_export(request=payload, stage_instance=stage_instance)
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
):
    if not stage_instance:
        raise HTTPException(status_code=400, detail="missing X-Chorus-Instance-Id header")
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
