import json
from pathlib import Path

from fastapi.testclient import TestClient
from nacl.signing import SigningKey

from chorus_bridge.app import create_app
from chorus_bridge.core import BridgeSettings
from chorus_bridge.schemas import ChorusPost, ModerationEvent


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
    message_data = b"fake-serialized-post"
    signature = signing_key.sign(message_data).signature.hex()
    envelope = {
        "sender_instance": "stage-A",
        "timestamp": 42,
        "message_type": "PostAnnouncement",
        "message_data": message_data.hex(),
        "signature": signature,
    }
    response = client.post(
        "/api/bridge/federation/send",
        data=json.dumps(envelope),
        headers={
            "Content-Type": "application/octet-stream",
            "X-Chorus-Instance-Id": "stage-A",
            "Idempotency-Key": "abc-123",
        },
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "accepted"
    assert body["fingerprint"]
    # duplicate envelope should be rejected
    dup_response = client.post(
        "/api/bridge/federation/send",
        data=json.dumps(envelope),
        headers={
            "Content-Type": "application/octet-stream",
            "X-Chorus-Instance-Id": "stage-A",
            "Idempotency-Key": "abc-123",
        },
    )
    assert dup_response.status_code == 409


def test_activitypub_export_requires_valid_signature(tmp_path: Path) -> None:
    client, signing_key = _make_app(tmp_path)
    post = ChorusPost(
        post_id="deadbeef",
        author_pubkey_hash="cafebabecafebabe",
        body_md="Hello Chorus",
        day_number=2,
        community="public-square",
    )
    post_payload = {
        "chorus_post": post.model_dump(),
        "signature": signing_key.sign(
            json.dumps(post.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).signature.hex(),
    }
    response = client.post(
        "/api/bridge/export",
        json=post_payload,
        headers={"X-Chorus-Instance-Id": "stage-A"},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"


def test_moderation_event_flow(tmp_path: Path) -> None:
    client, signing_key = _make_app(tmp_path)
    event = ModerationEvent(
        target_ref="post:123",
        action="remove",
        reason_hash="aa11bb22cc33dd44",
        creation_day=10,
    )
    moderation_event = {
        "moderation_event": event.model_dump(),
        "signature": signing_key.sign(
            json.dumps(event.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).signature.hex(),
    }
    response = client.post(
        "/api/bridge/moderation/event",
        json=moderation_event,
        headers={"X-Chorus-Instance-Id": "stage-A"},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["event_id"]
    assert body["status"] == "accepted"
