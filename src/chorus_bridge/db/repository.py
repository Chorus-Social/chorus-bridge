from __future__ import annotations

import time
import uuid
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session

from chorus_bridge.proto import federation_pb2 as pb2
from chorus_bridge.proto.federation_pb2 import FederationEnvelope
from chorus_bridge.schemas import DayProof, DayProofResponse

from .base import DatabaseSessionManager
from .models import (
    DayProofRecord,
    EnvelopeCache,
    IdempotencyKey,
    ExportLedger,
    ModerationEventRecord,
    QuarantinedEnvelope,
    FederatedPost,
    RegisteredUser,
    JtiCache,
    OutboundFederationLedger,
    FederatedCommunity,
    FederatedUserUpdate,
    FederatedCommunityUpdate,
    FederatedCommunityMembership,
)


class BridgeRepository:
    """Persistence primitives backed by SQLAlchemy for Chorus Bridge data."""

    def __init__(self, db: DatabaseSessionManager) -> None:
        """Initializes the BridgeRepository with a database session manager.

        Args:
            db: The DatabaseSessionManager instance.
        """
        self._db = db

    # Day proofs -------------------------------------------------------------

    def upsert_day_proof(self, proof: DayProof, *, source: str) -> None:
        """Inserts or updates a day proof record.

        Args:
            proof: The DayProof object to upsert.
            source: The source of the day proof (e.g., 'conductor', 'federated').
        """
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
        """Retrieves a day proof record by its day number.

        Args:
            day_number: The day number of the proof to retrieve.

        Returns:
            A DayProofResponse object if found, otherwise None.
        """
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

    def remember_envelope(
        self, fingerprint: str, envelope: FederationEnvelope, ttl_seconds: int
    ) -> bool:
        """Stores a federation envelope fingerprint to prevent replay attacks.

        Args:
            fingerprint: The unique fingerprint of the envelope.
            envelope: The FederationEnvelope object.
            ttl_seconds: Time-to-live for the fingerprint in seconds.

        Returns:
            True if the envelope was remembered (not a duplicate), False otherwise.
        """
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
        """Removes expired envelope fingerprints from the cache.

        Args:
            session: The SQLAlchemy session to use.
            now: The current Unix timestamp.
        """
        session.execute(delete(EnvelopeCache).where(EnvelopeCache.expires_at < now))

    # Idempotency ------------------------------------------------------------

    def remember_idempotency_key(
        self, instance_id: str, key: str, ttl_seconds: int
    ) -> bool:
        """Stores an idempotency key to prevent duplicate processing of requests.

        Args:
            instance_id: The ID of the instance that sent the key.
            key: The idempotency key.
            ttl_seconds: Time-to-live for the key in seconds.

        Returns:
            True if the key was remembered (not a duplicate), False otherwise.
        """
        now = int(time.time())
        expires = now + ttl_seconds
        with self._db.session() as session:
            session.execute(
                delete(IdempotencyKey).where(IdempotencyKey.expires_at < now)
            )
            existing = session.get(IdempotencyKey, (instance_id, key))
            if existing:
                return False
            session.add(
                IdempotencyKey(instance_id=instance_id, key=key, expires_at=expires)
            )
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
        """Enqueues an ActivityPub export job.

        Args:
            stage_instance: The ID of the Chorus Stage instance initiating the export.
            object_hash: The hash of the object being exported.
            ap_type: The ActivityPub type of the object (e.g., 'Note').
            target_url: The target ActivityPub outbox URL.
            status: The initial status of the job (e.g., 'queued').
            published_ts: The derived published timestamp for the ActivityPub object.
            raw_payload: The raw bytes of the Chorus object being exported.

        Returns:
            The job ID of the enqueued export.
        """
        job_id = str(uuid.uuid4())
        now = int(time.time())
        with self._db.session() as session:
            session.add(
                ExportLedger(
                    id=job_id,
                    object_hash=object_hash.decode(
                        "utf-8"
                    ),  # Assuming object_hash is bytes and can be decoded. If not, consider storing as LargeBinary in DB.
                    ap_type=ap_type,
                    target_url=target_url,
                    status=status,
                    last_attempt_at=None,
                    attempts=0,
                    raw_payload=raw_payload.decode(
                        "utf-8"
                    ),  # Assuming raw_payload is bytes and can be decoded. If not, consider storing as LargeBinary in DB.
                    created_at=now,
                    published_ts=published_ts,
                    retry_at=now,  # Initialize retry_at to now
                )
            )
            session.commit()
        return job_id

    def get_queued_exports(self) -> list[ExportLedger]:
        """Retrieves a list of ActivityPub exports that are queued or due for retry.

        Returns:
            A list of ExportLedger objects.
        """
        now = int(time.time())
        with self._db.session() as session:
            return (
                session.query(ExportLedger)
                .filter(
                    ExportLedger.status.in_(["queued", "retrying"]),
                    ExportLedger.retry_at <= now,
                )
                .all()
            )

    def update_export_status(self, job_id: str, status: str) -> None:
        """Updates the status of an ActivityPub export job.

        Args:
            job_id: The ID of the export job.
            status: The new status (e.g., 'delivered', 'failed').
        """
        now = int(time.time())
        with self._db.session() as session:
            export = session.get(ExportLedger, job_id)
            if export:
                export.status = status
                export.last_attempt_at = now
                session.commit()

    def update_export_for_retry(
        self, job_id: str, new_attempts: int, retry_at: int
    ) -> None:
        """Updates retry information for a failed ActivityPub export job.

        Args:
            job_id: The ID of the export job.
            new_attempts: The new number of retry attempts.
            retry_at: The Unix timestamp for the next retry attempt.
        """
        now = int(time.time())
        with self._db.session() as session:
            export = session.get(ExportLedger, job_id)
            if export:
                export.status = "retrying"
                export.attempts = new_attempts
                export.retry_at = retry_at
                export.last_attempt_at = now
                session.commit()

    def quarantine_envelope(self, raw_envelope: bytes, reason: str) -> None:
        """Stores a malformed federation envelope for operator review.

        Args:
            raw_envelope: The raw bytes of the failed envelope.
            reason: The reason for quarantining the envelope.
        """
        now = int(time.time())
        with self._db.session() as session:
            session.add(
                QuarantinedEnvelope(
                    raw_envelope=raw_envelope,
                    reason=reason,
                    quarantined_at=now,
                )
            )
            session.commit()

    def save_federated_post(
        self, sender_instance: str, post: pb2.PostAnnouncement
    ) -> None:
        """Saves a federated post received from another instance.

        Args:
            sender_instance: The ID of the instance that sent the post.
            post: The PostAnnouncement message.
        """
        now = int(time.time())
        with self._db.session() as session:
            session.add(
                FederatedPost(
                    post_id=post.post_id.hex(),
                    author_pubkey=post.author_pubkey.hex(),
                    content_hash=post.content_hash.hex(),
                    order_index=post.order_index,
                    creation_day=post.creation_day,
                    sender_instance=sender_instance,
                    received_at=now,
                )
            )
            session.commit()

    def save_registered_user(
        self, sender_instance: str, user_reg: pb2.UserRegistration
    ) -> None:
        """Saves a registered user received from another federated instance.

        Args:
            sender_instance: The ID of the instance that sent the registration.
            user_reg: The UserRegistration message.
        """
        now = int(time.time())
        with self._db.session() as session:
            session.add(
                RegisteredUser(
                    user_pubkey=user_reg.user_pubkey.hex(),
                    registration_day=user_reg.registration_day,
                    day_proof_hash=user_reg.day_proof_hash.hex(),
                    sender_instance=sender_instance,
                    registered_at=now,
                )
            )
            session.commit()

    def remember_jti(self, jti: str, instance_id: str, expires_at: int) -> bool:
        """Stores a JWT ID (JTI) to prevent replay attacks.

        Args:
            jti: The unique JWT ID.
            instance_id: The ID of the instance that issued the JWT.
            expires_at: The Unix timestamp when the JTI expires.

        Returns:
            True if the JTI was remembered (not a duplicate), False otherwise.
        """
        now = int(time.time())
        with self._db.session() as session:
            session.execute(delete(JtiCache).where(JtiCache.expires_at < now))
            existing = session.get(JtiCache, jti)
            if existing:
                return False
            session.add(
                JtiCache(jti=jti, instance_id=instance_id, expires_at=expires_at)
            )
            session.commit()
            return True

    def save_federated_community(
        self, sender_instance: str, community: pb2.CommunityCreation
    ) -> None:
        """Saves a federated community creation event received from another instance.

        Args:
            sender_instance: The ID of the instance that sent the community creation event.
            community: The CommunityCreation message.
        """
        now = int(time.time())
        with self._db.session() as session:
            session.add(
                FederatedCommunity(
                    community_id=community.community_id.hex(),
                    creator_pubkey=community.creator_pubkey.hex(),
                    name=community.name,
                    description=community.description,
                    creation_day=community.creation_day,
                    sender_instance=sender_instance,
                    received_at=now,
                )
            )
            session.commit()

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
                """Records a moderation event.



                Args:

                    stage_instance: The ID of the Chorus Stage instance initiating the event.

                    target_ref: The reference to the target of the moderation action.

                    action: The moderation action (e.g., 'hide', 'delete').

                    reason_hash: The hash of the reason for the moderation action.

                    creation_day: The day number when the event was created.

                    raw_payload: The raw bytes of the moderation event payload.



                Returns:

                    The ID of the recorded moderation event.

                """

                event_id = str(uuid.uuid4())

                now = int(time.time())

                with self._db.session() as session:
                    session.add(
                        ModerationEventRecord(
                            id=event_id,
                            target_ref=target_ref.decode(
                                "utf-8"
                            ),  # Assuming target_ref is bytes and can be decoded. If not, consider storing as LargeBinary in DB.
                            action=action,
                            reason_hash=reason_hash.decode(
                                "utf-8"
                            ),  # Assuming reason_hash is bytes and can be decoded. If not, consider storing as LargeBinary in DB.
                            creation_day=creation_day,
                            raw_payload=raw_payload,
                            stage_instance=stage_instance,
                            received_at=now,
                        )
                    )

                    session.commit()

                return event_id

            def save_federated_user_update(
                self, sender_instance: str, user_update: pb2.UserUpdate
            ) -> None:
                """Saves a federated user update event received from another instance."""

                now = int(time.time())

                with self._db.session() as session:
                    session.add(
                        FederatedUserUpdate(
                            user_pubkey=user_update.user_pubkey.hex(),
                            updated_fields_payload=user_update.updated_fields_payload.decode(
                                "utf-8"
                            ),
                            update_day=user_update.update_day,
                            sender_instance=sender_instance,
                            received_at=now,
                        )
                    )

                    session.commit()

            def save_federated_community_update(
                self, sender_instance: str, community_update: pb2.CommunityUpdate
            ) -> None:
                """Saves a federated community update event received from another instance."""

                now = int(time.time())

                with self._db.session() as session:
                    session.add(
                        FederatedCommunityUpdate(
                            community_id=community_update.community_id.hex(),
                            updated_fields_payload=community_update.updated_fields_payload.decode(
                                "utf-8"
                            ),
                            update_day=community_update.update_day,
                            sender_instance=sender_instance,
                            received_at=now,
                        )
                    )

                    session.commit()

            def save_federated_community_membership(
                self,
                sender_instance: str,
                membership_update: pb2.CommunityMembershipUpdate,
            ) -> None:
                """Saves a federated community membership update event received from another instance."""

                now = int(time.time())

                with self._db.session() as session:
                    session.add(
                        FederatedCommunityMembership(
                            community_id=membership_update.community_id.hex(),
                            user_pubkey=membership_update.user_pubkey.hex(),
                            action=membership_update.action,
                            update_day=membership_update.update_day,
                            sender_instance=sender_instance,
                            received_at=now,
                        )
                    )

                    session.commit()

            # Outbound Federation ----------------------------------------------------

        def enqueue_outbound_federation_message(
            self,
            target_instance_url: str,
            message_type: str,
            raw_envelope: bytes,
        ) -> str:
            """Enqueues an outbound federation message to be sent to a target Stage instance.



            Args:

                target_instance_url: The base URL of the target Stage instance.

                message_type: The type of the message (e.g., 'PostAnnouncement').

                raw_envelope: The raw bytes of the FederationEnvelope to send.



            Returns:

                The job ID of the enqueued outbound message.

            """

            job_id = str(uuid.uuid4())

            now = int(time.time())

            with self._db.session() as session:
                session.add(
                    OutboundFederationLedger(
                        id=job_id,
                        target_instance_url=target_instance_url,
                        message_type=message_type,
                        raw_envelope=raw_envelope,
                        status="queued",
                        last_attempt_at=None,
                        attempts=0,
                        retry_at=now,
                        created_at=now,
                    )
                )

                session.commit()

            return job_id

        def get_queued_outbound_federation_messages(
            self,
        ) -> list[OutboundFederationLedger]:
            """Retrieves a list of outbound federation messages that are queued or due for retry.



            Returns:

                A list of OutboundFederationLedger objects.

            """

            now = int(time.time())

            with self._db.session() as session:
                return (
                    session.query(OutboundFederationLedger)
                    .filter(
                        OutboundFederationLedger.status.in_(["queued", "retrying"]),
                        OutboundFederationLedger.retry_at <= now,
                    )
                    .all()
                )

        def update_outbound_federation_message_status(
            self, job_id: str, status: str
        ) -> None:
            """Updates the status of an outbound federation message job.



            Args:

                job_id: The ID of the outbound message job.

                status: The new status (e.g., 'delivered', 'failed').

            """

            now = int(time.time())

            with self._db.session() as session:
                message = session.get(OutboundFederationLedger, job_id)

                if message:
                    message.status = status

                    message.last_attempt_at = now

                    session.commit()

        def update_outbound_federation_message_for_retry(
            self, job_id: str, new_attempts: int, retry_at: int
        ) -> None:
            """Updates retry information for a failed outbound federation message job.



            Args:

                job_id: The ID of the outbound message job.

                new_attempts: The new number of retry attempts.

                retry_at: The Unix timestamp for the next retry attempt.

            """

            now = int(time.time())

            with self._db.session() as session:
                message = session.get(OutboundFederationLedger, job_id)

                if message:
                    message.status = "retrying"

                    message.attempts = new_attempts

                    message.retry_at = retry_at

                    message.last_attempt_at = now

                    session.commit()
