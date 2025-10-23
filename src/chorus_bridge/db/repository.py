from __future__ import annotations

import json
import time
import uuid
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session

from chorus_bridge.proto.federation_messages import FederationEnvelope, PostAnnouncement, ModerationEvent
from chorus_bridge.schemas import ActivityPubNote, DayProof, DayProofResponse, ModerationEventRequest

from .base import DatabaseSessionManager
from .models import BridgeActor, BridgeBlocklist, DayProofRecord, EnvelopeCache, IdempotencyKey, ExportLedger, ModerationEventRecord


class BridgeRepository:
    """Persistence primitives backed by SQLAlchemy."""

    def __init__(self, db: DatabaseSessionManager) -> None:
        self._db = db

    # Day proofs -------------------------------------------------------------

    def upsert_day_proof(self, proof: DayProof, *, source: str) -> None:
        now = int(time.time())
        with self._db.session() as session:
            record = session.get(DayProofRecord, proof.day_number)
            if record is None:
                record = DayProofRecord(
                    day=proof.day_number,
                    proof=proof.proof,
                    proof_hash=proof.proof_hash,
                    canonical=proof.canonical,
                    source=source,
                    created_at=now,
                )
                session.add(record)
            else:
                record.proof = proof.proof
                record.proof_hash = proof.proof_hash
                record.canonical = proof.canonical
                record.source = source
                record.created_at = now

    def get_day_proof(self, day_number: int) -> Optional[DayProofResponse]:
        with self._db.session() as session:
            record = session.get(DayProofRecord, day_number)
            if not record:
                return None
            return DayProofResponse(
                day_number=record.day,
                proof=record.proof,
                proof_hash=record.proof_hash,
                canonical=record.canonical,
                source=record.source,
            )

    # Federation envelope replay cache --------------------------------------

    def remember_envelope(self, fingerprint: str, envelope: FederationEnvelope, ttl_seconds: int) -> bool:
        now = int(time.time())
        expires = now + ttl_seconds
        with self._db.session() as session:
            self._purge_expired_envelopes(session, now)
            existing = session.get(EnvelopeCache, fingerprint)
            if existing:
                return False
            session.add(
                EnvelopeCache(
                    fingerprint=fingerprint,
                    sender_instance=envelope.sender_instance,
                    message_type=envelope.message_type,
                    expires_at=expires,
                )
            )
            return True

    def _purge_expired_envelopes(self, session: Session, now: int) -> None:
        session.execute(delete(EnvelopeCache).where(EnvelopeCache.expires_at < now))

    # Idempotency ------------------------------------------------------------

    def remember_idempotency_key(self, instance_id: str, key: str, ttl_seconds: int) -> bool:
        now = int(time.time())
        expires = now + ttl_seconds
        with self._db.session() as session:
            session.execute(delete(IdempotencyKey).where(IdempotencyKey.expires_at < now))
            existing = session.get(IdempotencyKey, (instance_id, key))
            if existing:
                return False
            session.add(IdempotencyKey(instance_id=instance_id, key=key, expires_at=expires))
            return True

    # ActivityPub exports ----------------------------------------------------

    def enqueue_export(
        self,
        *,
        stage_instance: str,
        object_hash: bytes,
        ap_type: str,
        target_url: str,
        status: str,
        published_ts: int,
        raw_payload: bytes,
    ) -> str:
        job_id = str(uuid.uuid4())
        now = int(time.time())
        with self._db.session() as session:
            session.add(
                ExportLedger(
                    id=job_id,
                    object_hash=object_hash.decode("utf-8"), # Assuming object_hash is bytes and can be decoded
                    ap_type=ap_type,
                    target_url=target_url,
                    status=status,
                    last_attempt_at=None,
                    attempts=0,
                    raw_payload=raw_payload.decode("utf-8"), # Assuming raw_payload is bytes and can be decoded
                    created_at=now,
                )
            )
        return job_id

    # Moderation events ------------------------------------------------------

    def record_moderation_event(
        self,
        *,
        stage_instance: str,
        target_ref: bytes,
        action: str,
        reason_hash: bytes,
        creation_day: int,
        raw_payload: bytes,
    ) -> str:
        event_id = str(uuid.uuid4())
        now = int(time.time())
        with self._db.session() as session:
            session.add(
                ModerationEventRecord(
                    id=event_id,
                    target_ref=target_ref.decode("utf-8"), # Assuming target_ref is bytes and can be decoded
                    action=action,
                    reason_hash=reason_hash.decode("utf-8"), # Assuming reason_hash is bytes and can be decoded
                    creation_day=creation_day,
                    raw_payload=raw_payload.decode("utf-8"), # Assuming raw_payload is bytes and can be decoded
                    stage_instance=stage_instance,
                    received_at=now,
                )
            )
        return event_id
