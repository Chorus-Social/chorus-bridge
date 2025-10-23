import pytest
import json
import base64
from chorus_bridge.proto.federation_messages import (
    FederationEnvelope,
    PostAnnouncement,
    UserRegistration,
    DayProof,
    ModerationEvent,
    InstanceJoinRequest,
)

def test_post_announcement_serialization():
    post = PostAnnouncement(
        post_id=b"post123",
        author_pubkey=b"author456",
        content_hash=b"content789",
        order_index=1,
        creation_day=100,
    )
    serialized = post.to_bytes()
    deserialized = PostAnnouncement.from_bytes(serialized)

    assert deserialized.post_id == post.post_id
    assert deserialized.author_pubkey == post.author_pubkey
    assert deserialized.content_hash == post.content_hash
    assert deserialized.order_index == post.order_index
    assert deserialized.creation_day == post.creation_day

def test_federation_envelope_with_post_announcement():
    post = PostAnnouncement(
        post_id=b"post123",
        author_pubkey=b"author456",
        content_hash=b"content789",
        order_index=1,
        creation_day=100,
    )
    envelope = FederationEnvelope(
        sender_instance="instance_a",
        timestamp=1234567890,
        message_type="PostAnnouncement",
        message_data=post.to_bytes(),
        signature=b"signature_bytes",
    )

    serialized_envelope = envelope.to_bytes()
    deserialized_envelope = FederationEnvelope.from_bytes(serialized_envelope)

    assert deserialized_envelope.sender_instance == envelope.sender_instance
    assert deserialized_envelope.timestamp == envelope.timestamp
    assert deserialized_envelope.message_type == envelope.message_type
    assert deserialized_envelope.message_data == envelope.message_data
    assert deserialized_envelope.signature == envelope.signature

    deserialized_post = deserialized_envelope.get_message_data_object()
    assert isinstance(deserialized_post, PostAnnouncement)
    assert deserialized_post.post_id == post.post_id

def test_moderation_event_serialization():
    event = ModerationEvent(
        target_ref=b"target123",
        action="delete",
        reason_hash=b"reason456",
        creation_day=200,
    )
    serialized = event.to_bytes()
    deserialized = ModerationEvent.from_bytes(serialized)

    assert deserialized.target_ref == event.target_ref
    assert deserialized.action == event.action
    assert deserialized.reason_hash == event.reason_hash
    assert deserialized.creation_day == event.creation_day

def test_federation_envelope_with_moderation_event():
    event = ModerationEvent(
        target_ref=b"target123",
        action="delete",
        reason_hash=b"reason456",
        creation_day=200,
    )
    envelope = FederationEnvelope(
        sender_instance="instance_b",
        timestamp=9876543210,
        message_type="ModerationEvent",
        message_data=event.to_bytes(),
        signature=b"another_signature",
    )

    serialized_envelope = envelope.to_bytes()
    deserialized_envelope = FederationEnvelope.from_bytes(serialized_envelope)

    assert deserialized_envelope.sender_instance == envelope.sender_instance
    assert deserialized_envelope.timestamp == envelope.timestamp
    assert deserialized_envelope.message_type == envelope.message_type
    assert deserialized_envelope.message_data == envelope.message_data
    assert deserialized_envelope.signature == envelope.signature

    deserialized_event = deserialized_envelope.get_message_data_object()
    assert isinstance(deserialized_event, ModerationEvent)
    assert deserialized_event.target_ref == event.target_ref

def test_set_message_data_object():
    post = PostAnnouncement(
        post_id=b"post_set",
        author_pubkey=b"author_set",
        content_hash=b"content_set",
        order_index=5,
        creation_day=300,
    )
    envelope = FederationEnvelope(
        sender_instance="instance_c",
        timestamp=1122334455,
        message_type="",  # Will be set by set_message_data_object
        message_data=b"",  # Will be set by set_message_data_object
        signature=b"set_signature",
    )

    envelope.set_message_data_object(post)

    assert envelope.message_type == "PostAnnouncement"
    assert envelope.message_data == post.to_bytes()

    retrieved_post = envelope.get_message_data_object()
    assert isinstance(retrieved_post, PostAnnouncement)
    assert retrieved_post.post_id == post.post_id
