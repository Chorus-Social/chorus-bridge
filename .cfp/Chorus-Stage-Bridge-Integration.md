# Chorus Stage ↔ Chorus Bridge Integration Contract

Status: Draft
Owners: Platform, API, Security
Scope: Define how Chorus Stage communicates with the separate Chorus Bridge service.

---

## Rationale
Chorus Bridge will own federation concerns (validator network, DHT, hashgraph anchoring, ActivityPub export). Chorus Stage remains focused on runtime APIs and core product flows. This document specifies the service-to-service contracts, configs, and rollout to enable Stage to call Bridge without introducing tight coupling.

---

## Integration Model

- Topology: One Bridge per deployment (can be shared by multiple Stage instances within an operator boundary).
- Directionality: Stage only initiates requests to Bridge. No Bridge-initiated callbacks in Phase 1 (webhooks optional in Phase 2).
- Privacy: Stage sends only day numbers, hashes, and anonymized identifiers. No timestamps exchanged.
- Security: mTLS or signed JWT for S2S. Secondary verification via Bridge JWKS or pinned public key.

---

## Use Cases and Endpoints

1) Canonical Day Proof Retrieval
- Purpose: Stage validates account age and ordering.
- Method: `GET {BRIDGE_BASE_URL}/api/bridge/day-proof/{day}`
- Response (200):
```json
{
  "day_number": 1234,
  "proof": "hex",
  "canonical": true,
  "proof_hash": "hex"
}
```
- Errors: 404 (not available), 502 (upstream consensus issue), 429 (rate limit)

2) Federation Message Relay (Bridge-owned federation layer)
- Purpose: Stage relays `FederationEnvelope` to peers via Bridge.
- Method: `POST {BRIDGE_BASE_URL}/api/bridge/federation/send`
- Headers: `Idempotency-Key: <uuid>`, `Content-Type: application/octet-stream`
- Body: serialized `FederationEnvelope` (see CFP-002)
- Responses: 202 (accepted), 400/401/403/409 as appropriate

3) ActivityPub Export (One-way)
- Purpose: Export eligible public content from Stage to Fediverse via Bridge (see CFP-009).
- Method: `POST {BRIDGE_BASE_URL}/api/bridge/export`
- Body (JSON):
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
- Responses: 202 (queued), 409 (blocked by policy), 422 (schema)

4) Moderation Event Anchoring (optional)
- Purpose: Bridge anchors moderation or dispute events to hashgraph.
- Method: `POST {BRIDGE_BASE_URL}/api/bridge/moderation/event`
- Body: Minimal event object with hashes only.

---

## Authentication & Security

### Phase 1 (Recommended)
- mTLS between Stage and Bridge (mutual certificates issued by operator CA).
- Additionally, Stage signs each request with a short-lived S2S JWT:
  - Header `Authorization: Bearer <jwt>`
  - Claims: `iss` (stage instance id), `aud` (bridge), `exp` (+5 min), `jti` (nonce)
  - JWT signed by Stage private key; Bridge validates via JWKS or pinned pubkey.

### Headers
- `X-Chorus-Instance-Id: <stage_instance_id>`
- `Idempotency-Key: <uuid>` for POSTs

### Replay Protection
- Bridge rejects duplicate `Idempotency-Key` for the same `X-Chorus-Instance-Id` within TTL.

---

## Configuration (Stage)

Environment variables:
```sh
CHORUS_BRIDGE_ENABLED=true
CHORUS_BRIDGE_BASE_URL=https://bridge.local
CHORUS_BRIDGE_INSTANCE_ID=stage-1
CHORUS_BRIDGE_MTLS_ENABLED=true
CHORUS_BRIDGE_JWKS_URL=https://bridge.local/.well-known/jwks.json
CHORUS_BRIDGE_JWT_ISS=stage-1
CHORUS_BRIDGE_JWT_AUD=chorus-bridge
CHORUS_BRIDGE_TOKEN_TTL_SECONDS=300
```

Feature flags (Stage config):
```yaml
features:
  bridge_day_proof: true
  bridge_federation_send: true
  bridge_activitypub_export: false  # opt-in per deployment
  bridge_moderation_anchor: false
```

Fallback behavior when disabled:
- `bridge_day_proof = false` → Stage uses local deterministic clock or cached proofs if present.
- `bridge_federation_send = false` → Stage does not expose or relay federation behaviors.

---

## OpenAPI Stubs (Bridge)

```yaml
openapi: 3.0.3
info: { title: Chorus Bridge, version: 0.1.0 }
servers: [{ url: https://bridge.local }]
paths:
  /api/bridge/day-proof/{day}:
    get:
      parameters:
        - in: path
          name: day
          required: true
          schema: { type: integer }
      responses:
        '200':
          description: Canonical day proof
          content:
            application/json:
              schema:
                type: object
                properties:
                  day_number: { type: integer }
                  proof: { type: string }
                  canonical: { type: boolean }
                  proof_hash: { type: string }
        '404': { description: not found }
  /api/bridge/federation/send:
    post:
      requestBody:
        required: true
        content:
          application/octet-stream:
            schema: { type: string, format: binary }
      responses:
        '202': { description: accepted }
        '400': { description: bad request }
        '401': { description: unauthorized }
        '409': { description: conflict }
  /api/bridge/export:
    post:
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                chorus_post: { type: object }
                signature: { type: string }
      responses:
        '202': { description: queued }
        '409': { description: blocked }
```

---

## Error Model
- 400: schema/validation failed.
- 401/403: authentication/authorization failed.
- 404: resource not found (e.g., day-proof not yet canonical).
- 409: conflict (policy block, duplicate, or state violation).
- 429: rate limited; Stage should backoff with jitter.
- 5xx: transient Bridge errors; Stage retries with exponential backoff and caps.

Recommended headers:
- `Retry-After` on 429/503
- Problem Details JSON (RFC 7807) for errors

---

## Telemetry & Observability
- Stage logs outbound request IDs, `Idempotency-Key`, and response codes.
- Bridge logs include `X-Chorus-Instance-Id`, request ID, and envelope hashes.
- Metrics:
  - `stage_bridge_requests_total{endpoint,code}`
  - `stage_bridge_latency_seconds_bucket{endpoint}`
  - `bridge_ingress_requests_total{endpoint,code}`

---

## Rollout Plan
1) Add config and feature flags to Stage (no runtime code yet).
2) Document the Stage client adapter responsibilities and error handling.
3) Provide Bridge OpenAPI artifact to Stage consumers.
4) Gate initial usage behind `bridge_day_proof` in non-critical flows (read-only).
5) Expand to federation relay and AP export once Bridge is stable.

---

## Stage Client Adapter Checklist (Future Work, No Code Yet)
- Config plumbing: read `CHORUS_BRIDGE_*` envs.
- HTTP client with mTLS and JWT signing.
- Helper to fetch canonical day proof with caching and retries.
- Helper to send FederationEnvelope with idempotency and backoff.
- Export helper for AP bridge with policy pre-checks.

---

## Open Questions
- Should Bridge expose a batched day-proof endpoint (ranges) for faster warmup?
- Do we require per-tenant scoping in multi-instance deployments?
- Is a webhook needed later for push-style federated updates to Stage?
