# Implementation Plan: CFP-007 API Spec

Status: Draft
Owners: API Team
Scope: REST/WS surfaces, OpenAPI deltas, quotas

---

## Endpoint Inventory
- Auth
  - `POST /auth/login`
  - `POST /auth/proof-challenge`
- Federation
  - `POST /federation/message`
  - `GET /federation/day-proof/{day_number}`
  - `GET /federation/peers`
- Posts
  - `GET /posts/feed`
  - `POST /posts/create`
  - `GET /posts/{id}`
- Votes
  - `POST /votes/cast`
  - `GET /votes/post/{post_id}`
- Messages
  - `POST /messages/send`
  - `GET /messages/thread/{user_pubkey}`
- Moderation
  - `POST /moderation/flag`
  - `GET /moderation/queue`
- Communities
  - `GET /communities`
  - `POST /communities/create`

---

## OpenAPI Changes (YAML Snippet)
```yaml
openapi: 3.0.3
info:
  title: Chorus Stage API
  version: 1.0.0
paths:
  /federation/message:
    post:
      requestBody:
        required: true
        content:
          application/octet-stream:
            schema:
              type: string
              format: binary
      responses:
        '202': { description: accepted }
        '400': { description: bad request }
        '401': { description: unauthorized }
        '403': { description: forbidden }
        '409': { description: conflict }
  /federation/day-proof/{day_number}:
    get:
      parameters:
        - in: path
          name: day_number
          required: true
          schema: { type: integer }
      responses:
        '200':
          description: canonical day proof
          content:
            application/json:
              schema:
                type: object
                properties:
                  day_number: { type: integer }
                  proof: { type: string }
```

---

## Rate Limits
```yaml
rate_limits:
  posts_create_per_day:
    tier_new: 5
    tier_veteran: 50
  votes_cast_per_day:
    tier_new: 20
    tier_veteran: 100
  federation_ingress_rps:
    default: 10
    burst: 50
```

---

## Telemetry
- Include request IDs and envelope hashes in structured logs.
- Emit counters for each endpoint and 4xx/5xx buckets.

---

## Rollout
- Stage changes behind a versioned router `api/v1` → `api/fed/v1` for federation.
- Add WS federation stream under `/ws/federation` with auth toggles.

