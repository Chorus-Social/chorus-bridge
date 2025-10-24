from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, Boolean, Column, Integer, String, Text, LargeBinary

from .base import Base


class DayProofRecord(Base):
    """Represents a record of a day proof, either canonical or from a specific source."""

    __tablename__ = "day_proofs"

    day = Column(Integer, primary_key=True)
    proof = Column(Text, nullable=False)
    proof_hash = Column(String(128), nullable=False)
    canonical = Column(Boolean, nullable=False, default=True)
    source = Column(String(64), nullable=False)
    created_at = Column(BigInteger, nullable=False)


class EnvelopeCache(Base):
    """Caches federation envelope fingerprints to prevent replay attacks."""

    __tablename__ = "envelope_cache"

    fingerprint = Column(String(128), primary_key=True)
    sender_instance = Column(String(128), nullable=False)
    message_type = Column(String(64), nullable=False)
    expires_at = Column(BigInteger, nullable=False)


class IdempotencyKey(Base):
    """Stores idempotency keys to ensure unique processing of requests."""

    __tablename__ = "idempotency_keys"

    instance_id = Column(String(128), primary_key=True)
    key = Column(String(128), primary_key=True)
    expires_at = Column(BigInteger, nullable=False)


class BridgeActor(Base):
    """Represents an ActivityPub actor managed by the Bridge for export purposes."""

    __tablename__ = "bridge_actor"

    id = Column(BigInteger, primary_key=True)
    pubkey_hash = Column(String(64), unique=True, nullable=False)
    actor_uri = Column(Text, nullable=False)
    created_at = Column(BigInteger, nullable=False)


class BridgeBlocklist(Base):
    """Stores hashes of content or objects that are blocked from federation or export."""

    __tablename__ = "bridge_blocklist"

    id = Column(BigInteger, primary_key=True)
    object_hash = Column(String(64), unique=True, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False)


class ExportLedger(Base):
    """Records the status of ActivityPub export jobs."""

    __tablename__ = "export_ledger"

    id = Column(BigInteger, primary_key=True)
    object_hash = Column(
        String(64), nullable=False
    )  # Consider LargeBinary if this can contain non-UTF-8 binary data
    ap_type = Column(String(32), nullable=False)
    target_url = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    last_attempt_at = Column(BigInteger, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    published_ts = Column(
        BigInteger, nullable=False
    )  # Timestamp when the item was published
    retry_at = Column(
        BigInteger, nullable=False, default=0
    )  # Timestamp for next retry attempt
    raw_payload = Column(
        Text, nullable=False
    )  # Consider LargeBinary if this can contain non-UTF-8 binary data


class ModerationEventRecord(Base):
    """Records moderation events received from federated instances."""

    __tablename__ = "moderation_events"

    id = Column(String(64), primary_key=True)
    target_ref = Column(String(256), nullable=False)
    action = Column(String(64), nullable=False)
    reason_hash = Column(String(128), nullable=False)
    creation_day = Column(Integer, nullable=False)
    raw_payload = Column(LargeBinary, nullable=False)  # Changed to LargeBinary
    stage_instance = Column(String(128), nullable=False)
    signature = Column(String(256), nullable=False)
    received_at = Column(BigInteger, nullable=False)


class QuarantinedEnvelope(Base):
    """Stores federation envelopes that failed parsing or validation for operator review."""

    __tablename__ = "quarantined_envelopes"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    raw_envelope = Column(LargeBinary, nullable=False)  # Changed to LargeBinary
    reason = Column(Text, nullable=False)
    quarantined_at = Column(BigInteger, nullable=False)


class FederatedPost(Base):
    """Stores federated posts received from other Chorus Stage instances."""

    __tablename__ = "federated_posts"

    post_id = Column(String(64), primary_key=True)
    author_pubkey = Column(String(64), nullable=False)
    content_hash = Column(String(64), nullable=False)
    order_index = Column(Integer, nullable=False)
    creation_day = Column(Integer, nullable=False)
    sender_instance = Column(String(128), nullable=False)
    received_at = Column(BigInteger, nullable=False)


class JtiCache(Base):
    """Caches JWT IDs (JTIs) to prevent replay attacks for authenticated requests."""

    __tablename__ = "jti_cache"

    jti = Column(String(256), primary_key=True)
    instance_id = Column(String(128), nullable=False)
    expires_at = Column(BigInteger, nullable=False)


class RegisteredUser(Base):
    """Stores records of user registrations received from federated instances."""

    __tablename__ = "registered_users"

    user_pubkey = Column(String(64), primary_key=True)

    registration_day = Column(Integer, nullable=False)

    day_proof_hash = Column(String(128), nullable=False)

    sender_instance = Column(String(128), nullable=False)

    registered_at = Column(BigInteger, nullable=False)


class OutboundFederationLedger(Base):
    """Records the status of outbound federation messages to other Stage instances."""

    __tablename__ = "outbound_federation_ledger"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))

    target_instance_url = Column(Text, nullable=False)

    message_type = Column(String(64), nullable=False)

    raw_envelope = Column(
        LargeBinary, nullable=False
    )  # The full FederationEnvelope to send

    status = Column(String(32), nullable=False, default="queued")

    last_attempt_at = Column(BigInteger, nullable=True)

    attempts = Column(Integer, nullable=False, default=0)

    retry_at = Column(BigInteger, nullable=False, default=0)

    created_at = Column(BigInteger, nullable=False)


class FederatedCommunity(Base):
    """Stores federated community creation events received from other Chorus Stage instances."""

    __tablename__ = "federated_communities"

    community_id = Column(String(64), primary_key=True)

    creator_pubkey = Column(String(64), nullable=False)

    name = Column(Text, nullable=False)

    description = Column(Text, nullable=False)

    creation_day = Column(Integer, nullable=False)

    sender_instance = Column(String(128), nullable=False)

    received_at = Column(BigInteger, nullable=False)


class FederatedUserUpdate(Base):
    """Stores federated user update events received from other Chorus Stage instances."""

    __tablename__ = "federated_user_updates"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))

    user_pubkey = Column(String(64), nullable=False)

    updated_fields_payload = Column(Text, nullable=False)

    update_day = Column(Integer, nullable=False)

    sender_instance = Column(String(128), nullable=False)

    received_at = Column(BigInteger, nullable=False)


class FederatedCommunityUpdate(Base):
    """Stores federated community update events received from other Chorus Stage instances."""

    __tablename__ = "federated_community_updates"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))

    community_id = Column(String(64), nullable=False)

    updated_fields_payload = Column(Text, nullable=False)

    update_day = Column(Integer, nullable=False)

    sender_instance = Column(String(128), nullable=False)

    received_at = Column(BigInteger, nullable=False)


class FederatedCommunityMembership(Base):
    """Stores federated community membership update events (join/leave) received from other Chorus Stage instances."""

    __tablename__ = "federated_community_memberships"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))

    community_id = Column(String(64), nullable=False)

    user_pubkey = Column(String(64), nullable=False)

    action = Column(String(32), nullable=False)  # "join" or "leave"

    update_day = Column(Integer, nullable=False)

    sender_instance = Column(String(128), nullable=False)

    received_at = Column(BigInteger, nullable=False)
