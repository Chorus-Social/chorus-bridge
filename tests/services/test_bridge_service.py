import pytest
import time
from unittest.mock import AsyncMock, MagicMock
from nacl.signing import VerifyKey

from chorus_bridge.core.settings import BridgeSettings
from chorus_bridge.core.trust import TrustStore, UnknownInstanceError
from chorus_bridge.db.repository import BridgeRepository
from chorus_bridge.proto.federation_messages import FederationEnvelope, PostAnnouncement, ModerationEvent
from chorus_bridge.schemas import ActivityPubExportRequest, DayProofResponse, ModerationEventRequest, DayProof
from chorus_bridge.services.bridge import (
    BridgeService,
    DuplicateEnvelopeError,
    DuplicateIdempotencyKeyError,
)
from chorus_bridge.services.conductor import ConductorReceipt, InMemoryConductorClient, ConductorEvent
from chorus_bridge.services.activitypub import ActivityPubTranslator


@pytest.fixture
def mock_settings():
    settings = MagicMock(spec=BridgeSettings)
    settings.replay_cache_ttl_seconds = 3600
    settings.idempotency_ttl_seconds = 600
    settings.export_genesis_timestamp = 1729670400
    settings.activitypub_actor_domain = "bridge.chorus.social"
    return settings


@pytest.fixture
def mock_repository():
    repo = MagicMock(spec=BridgeRepository)
    repo.remember_envelope = AsyncMock(return_value=True)
    repo.remember_idempotency_key = AsyncMock(return_value=True)
    repo.enqueue_export = AsyncMock(return_value="job_id_123")
    repo.record_moderation_event = AsyncMock(return_value="event_id_456")
    
    # Mock get_day_proof to return None initially, then a DayProofResponse after upsert
    mock_day_proof_response = DayProofResponse(day_number=1, proof="proof", proof_hash="hash", canonical=True, source="conductor")
    repo.get_day_proof = MagicMock(side_effect=[None, mock_day_proof_response])
    repo.upsert_day_proof = MagicMock()
    return repo


@pytest.fixture
def mock_verify_key():
    # Create a mock VerifyKey object
    verify_key = MagicMock(spec=VerifyKey)
    verify_key.verify = MagicMock()
    return verify_key


@pytest.fixture
def mock_trust_store(mock_verify_key):
    store = MagicMock(spec=TrustStore)
    store.get = MagicMock(return_value=mock_verify_key)
    return store


@pytest.fixture
def mock_conductor_client():
    client = MagicMock(spec=InMemoryConductorClient)
    client.submit_event = AsyncMock(return_value=ConductorReceipt(
        event_type="test", epoch=1, event_hash="hash123"
    ))
    client.get_day_proof = AsyncMock(return_value=DayProof(day_number=1, proof="proof", proof_hash="hash", canonical=True))
    return client


@pytest.fixture
def mock_activitypub_translator(mock_settings):
    translator = MagicMock(spec=ActivityPubTranslator)
    # model_dump_json should return a string, not bytes, for .encode() to work
    mock_note = MagicMock()
    mock_note.model_dump_json.return_value = '{"content":"test"}'
    translator.build_note = MagicMock(return_value=(
        mock_note,
        int(time.time())
    ))
    return translator


@pytest.fixture
def bridge_service(
    mock_settings,
    mock_repository,
    mock_trust_store,
    mock_conductor_client,
    mock_activitypub_translator,
):
    return BridgeService(
        settings=mock_settings,
        repository=mock_repository,
        trust_store=mock_trust_store,
        conductor=mock_conductor_client,
        activitypub_translator=mock_activitypub_translator,
    )


@pytest.mark.asyncio
async def test_get_day_proof_from_conductor(bridge_service, mock_repository, mock_conductor_client):
    result = await bridge_service.get_day_proof(1)
    assert result is not None
    mock_conductor_client.get_day_proof.assert_called_once_with(1)
    mock_repository.upsert_day_proof.assert_called_once()
    mock_repository.get_day_proof.assert_called_with(1)


