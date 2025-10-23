# Implementation Plan: CFP-009 One-Way ActivityPub Bridge

Status: Draft
Owners: Bridge Team
Scope: One-way export from Chorus to ActivityPub; no inbound federation

---

## Objectives
- Export eligible Chorus content (public posts, communities) to ActivityPub as anonymized actors.
- Maintain strict anonymity: no usernames, no timestamps from Chorus, only pseudonymous actor URIs.
- Block inbound AP ingestion to avoid metadata contamination.

## Non-Goals
- No inbound delivery or AP inbox/outbox processing for remote objects.
- No per-user opt-in UI in this phase (future enhancement).

---

## Architecture

Components:
- Bridge API: receives export events from Chorus instance.
- Identity Mapper: maps Chorus pubkey hash → AP actor URI.
- Policy Guard: checks local moderation state and export allowlist/blocklist.
- AP Adapter: constructs ActivityStreams objects and signs HTTP requests.
- Bridge DB: stores actor mappings and export ledger.

Data Flow:
1) Chorus Instance → `POST /api/bridge/export` with signed export payload.
2) Bridge validates signature, checks policy, translates to ActivityPub object.
3) Bridge AP Adapter sends `Create`/`Note` to target AP instance outbox (HTTP Sig).

---

## Configuration
```yaml
bridge:
  domain: bridge.chorus.social
  genesis_timestamp: 1729670400
  ap_targets:
    - https://mastodon.example/outbox
  db:
    url: postgresql://bridge:password@db:5432/bridge
  http_signature:
    key_id: https://bridge.chorus.social/keys/bridge
    private_key_path: /app/keys/bridge_ap.key
  export:
    include_votes_positive: true
    include_communities: true
    include_dms: false
```

---

## Data Model (SQL DDL)
```sql
CREATE TABLE bridge_actor (
  id BIGSERIAL PRIMARY KEY,
  pubkey_hash CHAR(64) UNIQUE NOT NULL,
  actor_uri TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE bridge_blocklist (
  id BIGSERIAL PRIMARY KEY,
  object_hash CHAR(64) UNIQUE NOT NULL,
  reason TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE export_ledger (
  id BIGSERIAL PRIMARY KEY,
  object_hash CHAR(64) NOT NULL,
  ap_type TEXT NOT NULL,
  target_url TEXT NOT NULL,
  status TEXT NOT NULL,
  last_attempt_at TIMESTAMP,
  attempts INT NOT NULL DEFAULT 0
);
```

---

## Identity Mapping
- Actor URI: `https://{bridge.domain}/actors/{sha256(pubkey_hex)[:16]}`
- One-to-one mapping stored in `bridge_actor`.
- No reverse mapping exported.

---

## Export Endpoint Contract
`POST /api/bridge/export`
```json
{
  "chorus_post": {
    "post_id": "hex",
    "author_pubkey_hash": "hex",
    "body_md": "...",
    "day_number": 1234,
    "community": "optional"
  },
  "signature": "hex"
}
```
Validation:
- Signature verified using instance trust store.
- Check `bridge_blocklist` before processing.

---

## Translation Rules
- Chorus → ActivityStreams
  - Post → `Note` with `attributedTo = actor_uri`.
  - Community creation → `Create` of `Group`.
  - Positive vote → `Like` (optional, feature-flagged).
  - Harmful votes/DMs → not exported.

### Published Timestamp Derivation (no direct timestamps)
- `published = genesis_timestamp + (day_number * 86400) + random_offset(0..86400)`
- Random offset persisted per-object to ensure stability on retries.

---

## ActivityPub Delivery
- HTTP Signature (Cavage) headers using configured key.
- Target outbox URLs configured per AP instance.
- Retries with exponential backoff; record in `export_ledger`.

---

## Security & Privacy
- One-way: inbound endpoints disabled (no inbox).
- No user PII or timestamps exported.
- Moderation state respected; flagged content never exported.

---

## Deployment (Compose)
```yaml
version: "3.8"
services:
  bridge:
    image: chorus/bridge:dev
    ports: ["443:443"]
    environment:
      - BRIDGE_DOMAIN=bridge.chorus.social
      - CHORUS_GENESIS_TIMESTAMP=1729670400
      - DATABASE_URL=postgresql://bridge:password@db:5432/bridge
    depends_on: [db]
    volumes:
      - ./keys:/app/keys
      - ./bridge.yaml:/app/bridge.yaml
  db:
    image: postgres:16
    environment:
      - POSTGRES_DB=bridge
      - POSTGRES_USER=bridge
      - POSTGRES_PASSWORD=password
    volumes:
      - bridge_db:/var/lib/postgresql/data
volumes:
  bridge_db:
```

---

## Rollout Plan
1) Implement DB schema and config plumbing (no runtime code checked in yet).
2) Add Bridge export contract and trust store configuration.
3) Implement translation rules and AP adapter with feature flags (future step).

## Testing
- Golden translation fixtures from Chorus → ActivityStreams JSON.
- HTTP signature validation against a local AP test target.
- Blocklist behavior and retry ledger updates.

## Open Questions
- Multi-target delivery fanout and per-target rate limits.
- Per-user opt-out/in controls and signal path from Chorus UI.

