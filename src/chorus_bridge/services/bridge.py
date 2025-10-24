from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

try:
    from google.protobuf.json_format import MessageToJson
except ImportError:
    MessageToJson = None

try:
    import blake3
except ImportError:
    blake3 = None

try:
    from nacl.signing import VerifyKey
except ImportError:
    VerifyKey = None

from chorus_bridge.core.security import envelope_fingerprint, verify_signature
from chorus_bridge.core.settings import BridgeSettings
from chorus_bridge.core.trust import TrustStore, UnknownInstanceError
from chorus_bridge.db.repository import BridgeRepository
from chorus_bridge.proto import federation_pb2 as pb2
from chorus_bridge.schemas import (
    ActivityPubExportRequest,
    DayProofResponse,
    ModerationEventRequest,
)

from .activitypub import ActivityPubTranslator
from .conductor import (
    ConductorClient,
    ConductorEvent,
    ConductorReceipt,
    InMemoryConductorClient,
)


logger = logging.getLogger(__name__)


class DuplicateEnvelopeError(RuntimeError):
    """Raised when a federation envelope fingerprint already exists."""


class DuplicateIdempotencyKeyError(RuntimeError):
    """Raised when an idempotency key has already been processed."""


def _canonical_model_json(model: Any) -> str:
    """Return a stable JSON representation for signature verification."""
    # For Protobuf messages, we serialize to bytes and then hex encode for a stable string representation
    if hasattr(model, "SerializeToString"):
        return model.SerializeToString().hex()
    # Fallback for Pydantic models if any still exist or are introduced
    return json.dumps(
        model.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )


