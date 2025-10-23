from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, Integer, String, Text
from sqlalchemy.types import JSON

from .base import Base


class DayProofRecord(Base):
    __tablename__ = "day_proofs"

    day = Column(Integer, primary_key=True)
    proof = Column(Text, nullable=False)
    proof_hash = Column(String(128), nullable=False)
    canonical = Column(Boolean, nullable=False, default=True)
    source = Column(String(64), nullable=False)
    created_at = Column(BigInteger, nullable=False)


class EnvelopeCache(Base):
    __tablename__ = "envelope_cache"

    fingerprint = Column(String(128), primary_key=True)
    sender_instance = Column(String(128), nullable=False)
    message_type = Column(String(64), nullable=False)
    expires_at = Column(BigInteger, nullable=False)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    instance_id = Column(String(128), primary_key=True)
    key = Column(String(128), primary_key=True)
    expires_at = Column(BigInteger, nullable=False)


class BridgeActor(Base):
    __tablename__ = "bridge_actor"

    id = Column(BigInteger, primary_key=True)
    pubkey_hash = Column(String(64), unique=True, nullable=False)
    actor_uri = Column(Text, nullable=False)
    created_at = Column(BigInteger, nullable=False)


class BridgeBlocklist(Base):
    __tablename__ = "bridge_blocklist"

    id = Column(BigInteger, primary_key=True)
    object_hash = Column(String(64), unique=True, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False)


class ExportLedger(Base):
    __tablename__ = "export_ledger"

    id = Column(BigInteger, primary_key=True)
    object_hash = Column(String(64), nullable=False)
    ap_type = Column(String(32), nullable=False)
    target_url = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    last_attempt_at = Column(BigInteger, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)


class ModerationEventRecord(Base):
    __tablename__ = "moderation_events"

    id = Column(String(64), primary_key=True)
    target_ref = Column(String(256), nullable=False)
    action = Column(String(64), nullable=False)
    reason_hash = Column(String(128), nullable=False)
    creation_day = Column(Integer, nullable=False)
    raw_payload = Column(Text, nullable=False)
    stage_instance = Column(String(128), nullable=False)
    signature = Column(String(256), nullable=False)
    received_at = Column(BigInteger, nullable=False)
