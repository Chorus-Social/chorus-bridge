# CFP-007: API Specification

**Version:** 1.0.0
**Status:** Draft
**Date:** October 23, 2025
**Authors:** Chorus Federation Protocol Team

---

## Abstract
This document provides a comprehensive specification of the REST, WebSocket, and optional GraphQL APIs exposed by Chorus Stage federation instances, covering endpoints, data models, rate limiting, real-time sync, and error handling.

---

## 1. REST API Endpoints

### 1.1 Authentication
- `POST /auth/login`  — Anonymous login with keypair proof
- `POST /auth/proof-challenge`  — Proof-of-work + signature challenge

### 1.2 Federation
- `POST /federation/message`  — Receives signed FederationEnvelope
- `GET /federation/day-proof/{day_number}`  — Get VDF proof
- `GET /federation/peers`  — List of trusted federation peers

### 1.3 Posts
- `GET /posts/feed`  — Deterministic ordered feed
- `POST /posts/create`  — Create new post (body_md, order_index, etc.)
- `GET /posts/{id}`  — Retrieve post (no timestamps, day number only)

### 1.4 Votes
- `POST /votes/cast`  — Submit vote (sentiment/harmful)
- `GET /votes/post/{post_id}`  — Vote results for a post

### 1.5 DMs
- `POST /messages/send`  — Encrypted DM using NaCl sealed box
- `GET /messages/thread/{user_pubkey}`  — Retrieve end-to-end encrypted DMs

### 1.6 Moderation
- `POST /moderation/flag`  — Flag post/user (ModerationEvent)
- `GET /moderation/queue`  — Retrieve moderation queue (community-driven)

### 1.7 Community
- `GET /communities`  — List all communities
- `POST /communities/create`  — Create new community (Veteran tier)

---

## 2. WebSocket API
### 2.1 Event Streams
- `/ws/feed` — Real-time new post and vote updates
- `/ws/federation` — Federation event propagation

---

## 3. GraphQL Query Layer (Optional)
```graphql
query GetFeed {
  feed {
    postId
    authorUserId
    bodyMd
    orderIndex
    dayNumber
  }
}
```

---

## 4. Rate Limiting
- All APIs enforce rate limits by account age/tier (documented in architecture)
  - 5–50 posts/day, 20–100+ votes/day, etc.
- Error 429 returned on exceeding quota

---

## 5. Data Models
### 5.1 User
```json
{
  "pubkey_hash": "...",
  "creation_day": 1234,
  "creation_day_proof": "...",
  "display_name": "anonymous_cat",
  "accent_color": "#111111"
}
```
### 5.2 Post
```json
{
  "id": 1,
  "order_index": 4,
  "author_user_id": "...",
  "body_md": "...",
  "day": 1234
}
```

---

## 6. Error Handling
- Standard: Error codes 400, 401, 403, 404, 409, 429, 500
- All API errors include reason and hint
```json
{
  "error": "rate_limit_exceeded",
  "hint": "Upgrade tier by account age"
}
```

---

**Document Status:** Draft v1.0.0
**Contact:** chorus-federation@example.com