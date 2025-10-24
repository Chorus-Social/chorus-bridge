from chorus_bridge.proto import federation_pb2 as pb2

def test_post_announcement_serialization():
    post = pb2.PostAnnouncement(
        post_id=b"post123",
        author_pubkey=b"author456",
        content_hash=b"content789",
        order_index=1,
        creation_day=100,
    )
    serialized = post.SerializeToString()
    deserialized = pb2.PostAnnouncement.FromString(serialized)

    assert deserialized.post_id == post.post_id
    assert deserialized.author_pubkey == post.author_pubkey
    assert deserialized.content_hash == post.content_hash
    assert deserialized.order_index == post.order_index
    assert deserialized.creation_day == post.creation_day

def test_federation_envelope_with_post_announcement():
    post = pb2.PostAnnouncement(
        post_id=b"post123",
        author_pubkey=b"author456",
        content_hash=b"content789",
        order_index=1,
        creation_day=100,
    )
    envelope = pb2.FederationEnvelope(
        sender_instance="instance_a",
        nonce=1234567890,
        message_type="PostAnnouncement",
        message_data=post.SerializeToString(),
        signature=b"signature_bytes",
    )

    serialized_envelope = envelope.SerializeToString()
    deserialized_envelope = pb2.FederationEnvelope.FromString(serialized_envelope)

    assert deserialized_envelope.sender_instance == envelope.sender_instance
    assert deserialized_envelope.nonce == envelope.nonce
    assert deserialized_envelope.message_type == envelope.message_type
    assert deserialized_envelope.message_data == envelope.message_data
    assert deserialized_envelope.signature == envelope.signature

    # Verify nested message
    deserialized_post = pb2.PostAnnouncement.FromString(deserialized_envelope.message_data)
    assert deserialized_post.post_id == post.post_id

def test_moderation_event_serialization():
    event = pb2.ModerationEvent(
        target_ref=b"target123",
        action="delete",
        reason_hash=b"reason456",
        creation_day=200,
    )
    serialized = event.SerializeToString()
    deserialized = pb2.ModerationEvent.FromString(serialized)

    assert deserialized.target_ref == event.target_ref
    assert deserialized.action == event.action
    assert deserialized.reason_hash == event.reason_hash
    assert deserialized.creation_day == event.creation_day

def test_federation_envelope_with_moderation_event():
    event = pb2.ModerationEvent(
        target_ref=b"target123",
        action="delete",
        reason_hash=b"reason456",
        creation_day=200,
    )
    envelope = pb2.FederationEnvelope(
        sender_instance="instance_b",
        nonce=9876543210,
        message_type="ModerationEvent",
        message_data=event.SerializeToString(),
        signature=b"another_signature",
    )

    serialized_envelope = envelope.SerializeToString()
    deserialized_envelope = pb2.FederationEnvelope.FromString(serialized_envelope)

    assert deserialized_envelope.sender_instance == envelope.sender_instance
    assert deserialized_envelope.nonce == envelope.nonce
    assert deserialized_envelope.message_type == envelope.message_type
    assert deserialized_envelope.message_data == envelope.message_data
    assert deserialized_envelope.signature == envelope.signature

    # Verify nested message
    deserialized_event = pb2.ModerationEvent.FromString(deserialized_envelope.message_data)
    assert deserialized_event.target_ref == event.target_ref

def test_conductor_event_serialization():
    event = pb2.ConductorEvent(
        event_type="test_event",
        epoch=123,
        payload=b"some_payload",
        metadata={"key": "value"},
    )
    serialized = event.SerializeToString()
    deserialized = pb2.ConductorEvent.FromString(serialized)

    assert deserialized.event_type == event.event_type
    assert deserialized.epoch == event.epoch
    assert deserialized.payload == event.payload
    assert deserialized.metadata == event.metadata

def test_day_proof_request_serialization():
    request = pb2.DayProofRequest(day_number=456)
    serialized = request.SerializeToString()
    deserialized = pb2.DayProofRequest.FromString(serialized)

    assert deserialized.day_number == request.day_number

def test_day_proof_response_serialization():
    response = pb2.DayProofResponse(
        day_number=456,
        proof="hex_proof_string",
        proof_hash="hex_proof_hash",
        canonical=True,
        source="conductor",
    )
    serialized = response.SerializeToString()
    deserialized = pb2.DayProofResponse.FromString(serialized)

    assert deserialized.day_number == response.day_number
    assert deserialized.proof == response.proof
    assert deserialized.proof_hash == response.proof_hash
    assert deserialized.canonical == response.canonical
    assert deserialized.source == response.source
