from __future__ import annotations

import dataclasses
import json
from typing import Any, Optional, Tuple

from nacl.signing import VerifyKey

from chorus_bridge.core.security import envelope_fingerprint, verify_signature
from chorus_bridge.core.settings import BridgeSettings
from chorus_bridge.core.trust import TrustStore, UnknownInstanceError
from chorus_bridge.db.repository import BridgeRepository
from chorus_bridge.proto.federation_messages import FederationEnvelope, BaseMessage
from chorus_bridge.schemas import ActivityPubExportRequest, DayProofResponse, ModerationEventRequest

from .activitypub import ActivityPubTranslator
from .conductor import ConductorClient, ConductorEvent, ConductorReceipt, InMemoryConductorClient


class DuplicateEnvelopeError(RuntimeError):
    """Raised when a federation envelope fingerprint already exists."""


class DuplicateIdempotencyKeyError(RuntimeError):
    """Raised when an idempotency key has already been processed."""


def _canonical_model_json(model: Any) -> str:
    """Return a stable JSON representation for signature verification."""
    if isinstance(model, BaseMessage):
        return json.dumps(model.to_dict(), sort_keys=True, separators=(",", ":"))
    # Fallback for Pydantic models if any still exist or are introduced
    return json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


class BridgeService:
    """Coordinator responsible for high-level Bridge operations."""

    def __init__(
        self,
        *,
        settings: BridgeSettings,
        repository: BridgeRepository,
        trust_store: TrustStore,
        conductor: Optional[ConductorClient] = None,
        activitypub_translator: Optional[ActivityPubTranslator] = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._trust_store = trust_store
        self._conductor = conductor or InMemoryConductorClient()
        self._translator = activitypub_translator or ActivityPubTranslator(
            genesis_timestamp=settings.export_genesis_timestamp,
            actor_domain=settings.activitypub_actor_domain,
        )

    # Day proofs ------------------------------------------------------------

    async def get_day_proof(self, day_number: int) -> Optional[DayProofResponse]:
        stored = self._repository.get_day_proof(day_number)
        if stored:
            return stored
        proof = await self._conductor.get_day_proof(day_number)
        if proof:
            self._repository.upsert_day_proof(proof, source="conductor")
            return self._repository.get_day_proof(day_number)
        return None

    async def record_day_proof(self, proof_json: str) -> ConductorReceipt:
        event = ConductorEvent(
            event_type="day_proof",
            epoch=self._derive_epoch_from_payload(proof_json),
            payload=proof_json.encode("utf-8"),
        )
        return await self._conductor.submit_event(event)

    # Federation envelopes --------------------------------------------------

    async def process_federation_envelope(
        self,
        *,
        raw_bytes: bytes,
        idempotency_key: Optional[str],
        stage_instance: str,
    ) -> Tuple[ConductorReceipt, str]:
        try:
            envelope = FederationEnvelope.from_bytes(raw_bytes)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid FederationEnvelope bytes: {exc}") from exc

        verify_key = self._fetch_verify_key(envelope.sender_instance)
        verify_signature(envelope.message_data, envelope.signature, verify_key)

        fingerprint = envelope_fingerprint(
            (
                envelope.sender_instance.encode("utf-8"),
                envelope.message_type.encode("utf-8"),
                envelope.message_data,
            )
        )

        if not self._repository.remember_envelope(
            fingerprint,
            envelope,
            self._settings.replay_cache_ttl_seconds,
        ):
            raise DuplicateEnvelopeError(fingerprint)

        if idempotency_key:
            if not self._repository.remember_idempotency_key(
                stage_instance,
                idempotency_key,
                self._settings.idempotency_ttl_seconds,
            ):
                raise DuplicateIdempotencyKeyError(idempotency_key)

        event = ConductorEvent(
            event_type="federation_envelope",
            epoch=self._derive_epoch(envelope.timestamp),
            payload=envelope.message_data,
            metadata={
                "sender_instance": envelope.sender_instance,
                "message_type": envelope.message_type,
            },
        )
        receipt = await self._conductor.submit_event(event)
        return receipt, fingerprint

    # ActivityPub -----------------------------------------------------------

    async def queue_activitypub_export(
        self,
        *,
        request: ActivityPubExportRequest,
        stage_instance: str,
    ) -> str:
        verify_key = self._fetch_verify_key(stage_instance)
        verify_signature(
            _canonical_model_json(request.chorus_post).encode("utf-8"),
            request.signature,
            verify_key,
        )
        note, published_ts = self._translator.build_note(request.chorus_post)
        job_id = self._repository.enqueue_export(
            stage_instance=stage_instance,
            object_hash=request.chorus_post.post_id, # Using post_id as object_hash for now
            ap_type="Note", # Assuming Note for posts
            target_url="", # This needs to be determined or passed
            status="queued",
            published_ts=published_ts,
            raw_payload=request.chorus_post.to_bytes(),
        )
        event = ConductorEvent(
            event_type="activitypub_export",
            epoch=self._derive_epoch(request.chorus_post.creation_day),
            payload=note.model_dump_json(by_alias=True).encode("utf-8"),
            metadata={"stage_instance": stage_instance, "post_id": request.chorus_post.post_id},
        )
        await self._conductor.submit_event(event)
        return job_id

    # Moderation ------------------------------------------------------------

    async def record_moderation_event(
        self,
        *,
        request: ModerationEventRequest,
        stage_instance: str,
    ) -> Tuple[str, ConductorReceipt]:
        verify_key = self._fetch_verify_key(stage_instance)
        verify_signature(
            _canonical_model_json(request.moderation_event).encode("utf-8"),
            request.signature,
            verify_key,
        )
        event_id = self._repository.record_moderation_event(
            stage_instance=stage_instance,
            target_ref=request.moderation_event.target_ref,
            action=request.moderation_event.action,
            reason_hash=request.moderation_event.reason_hash,
            creation_day=request.moderation_event.creation_day,
            raw_payload=request.moderation_event.to_bytes(),
        )
        receipt = await self._conductor.submit_event(
            ConductorEvent(
                event_type="moderation_event",
                epoch=self._derive_epoch(request.moderation_event.creation_day),
                payload=request.moderation_event.to_bytes(),
                metadata={"stage_instance": stage_instance, "event_id": event_id},
            )
        )
        return event_id, receipt

    # Internal --------------------------------------------------------------

    def _fetch_verify_key(self, instance_id: str) -> VerifyKey:
        try:
            return self._trust_store.get(instance_id)
        except UnknownInstanceError as exc:
            raise PermissionError(f"unknown instance '{instance_id}'") from exc

    @staticmethod
    def _derive_epoch(timestamp_or_day: int) -> int:
        if timestamp_or_day > 10_000:
            return timestamp_or_day
        return timestamp_or_day

    @staticmethod
    def _derive_epoch_from_payload(json_payload: str) -> int:
        data = json.loads(json_payload)
        day_number = int(data.get("day_number", 0))
        return day_number


__all__ = [
    "BridgeService",
    "DuplicateEnvelopeError",
    "DuplicateIdempotencyKeyError",
]