@pytest.mark.asyncio
async def test_process_federation_envelope_success(bridge_service, mock_repository, mock_trust_store):
    post = PostAnnouncement(
        post_id=b"post123", author_pubkey=b"author456", content_hash=b"content789", order_index=1, creation_day=100
    )
    envelope = FederationEnvelope(
        sender_instance="instance_a",
        timestamp=1234567890,
        message_type="PostAnnouncement",
        message_data=post.to_bytes(),
        signature=b"valid_signature",
    )
    raw_bytes = envelope.to_bytes()

    receipt, fingerprint = await bridge_service.process_federation_envelope(
        raw_bytes=raw_bytes,
        idempotency_key="key123",
        stage_instance="instance_a",
    )

    assert receipt.event_hash == "hash123"
    mock_trust_store.get.assert_called_once_with("instance_a")
    mock_trust_store.get.return_value.verify.assert_called_once()
    mock_repository.remember_envelope.assert_called_once()
    mock_repository.remember_idempotency_key.assert_called_once()
    # mock_conductor_client.submit_event.assert_called_once() # Conductor client is mocked in fixture


@pytest.mark.asyncio
async def test_process_federation_envelope_duplicate_envelope(bridge_service, mock_repository, mock_trust_store):
    mock_repository.remember_envelope.return_value = False
    post = PostAnnouncement(
        post_id=b"post123", author_pubkey=b"author456", content_hash=b"content789", order_index=1, creation_day=100
    )
    envelope = FederationEnvelope(
        sender_instance="instance_a",
        timestamp=1234567890,
        message_type="PostAnnouncement",
        message_data=post.to_bytes(),
        signature=b"valid_signature",
    )
    raw_bytes = envelope.to_bytes()

    with pytest.raises(DuplicateEnvelopeError):
        await bridge_service.process_federation_envelope(
            raw_bytes=raw_bytes,
            idempotency_key="key123",
            stage_instance="instance_a",
        )
    mock_trust_store.get.return_value.verify.assert_called_once()


@pytest.mark.asyncio
async def test_process_federation_envelope_duplicate_idempotency_key(bridge_service, mock_repository, mock_trust_store):
    mock_repository.remember_idempotency_key.return_value = False
    post = PostAnnouncement(
        post_id=b"post123", author_pubkey=b"author456", content_hash=b"content789", order_index=1, creation_day=100
    )
    envelope = FederationEnvelope(
        sender_instance="instance_a",
        timestamp=1234567890,
        message_type="PostAnnouncement",
        message_data=post.to_bytes(),
        signature=b"valid_signature",
    )
    raw_bytes = envelope.to_bytes()

    with pytest.raises(DuplicateIdempotencyKeyError):
        await bridge_service.process_federation_envelope(
            raw_bytes=raw_bytes,
            idempotency_key="key123",
            stage_instance="instance_a",
        )
    mock_trust_store.get.return_value.verify.assert_called_once()


@pytest.mark.asyncio
async def test_queue_activitypub_export_success(bridge_service, mock_repository, mock_trust_store):
    post = PostAnnouncement(
        post_id=b"post123", author_pubkey=b"author456", content_hash=b"content789", order_index=1, creation_day=100
    )
    request = ActivityPubExportRequest(chorus_post=post, signature=b"valid_signature")

    job_id = await bridge_service.queue_activitypub_export(
        request=request,
        stage_instance="instance_a",
    )

    assert job_id == "job_id_123"
    mock_trust_store.get.assert_called_once_with("instance_a")
    mock_trust_store.get.return_value.verify.assert_called_once()
    mock_repository.enqueue_export.assert_called_once()


@pytest.mark.asyncio
async def test_record_moderation_event_success(bridge_service, mock_repository, mock_trust_store):
    event = ModerationEvent(
        target_ref=b"target123", action="delete", reason_hash=b"reason456", creation_day=100
    )
    request = ModerationEventRequest(moderation_event=event, signature=b"valid_signature")

    event_id, receipt = await bridge_service.record_moderation_event(
        request=request,
        stage_instance="instance_a",
    )

    assert event_id == "event_id_456"
    assert receipt.event_hash == "hash123"
    mock_trust_store.get.assert_called_once_with("instance_a")
    mock_trust_store.get.return_value.verify.assert_called_once()
    mock_repository.record_moderation_event.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_verify_key_unknown_instance(bridge_service, mock_trust_store):
    mock_trust_store.get.side_effect = UnknownInstanceError("unknown")
    with pytest.raises(PermissionError, match="unknown instance 'instance_x'"):
        bridge_service._fetch_verify_key("instance_x")