class BridgeService:
    """Coordinator responsible for high-level Bridge operations.

    The BridgeService is the central orchestrator for the Chorus Bridge, handling:
    - Federation envelope processing and validation
    - Conductor network communication
    - ActivityPub translation and export
    - Trust store management
    - Message routing and delivery

    This service ensures secure, reliable, and efficient communication between
    Chorus Stage instances and the Conductor network.
    """

    def __init__(
        self,
        *,
        settings: BridgeSettings,
        repository: BridgeRepository,
        trust_store: TrustStore,
        conductor: Optional[ConductorClient] = None,
        activitypub_translator: Optional[ActivityPubTranslator] = None,
        libp2p_client: Optional[Any] = None,  # Libp2pBridgeClient not yet implemented
    ) -> None:
        """Initialize the BridgeService with required dependencies.

        Args:
            settings: Configuration settings for the bridge service.
            repository: Database repository for data persistence.
            trust_store: Trust store for verifying federated instances.
            conductor: Conductor client for network communication (optional).
            activitypub_translator: ActivityPub translator for external protocols (optional).
            libp2p_client: libp2p client for peer-to-peer communication (optional).

        Raises:
            ValueError: If required dependencies are not provided.
        """
        self._settings = settings
        self._repository = repository
        self._trust_store = trust_store
        self._conductor = conductor or InMemoryConductorClient()
        self._translator = activitypub_translator or ActivityPubTranslator(
            genesis_timestamp=settings.export_genesis_timestamp,
            actor_domain=settings.activitypub_actor_domain,
        )
        self._libp2p_client = libp2p_client
        self._message_handlers: Dict[str, Callable[[str, Any], Awaitable[None]]] = {}
        if settings.federation_post_announce_enabled:
            self._message_handlers["PostAnnouncement"] = self._handle_post_announcement
        if settings.federation_user_registration_enabled:
            self._message_handlers["UserRegistration"] = self._handle_user_registration
        if settings.federation_day_proof_consumption_enabled:
            self._message_handlers["DayProof"] = self._handle_day_proof_message
        if settings.federation_moderation_events_enabled:
            self._message_handlers["ModerationEvent"] = (
                self._handle_moderation_event_message
            )
        if settings.federation_community_creation_enabled:
            self._message_handlers["CommunityCreation"] = (
                self._handle_community_creation
            )
        if settings.federation_user_update_enabled:
            self._message_handlers["UserUpdate"] = self._handle_user_update
        if settings.federation_community_update_enabled:
            self._message_handlers["CommunityUpdate"] = self._handle_community_update
        if settings.federation_community_membership_update_enabled:
            self._message_handlers["CommunityMembershipUpdate"] = (
                self._handle_community_membership_update
            )
        self._message_handlers["BlacklistUpdate"] = self._handle_blacklist_update
        # InstanceJoinRequest is not explicitly feature-flagged in CFP-006, so it's always enabled for now
        self._message_handlers["InstanceJoinRequest"] = (
            self._handle_instance_join_request
        )

    # Day proofs ------------------------------------------------------------

    async def get_day_proof(self, day_number: int) -> Optional[DayProofResponse]:
        """Retrieves a day proof, first from local cache, then from Conductor.

        Args:
            day_number: The day number for which to retrieve the proof.

        Returns:
            An Optional DayProofResponse object.
        """
        stored = self._repository.get_day_proof(day_number)
        if stored:
            return stored
        proof = await self._conductor.get_day_proof(day_number)
        if proof:
            self._repository.upsert_day_proof(proof, source="conductor")
            return self._repository.get_day_proof(day_number)
        return None

    async def record_day_proof(self, proof_json: str) -> ConductorReceipt:
        """Records a day proof by submitting it to the Conductor network.

        Args:
            proof_json: The JSON string representation of the day proof.

        Returns:
            A ConductorReceipt for the submitted event.
        """
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
        envelope: pb2.FederationEnvelope,
        idempotency_key: Optional[str],
        stage_instance: str,
    ) -> Tuple[ConductorReceipt, str]:
        """Processes an incoming federation envelope, including validation, replay protection, and dispatching.

        Args:
            envelope: The Protobuf FederationEnvelope.
            idempotency_key: An optional idempotency key for the request.
            stage_instance: The ID of the Chorus Stage instance sending the envelope.

        Returns:
            A tuple containing the ConductorReceipt and the envelope fingerprint.

        Raises:
            ValueError: If the envelope bytes are invalid.
            PermissionError: If signature verification fails or the sender is unknown.
            DuplicateEnvelopeError: If the envelope is a replay.
            DuplicateIdempotencyKeyError: If the idempotency key has been used before.
        """
        logger.info(
            "Received FederationEnvelope from %s with message_type %s",
            envelope.sender_instance,
            envelope.message_type,
        )

        try:
            verify_key = self._fetch_verify_key(envelope.sender_instance)
            verify_signature(envelope.message_data, envelope.signature, verify_key)
            logger.debug(
                "Signature verified for envelope from %s", envelope.sender_instance
            )
        except PermissionError as exc:
            logger.warning(
                "Signature verification failed for %s: %s",
                envelope.sender_instance,
                exc,
            )  # ALERT: Federation signature failure
            raise exc
        except Exception as exc:
            logger.error(
                "Unexpected error during signature verification for %s: %s",
                envelope.sender_instance,
                exc,
            )  # ALERT: Unexpected signature verification error
            raise exc

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
            logger.warning(
                "Duplicate FederationEnvelope received from %s with fingerprint %s",
                envelope.sender_instance,
                fingerprint,
            )  # ALERT: Replay cache hit
            raise DuplicateEnvelopeError(fingerprint)

        if idempotency_key:
            if not self._repository.remember_idempotency_key(
                stage_instance,
                idempotency_key,
                self._settings.idempotency_ttl_seconds,
            ):
                logger.warning(
                    "Duplicate idempotency key %s for instance %s",
                    idempotency_key,
                    stage_instance,
                )  # ALERT: Idempotency key replay
                raise DuplicateIdempotencyKeyError(idempotency_key)

        event = ConductorEvent(
            event_type="federation_envelope",
            epoch=self._derive_epoch(envelope),
            payload=envelope.message_data,
            metadata={
                "sender_instance": envelope.sender_instance,
                "message_type": envelope.message_type,
            },
        )
        receipt = await self._conductor.submit_event(event)
        logger.info(
            "FederationEnvelope from %s submitted to Conductor. Receipt: %s",
            envelope.sender_instance,
            receipt.event_hash,
        )

        # Publish to libp2p gossipsub for other Bridges
        if self._libp2p_client:
            await self._libp2p_client.publish_federation_envelope(
                envelope, envelope.nonce
            )  # Using nonce as day_number for topic for now

        # Process the specific message type
        message_type_map = {
            "PostAnnouncement": pb2.PostAnnouncement,
            "UserRegistration": pb2.UserRegistration,
            "DayProof": pb2.DayProof,
            "ModerationEvent": pb2.ModerationEvent,
            "InstanceJoinRequest": pb2.InstanceJoinRequest,
            "CommunityCreation": pb2.CommunityCreation,
            "UserUpdate": pb2.UserUpdate,
            "CommunityUpdate": pb2.CommunityUpdate,
            "CommunityMembershipUpdate": pb2.CommunityMembershipUpdate,
            "BlacklistUpdate": pb2.BlacklistUpdate,
        }
        message_cls = message_type_map.get(envelope.message_type)
        if not message_cls:
            logger.warning(
                "Unknown message_type: %s. Cannot deserialize message_data.",
                envelope.message_type,
            )
            message_object = None  # Or handle as an error
        else:
            message_object = message_cls.FromString(envelope.message_data)
        handler = self._message_handlers.get(envelope.message_type)
        if handler:
            await handler(envelope.sender_instance, message_object)
        else:
            logger.warning(
                "No specific handler for message_type: %s. Envelope relayed to Conductor only.",
                envelope.message_type,
            )

        return receipt, fingerprint

    async def _handle_post_announcement(
        self, sender_instance: str, message: pb2.PostAnnouncement
    ):
        """Handles a PostAnnouncement message by saving the federated post and enqueuing it for outbound federation."""
        logger.info(
            "Handling PostAnnouncement from %s: %s",
            sender_instance,
            message.post_id.hex(),
        )
        self._repository.save_federated_post(sender_instance, message)
        logger.info(
            "Federated post %s saved from %s.", message.post_id.hex(), sender_instance
        )

        # Enqueue for outbound federation to other Stages
        for target_stage_url in self._settings.federation_target_stages:
            # Reconstruct the original FederationEnvelope for outbound push
            # This assumes the original envelope is what needs to be pushed.
            # In a real scenario, you might construct a new envelope with Bridge's signature.
            # Generate a deterministic nonce for outbound envelope to ensure replay protection and anonymity.
            # The nonce should be unique per message and deterministic.
            # Using a hash of post_id, creation_day, and order_index.
            deterministic_nonce_data = f"{message.post_id.hex()}-{message.creation_day}-{message.order_index}".encode(
                "utf-8"
            )
            deterministic_nonce = int.from_bytes(
                blake3.blake3(deterministic_nonce_data).digest()[:8], "big"
            )  # Use first 8 bytes for uint64

            outbound_envelope = pb2.FederationEnvelope(
                sender_instance=sender_instance,
                nonce=deterministic_nonce,
                message_type="PostAnnouncement",
                message_data=message.SerializeToString(),
                signature=b"",  # Signature will be added by OutboundFederationWorker
            )
            self._repository.enqueue_outbound_federation_message(
                target_instance_url=target_stage_url,
                message_type="PostAnnouncement",
                raw_envelope=outbound_envelope.SerializeToString(),
            )
            logger.info(
                "PostAnnouncement %s enqueued for outbound federation to %s.",
                message.post_id.hex(),
                target_stage_url,
            )

    async def _handle_user_registration(
        self, sender_instance: str, message: pb2.UserRegistration
    ):
        """Handles a UserRegistration message by saving the registered user and enqueuing it for outbound federation."""
        logger.info(
            "Handling UserRegistration from %s: %s",
            sender_instance,
            message.user_pubkey.hex(),
        )
        self._repository.save_registered_user(sender_instance, message)
        logger.info(
            "User %s registered from %s saved.",
            message.user_pubkey.hex(),
            sender_instance,
        )

        # Enqueue for outbound federation to other Stages
        for target_stage_url in self._settings.federation_target_stages:
            deterministic_nonce_data = (
                f"{message.user_pubkey.hex()}-{message.registration_day}".encode(
                    "utf-8"
                )
            )
            deterministic_nonce = int.from_bytes(
                blake3.blake3(deterministic_nonce_data).digest()[:8], "big"
            )

            outbound_envelope = pb2.FederationEnvelope(
                sender_instance=sender_instance,
                nonce=deterministic_nonce,
                message_type="UserRegistration",
                message_data=message.SerializeToString(),
                signature=b"",
            )
            self._repository.enqueue_outbound_federation_message(
                target_instance_url=target_stage_url,
                message_type="UserRegistration",
                raw_envelope=outbound_envelope.SerializeToString(),
            )
            logger.info(
                "UserRegistration for %s enqueued for outbound federation to %s.",
                message.user_pubkey.hex(),
                target_stage_url,
            )

    async def _handle_day_proof_message(
        self, sender_instance: str, message: pb2.DayProof
    ):
        """Handles a DayProof message by updating the local day proof cache and enqueuing it for outbound federation."""
        logger.info(
            "Handling DayProof from %s: day %s, hash %s",
            sender_instance,
            message.day_number,
            message.canonical_proof_hash.hex(),
        )
        # The Bridge already fetches canonical proofs from Conductor. This handler can be used
        # to update the local cache if a new canonical proof is received from a trusted peer.
        # For now, we'll just upsert it into the repository.
        day_proof_response = DayProofResponse(
            day_number=message.day_number,
            proof="",  # The full proof is not in this message, only hash
            proof_hash=message.canonical_proof_hash.hex(),
            canonical=True,
            source=sender_instance,
        )
        self._repository.upsert_day_proof(day_proof_response, source=sender_instance)
        logger.info(
            "Day proof for day %s from %s updated in local cache.",
            message.day_number,
            sender_instance,
        )

        # Enqueue for outbound federation to other Stages
        for target_stage_url in self._settings.federation_target_stages:
            deterministic_nonce_data = (
                f"{message.day_number}-{message.canonical_proof_hash.hex()}".encode(
                    "utf-8"
                )
            )
            deterministic_nonce = int.from_bytes(
                blake3.blake3(deterministic_nonce_data).digest()[:8], "big"
            )

            outbound_envelope = pb2.FederationEnvelope(
                sender_instance=sender_instance,
                nonce=deterministic_nonce,
                message_type="DayProof",
                message_data=message.SerializeToString(),
                signature=b"",
            )
            self._repository.enqueue_outbound_federation_message(
                target_instance_url=target_stage_url,
                message_type="DayProof",
                raw_envelope=outbound_envelope.SerializeToString(),
            )
            logger.info(
                "DayProof for day %s enqueued for outbound federation to %s.",
                message.day_number,
                target_stage_url,
            )

    async def _handle_moderation_event_message(
        self, sender_instance: str, message: pb2.ModerationEvent
    ):
        """Handles a ModerationEvent message by recording the moderation event and enqueuing it for outbound federation."""
        logger.info(
            "Handling ModerationEvent from %s: target %s, action %s",
            sender_instance,
            message.target_ref.hex(),
            message.action,
        )
        # The Bridge already has a record_moderation_event method that handles submission to Conductor.
        # This handler can simply record the event locally.
        self._repository.record_moderation_event(
            stage_instance=sender_instance,
            target_ref=message.target_ref,
            action=message.action,
            reason_hash=message.reason_hash,
            creation_day=message.creation_day,
            raw_payload=message.SerializeToString(),
        )
        logger.info(
            "Moderation event for target %s from %s recorded.",
            message.target_ref.hex(),
            sender_instance,
        )

        # Enqueue for outbound federation to other Stages
        for target_stage_url in self._settings.federation_target_stages:
            deterministic_nonce_data = f"{message.target_ref.hex()}-{message.action}-{message.creation_day}".encode(
                "utf-8"
            )
            deterministic_nonce = int.from_bytes(
                blake3.blake3(deterministic_nonce_data).digest()[:8], "big"
            )

            outbound_envelope = pb2.FederationEnvelope(
                sender_instance=sender_instance,
                nonce=deterministic_nonce,
                message_type="ModerationEvent",
                message_data=message.SerializeToString(),
                signature=b"",
            )
            self._repository.enqueue_outbound_federation_message(
                target_instance_url=target_stage_url,
                message_type="ModerationEvent",
                raw_envelope=outbound_envelope.SerializeToString(),
            )
            logger.info(
                "ModerationEvent for target %s enqueued for outbound federation to %s.",
                message.target_ref.hex(),
                target_stage_url,
            )

    async def _handle_instance_join_request(
        self, sender_instance: str, message: pb2.InstanceJoinRequest
    ):
        """Handles an InstanceJoinRequest message by updating the trust store and enqueuing it for outbound federation."""
        logger.info(
            "Handling InstanceJoinRequest from %s: instance %s",
            sender_instance,
            message.instance_id,
        )
        # Update trust store with the new instance's public key
        self._trust_store.add_trusted_peer(message.instance_id, message.instance_pubkey)
        logger.info(
            "Instance %s added to trust store with public key %s.",
            message.instance_id,
            message.instance_pubkey.hex(),
        )
        # TODO: Implement logic for manual approval flow if required

        # Enqueue for outbound federation to other Stages
        for target_stage_url in self._settings.federation_target_stages:
            deterministic_nonce_data = (
                f"{message.instance_id}-{message.timestamp}".encode("utf-8")
            )
            deterministic_nonce = int.from_bytes(
                blake3.blake3(deterministic_nonce_data).digest()[:8], "big"
            )

            outbound_envelope = pb2.FederationEnvelope(
                sender_instance=sender_instance,
                nonce=deterministic_nonce,
                message_type="InstanceJoinRequest",
                message_data=message.SerializeToString(),
                signature=b"",
            )
            self._repository.enqueue_outbound_federation_message(
                target_instance_url=target_stage_url,
                message_type="InstanceJoinRequest",
                raw_envelope=outbound_envelope.SerializeToString(),
            )
            logger.info(
                "InstanceJoinRequest for %s enqueued for outbound federation to %s.",
                message.instance_id,
                target_stage_url,
            )

    async def _handle_community_creation(
        self, sender_instance: str, message: pb2.CommunityCreation
    ):
        """Handles a CommunityCreation message by saving the federated community and enqueuing it for outbound federation."""
        logger.info(
            "Handling CommunityCreation from %s: community %s, name %s",
            sender_instance,
            message.community_id.hex(),
            message.name,
        )
        self._repository.save_federated_community(sender_instance, message)
        logger.info(
            "Federated community %s saved from %s.",
            message.community_id.hex(),
            sender_instance,
        )

        # Enqueue for outbound federation to other Stages
        for target_stage_url in self._settings.federation_target_stages:
            deterministic_nonce_data = (
                f"{message.community_id.hex()}-{message.creation_day}".encode("utf-8")
            )
            deterministic_nonce = int.from_bytes(
                blake3.blake3(deterministic_nonce_data).digest()[:8], "big"
            )

            outbound_envelope = pb2.FederationEnvelope(
                sender_instance=sender_instance,
                nonce=deterministic_nonce,
                message_type="CommunityCreation",
                message_data=message.SerializeToString(),
                signature=b"",
            )
            self._repository.enqueue_outbound_federation_message(
                target_instance_url=target_stage_url,
                message_type="CommunityCreation",
                raw_envelope=outbound_envelope.SerializeToString(),
            )
            logger.info(
                "CommunityCreation for %s enqueued for outbound federation to %s.",
                message.community_id.hex(),
                target_stage_url,
            )

    async def _handle_user_update(self, sender_instance: str, message: pb2.UserUpdate):
        """Handles a UserUpdate message by saving the federated user update and enqueuing it for outbound federation."""
        logger.info(
            "Handling UserUpdate from %s: user %s",
            sender_instance,
            message.user_pubkey.hex(),
        )
        self._repository.save_federated_user_update(sender_instance, message)
        logger.info(
            "Federated user update for %s saved from %s.",
            message.user_pubkey.hex(),
            sender_instance,
        )

        # Enqueue for outbound federation to other Stages
        for target_stage_url in self._settings.federation_target_stages:
            deterministic_nonce_data = (
                f"{message.user_pubkey.hex()}-{message.update_day}".encode("utf-8")
            )
            deterministic_nonce = int.from_bytes(
                blake3.blake3(deterministic_nonce_data).digest()[:8], "big"
            )

            outbound_envelope = pb2.FederationEnvelope(
                sender_instance=sender_instance,
                nonce=deterministic_nonce,
                message_type="UserUpdate",
                message_data=message.SerializeToString(),
                signature=b"",
            )
            self._repository.enqueue_outbound_federation_message(
                target_instance_url=target_stage_url,
                message_type="UserUpdate",
                raw_envelope=outbound_envelope.SerializeToString(),
            )
            logger.info(
                "UserUpdate for %s enqueued for outbound federation to %s.",
                message.user_pubkey.hex(),
                target_stage_url,
            )

    async def _handle_community_update(
        self, sender_instance: str, message: pb2.CommunityUpdate
    ):
        """Handles a CommunityUpdate message by saving the federated community update and enqueuing it for outbound federation."""
        logger.info(
            "Handling CommunityUpdate from %s: community %s",
            sender_instance,
            message.community_id.hex(),
        )
        self._repository.save_federated_community_update(sender_instance, message)
        logger.info(
            "Federated community update for %s saved from %s.",
            message.community_id.hex(),
            sender_instance,
        )

        # Enqueue for outbound federation to other Stages
        for target_stage_url in self._settings.federation_target_stages:
            deterministic_nonce_data = (
                f"{message.community_id.hex()}-{message.update_day}".encode("utf-8")
            )
            deterministic_nonce = int.from_bytes(
                blake3.blake3(deterministic_nonce_data).digest()[:8], "big"
            )

            outbound_envelope = pb2.FederationEnvelope(
                sender_instance=sender_instance,
                nonce=deterministic_nonce,
                message_type="CommunityUpdate",
                message_data=message.SerializeToString(),
                signature=b"",
            )
            self._repository.enqueue_outbound_federation_message(
                target_instance_url=target_stage_url,
                message_type="CommunityUpdate",
                raw_envelope=outbound_envelope.SerializeToString(),
            )
            logger.info(
                "CommunityUpdate for %s enqueued for outbound federation to %s.",
                message.community_id.hex(),
                target_stage_url,
            )

    async def _handle_community_membership_update(
        self, sender_instance: str, message: pb2.CommunityMembershipUpdate
    ):
        """Handles a CommunityMembershipUpdate message by saving the federated membership update and enqueuing it for outbound federation."""
        logger.info(
            "Handling CommunityMembershipUpdate from %s: community %s, user %s, action %s",
            sender_instance,
            message.community_id.hex(),
            message.user_pubkey.hex(),
            message.action,
        )
        self._repository.save_federated_community_membership(sender_instance, message)
        logger.info(
            "Federated community membership update for community %s, user %s saved from %s.",
            message.community_id.hex(),
            message.user_pubkey.hex(),
            sender_instance,
        )

        # Enqueue for outbound federation to other Stages
        for target_stage_url in self._settings.federation_target_stages:
            deterministic_nonce_data = f"{message.community_id.hex()}-{message.user_pubkey.hex()}-{message.action}-{message.update_day}".encode(
                "utf-8"
            )
            deterministic_nonce = int.from_bytes(
                blake3.blake3(deterministic_nonce_data).digest()[:8], "big"
            )

            outbound_envelope = pb2.FederationEnvelope(
                sender_instance=sender_instance,
                nonce=deterministic_nonce,
                message_type="CommunityMembershipUpdate",
                message_data=message.SerializeToString(),
                signature=b"",
            )
            self._repository.enqueue_outbound_federation_message(
                target_instance_url=target_stage_url,
                message_type="CommunityMembershipUpdate",
                raw_envelope=outbound_envelope.SerializeToString(),
            )
            logger.info(
                "CommunityMembershipUpdate for community %s, user %s enqueued for outbound federation to %s.",
                message.community_id.hex(),
                message.user_pubkey.hex(),
                target_stage_url,
            )

    async def _handle_community_membership_update(
        self, sender_instance: str, message: pb2.CommunityMembershipUpdate
    ):
        """Handles a CommunityMembershipUpdate message by saving the federated membership update and enqueuing it for outbound federation."""
        logger.info(
            "Handling CommunityMembershipUpdate from %s: community %s, user %s, action %s",
            sender_instance,
            message.community_id.hex(),
            message.user_pubkey.hex(),
            message.action,
        )
        self._repository.save_federated_community_membership(sender_instance, message)
        logger.info(
            "Federated community membership update for community %s, user %s saved from %s.",
            message.community_id.hex(),
            message.user_pubkey.hex(),
            sender_instance,
        )

        # Enqueue for outbound federation to other Stages
        for target_stage_url in self._settings.federation_target_stages:
            deterministic_nonce_data = f"{message.community_id.hex()}-{message.user_pubkey.hex()}-{message.action}-{message.update_day}".encode(
                "utf-8"
            )
            deterministic_nonce = int.from_bytes(
                blake3.blake3(deterministic_nonce_data).digest()[:8], "big"
            )

            outbound_envelope = pb2.FederationEnvelope(
                sender_instance=sender_instance,
                nonce=deterministic_nonce,
                message_type="CommunityMembershipUpdate",
                message_data=message.SerializeToString(),
                signature=b"",
            )
            self._repository.enqueue_outbound_federation_message(
                target_instance_url=target_stage_url,
                message_type="CommunityMembershipUpdate",
                raw_envelope=outbound_envelope.SerializeToString(),
            )
            logger.info(
                "CommunityMembershipUpdate for community %s, user %s enqueued for outbound federation to %s.",
                message.community_id.hex(),
                message.user_pubkey.hex(),
                target_stage_url,
            )

    async def _handle_blacklist_update(
        self, sender_instance: str, message: pb2.BlacklistUpdate
    ):
        """Handles a BlacklistUpdate message by updating the local trust store."""
        logger.info(
            "Handling BlacklistUpdate from %s: instance %s, action %s",
            sender_instance,
            message.instance_id,
            message.action,
        )
        if message.action == "add":
            self._trust_store.remove_trusted_peer(message.instance_id)
            logger.info(
                "Instance %s removed from trust store due to blacklist update.",
                message.instance_id,
            )
        elif message.action == "remove":
            # Re-adding a peer would require a full re-evaluation of trust,
            # potentially involving a new InstanceJoinRequest and consensus.
            # For now, we only support adding to blacklist, not un-blacklisting via this message.
            logger.warning(
                "Received un-blacklist request for %s, which is not supported via BlacklistUpdate.",
                message.instance_id,
            )
        else:
            logger.warning(
                "Unknown blacklist action: %s from %s.", message.action, sender_instance
            )

    # ActivityPub -----------------------------------------------------------

    async def queue_activitypub_export(
        self,
        *,
        request: ActivityPubExportRequest,
        stage_instance: str,
    ) -> str:
        """Enqueues an ActivityPub export job.

        Args:
            request: The ActivityPubExportRequest containing the Chorus content to export.
            stage_instance: The ID of the Chorus Stage instance initiating the export.

        Returns:
            The job ID of the enqueued export.
        """
        chorus_post = pb2.PostAnnouncement.FromString(
            bytes.fromhex(request.chorus_post)
        )
        verify_key = self._fetch_verify_key(stage_instance)
        verify_signature(
            _canonical_model_json(chorus_post).encode("utf-8"),
            request.signature,
            verify_key,
        )
        note, published_ts = self._translator.build_note(chorus_post, request.body_md)
        job_id = self._repository.enqueue_export(
            stage_instance=stage_instance,
            object_hash=chorus_post.post_id,  # Using post_id as object_hash for now
            ap_type="Note",  # Assuming Note for posts
            target_url="",  # This needs to be determined or passed
            status="queued",
            published_ts=published_ts,
            raw_payload=request.model_dump_json().encode("utf-8"),
        )
        event = ConductorEvent(
            event_type="activitypub_export",
            epoch=self._derive_epoch(chorus_post),
            payload=note.model_dump_json(by_alias=True).encode("utf-8"),
            metadata={
                "stage_instance": stage_instance,
                "post_id": chorus_post.post_id.hex(),
            },
        )
        await self._conductor.submit_event(event)
        logger.info(
            "ActivityPub export for post %s from %s enqueued.",
            chorus_post.post_id.hex(),
            stage_instance,
        )
        return job_id

    # Moderation ------------------------------------------------------------

    async def record_moderation_event(
        self,
        *,
        request: ModerationEventRequest,
        stage_instance: str,
    ) -> Tuple[str, ConductorReceipt]:
        """Records a moderation event and submits it to the Conductor network.

        Args:
            request: The ModerationEventRequest containing the moderation event details.
            stage_instance: The ID of the Chorus Stage instance initiating the event.

        Returns:
            A tuple containing the event ID and the ConductorReceipt.
        """
        moderation_event = pb2.ModerationEvent.FromString(
            bytes.fromhex(request.moderation_event)
        )
        verify_key = self._fetch_verify_key(stage_instance)
        verify_signature(
            _canonical_model_json(moderation_event).encode("utf-8"),
            request.signature,
            verify_key,
        )
        event_id = self._repository.record_moderation_event(
            stage_instance=stage_instance,
            target_ref=moderation_event.target_ref,
            action=moderation_event.action,
            reason_hash=moderation_event.reason_hash,
            creation_day=moderation_event.creation_day,
            raw_payload=moderation_event.SerializeToString(),
        )
        receipt = await self._conductor.submit_event(
            ConductorEvent(
                event_type="moderation_event",
                epoch=self._derive_epoch(moderation_event),
                payload=moderation_event.SerializeToString(),
                metadata={"stage_instance": stage_instance, "event_id": event_id},
            )
        )
        logger.info(
            "Moderation event %s from %s recorded and submitted to Conductor.",
            event_id,
            stage_instance,
        )
        return event_id, receipt

    # Internal --------------------------------------------------------------

    def _fetch_verify_key(self, instance_id: str) -> VerifyKey:
        """Fetches the Ed25519 VerifyKey for a given instance ID from the trust store.

        Args:
            instance_id: The ID of the instance.

        Returns:
            The VerifyKey for the instance.

        Raises:
            PermissionError: If the instance ID is not found in the trust store.
        """
        try:
            key = self._trust_store.get(instance_id)
            logger.debug("Fetched verify key for instance %s", instance_id)
            return key
        except UnknownInstanceError as exc:
            logger.warning(
                "Attempted to fetch verify key for unknown instance %s", instance_id
            )  # ALERT: Unknown instance attempting federation
            raise PermissionError(f"unknown instance '{instance_id}'") from exc

    def _derive_epoch(self, message) -> int:
        """Derives the Conductor epoch from the message's creation_day or a default."""
        # Handle FederationEnvelope
        if hasattr(message, "message_type") and hasattr(message, "message_data"):
            # Attempt to get creation_day from the inner message
            message_object = None
            try:
                message_type_map = {
                    "PostAnnouncement": pb2.PostAnnouncement,
                    "UserRegistration": pb2.UserRegistration,
                    "DayProof": pb2.DayProof,
                    "ModerationEvent": pb2.ModerationEvent,
                    "InstanceJoinRequest": pb2.InstanceJoinRequest,
                    "CommunityCreation": pb2.CommunityCreation,
                    "UserUpdate": pb2.UserUpdate,
                    "CommunityUpdate": pb2.CommunityUpdate,
                    "CommunityMembershipUpdate": pb2.CommunityMembershipUpdate,
                }
                message_cls = message_type_map.get(message.message_type)
                if message_cls:
                    message_object = message_cls.FromString(message.message_data)
            except Exception as e:
                logger.warning(
                    "Could not deserialize inner message for epoch derivation: %s", e
                )
        else:
            # Handle direct message objects (like ModerationEvent)
            message_object = message

        if hasattr(message_object, "creation_day") and isinstance(
            message_object.creation_day, int
        ):
            return message_object.creation_day
        elif hasattr(message_object, "registration_day") and isinstance(
            message_object.registration_day, int
        ):
            return message_object.registration_day
        elif hasattr(message_object, "update_day") and isinstance(
            message_object.update_day, int
        ):
            return message_object.update_day
        elif hasattr(message_object, "day_number") and isinstance(
            message_object.day_number, int
        ):
            return message_object.day_number

        # Fallback: Raise an error if no day is available, as real-world timestamps are forbidden.
        message_type = getattr(message, "message_type", type(message).__name__)
        raise ValueError(
            f"Cannot derive epoch for message type {message_type}: No day information found."
        )

    def get_trusted_peers_info(self) -> Dict[str, str]:
        """Returns a dictionary mapping instance IDs to their hex-encoded public keys from the TrustStore."""
        return self._trust_store.get_trusted_peers_info()


__all__ = [
    "BridgeService",
    "DuplicateEnvelopeError",
    "DuplicateIdempotencyKeyError",
]
