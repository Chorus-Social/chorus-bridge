import json
from pathlib import Path

from fastapi.testclient import TestClient
from nacl.signing import SigningKey

from chorus_bridge.app import create_app
from chorus_bridge.core import BridgeSettings
from chorus_bridge.proto import federation_pb2 as pb2
from chorus_bridge.schemas import ActivityPubExportRequest, ModerationEventRequest


def _write_trust_store(path: Path, mapping: dict[str, str]) -> None:
    path.write_text(json.dumps({"instances": mapping}), encoding="utf-8")


def _make_app(tmp_path: Path) -> tuple[TestClient, SigningKey]:
    signing_key = SigningKey.generate()
    trust_path = tmp_path / "trust.json"
    _write_trust_store(trust_path, {"stage-A": signing_key.verify_key.encode().hex()})
    db_path = tmp_path / "bridge.db"
    settings = BridgeSettings(
        instance_id="bridge-test",
        trust_store_path=trust_path,
        conductor_mode="memory",
        activitypub_actor_domain="bridge.example",
        database_url=f"sqlite+pysqlite:///{db_path}",
        jwt_enforcement_enabled=True, # Enable JWT enforcement for testing
        jwt_public_key=signing_key.verify_key.encode().hex(), # Use the stage-A key for JWT verification
    )
    app = create_app(settings)
    client = TestClient(app)
    return client, signing_key


def test_day_proof_not_found(tmp_path: Path) -> None:
    client, _ = _make_app(tmp_path)
    response = client.get("/api/bridge/day-proof/1")
    assert response.status_code == 404


def test_federation_send_accepts_valid_envelope(tmp_path: Path) -> None:
    client, signing_key = _make_app(tmp_path)
    
    post_announcement = pb2.PostAnnouncement(
        post_id=b"post123",
        author_pubkey=signing_key.verify_key.encode(),
        content_hash=b"content789",
        order_index=1,
        creation_day=100,
    )
    message_data = post_announcement.SerializeToString()
    
    # Sign the message_data
    signed_message = signing_key.sign(message_data)

    envelope = pb2.FederationEnvelope(
        sender_instance="stage-A",
        nonce=42,
        message_type="PostAnnouncement",
        message_data=message_data,
        signature=signed_message.signature,
    )
    
    serialized_envelope = envelope.SerializeToString()

    response = client.post(
        "/api/bridge/federation/send",
        data=serialized_envelope,
        headers={
            "Content-Type": "application/octet-stream",
            "X-Chorus-Instance-Id": "stage-A",
            "Idempotency-Key": "abc-123",
                "Authorization": f"Bearer {signing_key.sign(b'jwt_payload').signature.hex()}" # Placeholder JWT
        },
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "accepted"
    assert body["fingerprint"]
    
    # duplicate envelope should be rejected
    dup_response = client.post(
        "/api/bridge/federation/send",
        data=serialized_envelope,
        headers={
            "Content-Type": "application/octet-stream",
            "X-Chorus-Instance-Id": "stage-A",
            "Idempotency-Key": "abc-123",
                "Authorization": f"Bearer {signing_key.sign(b'jwt_payload').signature.hex()}" # Placeholder JWT
        },
    )
    assert dup_response.status_code == 409


def test_activitypub_export_requires_valid_signature(tmp_path: Path) -> None:
    client, signing_key = _make_app(tmp_path)
    post_announcement = pb2.PostAnnouncement(
        post_id=b"deadbeef",
        author_pubkey=signing_key.verify_key.encode(),
        content_hash=b"cafebabecafebabe", # This should be a hash of body_md
        order_index=1,
        creation_day=2,
    )
    body_md = "Hello Chorus"
    
    # The signature is over the canonical JSON representation of the request payload
    # which now includes the hex-encoded Protobuf post and body_md.
    request_payload = ActivityPubExportRequest(
        chorus_post=post_announcement.SerializeToString().hex(),
        body_md=body_md,
        signature=b"" # Placeholder, will be signed below
    )
    
    # Canonical JSON for signing
    canonical_json_for_signing = json.dumps(
        {
            "chorus_post": request_payload.chorus_post,
            "body_md": request_payload.body_md,
        },
        sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    post_payload = {
        "chorus_post": request_payload.chorus_post,
        "body_md": request_payload.body_md,
        "signature": signing_key.sign(canonical_json_for_signing).signature.hex(),
    }
    response = client.post(
        "/api/bridge/export",
        json=post_payload,
        headers={
            "X-Chorus-Instance-Id": "stage-A",
                "Authorization": f"Bearer {signing_key.sign(b'jwt_payload').signature.hex()}" # Placeholder JWT
        },
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"


def test_moderation_event_flow(tmp_path: Path) -> None:
    client, signing_key = _make_app(tmp_path)
    moderation_event_pb = pb2.ModerationEvent(
        target_ref=b"post:123",
        action="remove",
        reason_hash=b"aa11bb22cc33dd44",
        creation_day=10,
    )
    
    # Canonical JSON for signing
    canonical_json_for_signing = json.dumps(
        {
            "moderation_event": moderation_event_pb.SerializeToString().hex(),
        },
        sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    moderation_event_payload = {
        "moderation_event": moderation_event_pb.SerializeToString().hex(),
        "signature": signing_key.sign(canonical_json_for_signing).signature.hex(),
    }
    response = client.post(
        "/api/bridge/moderation/event",
        json=moderation_event_payload,
        headers={
            "X-Chorus-Instance-Id": "stage-A",
                "Authorization": f"Bearer {signing_key.sign(b'jwt_payload').signature.hex()}" # Placeholder JWT
        },
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["event_id"]
    assert body["status"] == "accepted"
