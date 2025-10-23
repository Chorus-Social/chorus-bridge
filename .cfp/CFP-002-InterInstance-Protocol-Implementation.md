# Implementation Plan: CFP-002 Inter-Instance Protocol

Status: Draft
Owners: Federation Platform Team
Scope: Message schema, signing, REST/WebSocket gateway, replay protection

---

## Objectives
- Define a compact, extensible wire format for federation messages.
- Authenticate all inter-instance messages with instance keypairs.
- Provide REST ingestion, WS fanout, and replay/throttle controls.

## Deliverables
- Proto definitions in `proto/chorus/*.proto`.
- Federation gateway routes: `POST /federation/message`, `GET /federation/day-proof/{N}`, `GET /federation/peers}`.
- Signature verification and instance trust store.
- Replay protection keyed by `(sender, message_hash)`.

---

## Schemas

### FederationEnvelope (Proto3)
```
syntax = "proto3";
package chorus;

message FederationEnvelope {
  string sender_instance = 1;
  uint64 timestamp = 2;
  string message_type = 3; // e.g., "PostAnnouncement"
  bytes message_data = 4;  // Embedded type, serialized
  bytes signature = 5;     // Ed25519 over message_data
}

message PostAnnouncement {
  bytes post_id = 1;
  bytes author_pubkey = 2;
  bytes content_hash = 3;
  uint32 order_index = 4;
  int32 creation_day = 5;
}
```

### Canonical Types
- PostAnnouncement
- UserRegistration
- DayProof
- ModerationEvent
- InstanceJoinRequest

---

## Gateway

### REST
- `POST /federation/message`
  - Content-Type: `application/octet-stream` (serialized `FederationEnvelope`)
  - Steps:
    - Parse envelope → validate `message_type`
    - Lookup `sender_instance` pubkey in trust store
    - Verify Ed25519 signature over `message_data`
    - Derive `message_hash` (BLAKE3) for replay cache
    - Enqueue for async processing
  - Responses: 202 on accept, 400/401/403/409 on errors

- `GET /federation/day-proof/{N}`
  - Return canonical proof from validator/DHT cache
  - Response: `application/json` proof object

- `GET /federation/peers`
  - Return configured trusted peers with pubkeys and reachability status

### WebSocket
- `/ws/federation`
  - Emits validated events to peers; optional authenticated subscription

---

## Trust & Keys

### Trust Store
```yaml
federation:
  instance_id: chorus1.example.net
  private_key_path: /etc/chorus/private_ed25519.pem
  trusted_peers:
    - id: chorus2.example.net
      pubkey: hex-encoded-ed25519
    - id: chorus3.example.net
      pubkey: hex-encoded-ed25519
```

### Signature Policy
- Ed25519 over `message_data` bytes.
- Envelope also contains `sender_instance`, `timestamp`, `message_type`.
- Anti-replay: cache `BLAKE3(envelope_bytes)` with TTL.

---

## Processing Pipeline
1. Ingest (REST) → Validate → Enqueue.
2. Worker validates schema based on `message_type`.
3. Side-effects:
   - PostAnnouncement → store/announce post head to feed fanout
   - DayProof → store canonical if threshold met
   - UserRegistration → add known user (if policy allows)
   - ModerationEvent → update moderation queue

---

## Rate Limiting & Replay
- Global and per-peer rate limits (buckets by `sender_instance`).
- Replay cache key: `sender_instance:message_hash` with TTL (e.g., 24h).

---

## Rollout Plan
- Phase 1: Define `.proto`, generate artifacts (no runtime binding yet).
- Phase 2: Add REST ingestion endpoint skeleton (no internal mutations).
- Phase 3: Wire trust store, signature verification, replay cache.
- Phase 4: Implement per-type processors + feature flags per type.

## Testing
- Golden serialized envelopes round-trip tests.
- Signature verification with known test keys.
- Negative tests: bad signature, unknown peer, replay, malformed payload.

## Open Questions
- Envelope timestamp usage policy; day numbers preferred elsewhere.
- Optional mTLS between instances; sequence with HTTP Sig.

