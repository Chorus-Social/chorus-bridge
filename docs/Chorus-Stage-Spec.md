# Chorus Stage Technical Specification

**Version:** 1.0  
**Date:** October 23, 2025  
**Status:** Technical Specification

---

## Abstract

**Chorus Stage** is the FastAPI-based user-facing server that acts as the primary interface between **Chorus Clients** and the broader Chorus ecosystem. Each Stage instance hosts its own PostgreSQL database for user data, posts, votes, messages, and moderation state. Stage instances communicate with **Chorus Bridge** to participate in federation and ensure data replication across the network. This document defines the architecture, responsibilities, API surface, data models, and integration points for Chorus Stage.

---

## 1. Purpose & Scope

**Chorus Stage** serves as:
- The **API gateway** for all client requests (authentication, posting, voting, messaging, moderation).
- The **data custodian** for its local users and content.
- The **federation participant** that submits events to and receives events from Chorus Bridge.
- The **privacy enforcer** that ensures no real-world timestamps or linkable metadata are exposed.

**Out of Scope:**
- Direct consensus participation (handled by Conductor via Bridge).
- Peer-to-peer Stage-to-Stage communication (mediated by Bridge).

---

## 2. Core Responsibilities

### 2.1 Client-Server Communication
- Expose REST and WebSocket APIs for client interactions.
- Authenticate users via Ed25519 public-key cryptography.
- Enforce rate limits and tier-based access controls.

### 2.2 Data Management
- Store user accounts, posts, votes, messages, communities, and moderation events in a local PostgreSQL database.
- Use **day numbers** and **order IDs** instead of timestamps for all temporal data.
- Encrypt sensitive data (e.g., direct messages) at rest.

### 2.3 Federation Integration
- Submit new user actions (posts, votes, registrations) to **Chorus Bridge** for federation.
- Receive federated events from Bridge and update local state accordingly.
- Never expose timestamps to Bridge; only day numbers, hashes, and anonymized identifiers.

### 2.4 Privacy Enforcement
- Reject any API request or data model that includes real-world timestamps.
- Store only cryptographic hashes of user public keys (not full public keys unless required for encryption).
- Implement data minimization: if data is not essential, do not store it.

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────┐
│        Chorus Clients                   │
│  (Web, Mobile, Desktop, 3rd Party)     │
└──────────────┬──────────────────────────┘
               │
               │ REST / WebSocket
               │ (HTTPS, JWT Auth)
               ▼
       ┌───────────────────┐
       │   Chorus Stage    │
       │    (FastAPI)      │
       │                   │
       │  ┌─────────────┐  │
       │  │ PostgreSQL  │  │
       │  │  Database   │  │
       │  └─────────────┘  │
       └──────────┬────────┘
                  │
                  │ Bridge Integration
                  │ (REST API / gRPC)
                  ▼
          ┌───────────────────┐
          │   Chorus Bridge   │
          └───────────────────┘
```

### Key Components:
- **FastAPI Application**: Handles all HTTP/WebSocket traffic.
- **PostgreSQL Database**: Stores user data, posts, votes, messages, communities, and moderation state.
- **Bridge Client**: Communicates with Chorus Bridge for federation concerns.
- **Background Workers**: Process async tasks (federation updates, moderation queue processing, etc.).

---

## 4. Technology Stack

- **Framework**: FastAPI (Python 3.10+)
- **Database**: PostgreSQL 15+
- **Cryptography**: `cryptography` (Ed25519), `pynacl` (NaCl for E2E encryption)
- **Hashing**: BLAKE3 for all content hashing
- **WebSockets**: `fastapi.WebSocket` for real-time updates
- **Background Tasks**: Celery or FastAPI background tasks
- **Observability**: Prometheus metrics, structured logging (JSON)

---

## 5. Database Schema

### 5.1 Users Table
```sql
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  pubkey_hash CHAR(64) UNIQUE NOT NULL,  -- BLAKE3(pubkey)
  creation_day INTEGER NOT NULL,
  tier VARCHAR(20) NOT NULL DEFAULT 'new',  -- 'new', 'veteran'
  accent_color CHAR(7),  -- Optional hex color
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),  -- Internal only, never exposed
  INDEX (pubkey_hash)
);
```

### 5.2 Posts Table
```sql
CREATE TABLE posts (
  id BIGSERIAL PRIMARY KEY,
  post_id CHAR(64) UNIQUE NOT NULL,  -- BLAKE3(content)
  author_pubkey_hash CHAR(64) NOT NULL,
  body_md TEXT NOT NULL,
  creation_day INTEGER NOT NULL,
  order_index INTEGER NOT NULL,  -- Within-day ordering
  community VARCHAR(100),
  vote_score INTEGER DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),  -- Internal only
  FOREIGN KEY (author_pubkey_hash) REFERENCES users(pubkey_hash),
  INDEX (creation_day, order_index),
  INDEX (community)
);
```

### 5.3 Votes Table
```sql
CREATE TABLE votes (
  id BIGSERIAL PRIMARY KEY,
  vote_id CHAR(64) UNIQUE NOT NULL,
  target_post_id CHAR(64) NOT NULL,
  voter_pubkey_hash CHAR(64) NOT NULL,
  vote_type VARCHAR(10) NOT NULL,  -- 'positive', 'negative', 'neutral'
  creation_day INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),  -- Internal only
  FOREIGN KEY (target_post_id) REFERENCES posts(post_id),
  FOREIGN KEY (voter_pubkey_hash) REFERENCES users(pubkey_hash),
  UNIQUE (target_post_id, voter_pubkey_hash)
);
```

### 5.4 Messages Table (E2E Encrypted)
```sql
CREATE TABLE messages (
  id BIGSERIAL PRIMARY KEY,
  message_id CHAR(64) UNIQUE NOT NULL,
  sender_pubkey_hash CHAR(64) NOT NULL,
  recipient_pubkey_hash CHAR(64) NOT NULL,
  encrypted_body TEXT NOT NULL,  -- NaCl Box encrypted
  creation_day INTEGER NOT NULL,
  order_index INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),  -- Internal only
  FOREIGN KEY (sender_pubkey_hash) REFERENCES users(pubkey_hash),
  FOREIGN KEY (recipient_pubkey_hash) REFERENCES users(pubkey_hash),
  INDEX (sender_pubkey_hash, recipient_pubkey_hash),
  INDEX (creation_day, order_index)
);
```

### 5.5 Communities Table
```sql
CREATE TABLE communities (
  id BIGSERIAL PRIMARY KEY,
  community_id VARCHAR(100) UNIQUE NOT NULL,
  name VARCHAR(200) NOT NULL,
  description TEXT,
  creation_day INTEGER NOT NULL,
  creator_pubkey_hash CHAR(64) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),  -- Internal only
  FOREIGN KEY (creator_pubkey_hash) REFERENCES users(pubkey_hash)
);
```

### 5.6 Moderation Events Table
```sql
CREATE TABLE moderation_events (
  id BIGSERIAL PRIMARY KEY,
  event_id CHAR(64) UNIQUE NOT NULL,
  target_ref CHAR(64) NOT NULL,  -- Post/user hash
  action VARCHAR(50) NOT NULL,  -- 'flag', 'hide', 'ban'
  reason_hash CHAR(64),  -- Hash of reason (privacy)
  moderator_pubkey_hash CHAR(64) NOT NULL,
  creation_day INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),  -- Internal only
  FOREIGN KEY (moderator_pubkey_hash) REFERENCES users(pubkey_hash)
);
```

### 5.7 Federation Event Log (for outbound tracking)
```sql
CREATE TABLE federation_outbound (
  id BIGSERIAL PRIMARY KEY,
  event_type VARCHAR(50) NOT NULL,  -- 'PostAnnouncement', 'UserRegistration', etc.
  event_hash CHAR(64) UNIQUE NOT NULL,
  payload BYTEA NOT NULL,  -- Serialized FederationEnvelope
  submitted_at TIMESTAMP NOT NULL DEFAULT NOW(),
  status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'accepted', 'failed'
  retry_count INTEGER DEFAULT 0
);
```

---

## 6. API Surface

### 6.1 Base URL
```
https://{stage_domain}/api/v1
```

### 6.2 Authentication Endpoints

#### `GET /auth/challenge`
- **Purpose**: Request a cryptographic challenge for login.
- **Response**:
  ```json
  {
    "challenge": "hex-bytes",
    "expires_in": 300
  }
  ```

#### `POST /auth/login`
- **Purpose**: Authenticate user with signed challenge.
- **Request**:
  ```json
  {
    "pubkey_hash": "hex",
    "signature": "hex"
  }
  ```
- **Response**:
  ```json
  {
    "token": "jwt",
    "expires_in": 3600
  }
  ```

#### `POST /auth/register`
- **Purpose**: Register new user with PoW and signed challenge.
- **Request**:
  ```json
  {
    "pubkey_hash": "hex",
    "pow_nonce": "hex",
    "signature": "hex"
  }
  ```
- **Response**:
  ```json
  {
    "user_id": "hex",
    "creation_day": 1234,
    "tier": "new"
  }
  ```

### 6.3 Post Endpoints

#### `POST /posts/create`
- **Purpose**: Create a new post.
- **Request**:
  ```json
  {
    "body_md": "# Hello World",
    "community": "general"
  }
  ```
- **Response**:
  ```json
  {
    "post_id": "hex",
    "creation_day": 1234,
    "order_index": 567
  }
  ```

#### `GET /posts/feed`
- **Purpose**: Retrieve feed (paginated, sorted by day/order).
- **Query Params**: `?community=general&limit=50&after_day=1234&after_order=567`
- **Response**:
  ```json
  {
    "posts": [
      {
        "post_id": "hex",
        "author_pubkey_hash": "hex",
        "body_md": "...",
        "creation_day": 1234,
        "order_index": 567,
        "vote_score": 42
      }
    ],
    "next_cursor": { "day": 1234, "order": 600 }
  }
  ```

#### `GET /posts/{post_id}`
- **Purpose**: Retrieve a single post by ID.
- **Response**: Same as feed item.

### 6.4 Vote Endpoints

#### `POST /votes/cast`
- **Purpose**: Cast a vote on a post.
- **Request**:
  ```json
  {
    "target_post_id": "hex",
    "vote_type": "positive"
  }
  ```
- **Response**:
  ```json
  {
    "vote_id": "hex",
    "creation_day": 1234
  }
  ```

#### `GET /votes/post/{post_id}`
- **Purpose**: Retrieve votes for a post.
- **Response**:
  ```json
  {
    "vote_score": 42,
    "vote_count": 100
  }
  ```

### 6.5 Message Endpoints

#### `POST /messages/send`
- **Purpose**: Send E2E encrypted direct message.
- **Request**:
  ```json
  {
    "recipient_pubkey_hash": "hex",
    "encrypted_body": "hex"
  }
  ```
- **Response**:
  ```json
  {
    "message_id": "hex",
    "creation_day": 1234,
    "order_index": 123
  }
  ```

#### `GET /messages/thread/{user_pubkey}`
- **Purpose**: Retrieve message thread with another user.
- **Response**:
  ```json
  {
    "messages": [
      {
        "message_id": "hex",
        "sender_pubkey_hash": "hex",
        "encrypted_body": "hex",
        "creation_day": 1234,
        "order_index": 123
      }
    ]
  }
  ```

### 6.6 Moderation Endpoints

#### `POST /moderation/flag`
- **Purpose**: Flag content for moderation.
- **Request**:
  ```json
  {
    "target_ref": "hex",
    "reason_hash": "hex"
  }
  ```
- **Response**:
  ```json
  {
    "event_id": "hex",
    "creation_day": 1234
  }
  ```

#### `GET /moderation/queue`
- **Purpose**: View moderation queue (requires moderator permissions).
- **Response**:
  ```json
  {
    "events": [
      {
        "event_id": "hex",
        "target_ref": "hex",
        "action": "flag",
        "creation_day": 1234
      }
    ]
  }
  ```

### 6.7 Community Endpoints

#### `GET /communities`
- **Purpose**: List all communities.
- **Response**:
  ```json
  {
    "communities": [
      {
        "community_id": "general",
        "name": "General Discussion",
        "description": "...",
        "creation_day": 1
      }
    ]
  }
  ```

#### `POST /communities/create`
- **Purpose**: Create a new community.
- **Request**:
  ```json
  {
    "community_id": "my-community",
    "name": "My Community",
    "description": "..."
  }
  ```
- **Response**:
  ```json
  {
    "community_id": "my-community",
    "creation_day": 1234
  }
  ```

### 6.8 WebSocket Endpoint

#### `wss://{stage_domain}/ws/feed`
- **Purpose**: Real-time feed updates.
- **Events**:
  - `new_post`: New post announcement.
  - `new_vote`: Vote cast on a post.
  - `moderation_update`: Moderation action taken.
- **Example Event**:
  ```json
  {
    "type": "new_post",
    "data": {
      "post_id": "hex",
      "creation_day": 1234,
      "order_index": 567
    }
  }
  ```

---

## 7. Bridge Integration

### 7.1 Configuration
Stage instances are configured with a Bridge connection:
```yaml
bridge:
  enabled: true
  base_url: https://bridge.chorus.local
  instance_id: stage-1
  mtls_enabled: true
  jwks_url: https://bridge.chorus.local/.well-known/jwks.json
  jwt_issuer: stage-1
  jwt_audience: chorus-bridge
  token_ttl_seconds: 300
```

### 7.2 Outbound Events (Stage → Bridge)

#### Day Proof Retrieval
```
GET {BRIDGE_BASE_URL}/api/bridge/day-proof/{day}
```
- Purpose: Fetch canonical day proof for account age validation.

#### Federation Message Relay
```
POST {BRIDGE_BASE_URL}/api/bridge/federation/send
Headers:
  Authorization: Bearer <jwt>
  Idempotency-Key: <uuid>
  Content-Type: application/octet-stream
Body: serialized FederationEnvelope
```
- Purpose: Submit user actions (posts, votes, registrations) to Bridge for federation.

#### ActivityPub Export (Optional)
```
POST {BRIDGE_BASE_URL}/api/bridge/export
Body:
  {
    "chorus_post": { ... },
    "signature": "hex"
  }
```
- Purpose: Export public content to ActivityPub via Bridge.

### 7.3 Inbound Events (Bridge → Stage)

**Phase 1**: Stage polls Bridge for new federated events (pull model).
**Phase 2**: Bridge pushes events to Stage via webhooks (future enhancement).

#### Federated Event Processing
- Bridge relays validated events (posts, votes, moderation) from other Stages.
- Stage validates signature, checks blacklist, updates local database.

---

## 8. Privacy & Security

### 8.1 No Timestamp Exposure
- Internal database timestamps (`created_at`) are **never** exposed via API.
- All temporal data uses `creation_day` (integer) and `order_index`.

### 8.2 Data Minimization
- Only store cryptographic hashes of public keys (unless full key needed for encryption).
- No persistent device identifiers, IP addresses, or user-agent strings.

### 8.3 End-to-End Encryption (Messages)
- Direct messages are encrypted client-side with NaCl Box.
- Stage stores only ciphertext; cannot decrypt.

### 8.4 Rate Limiting
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

### 8.5 Proof-of-Work (Registration)
- New users must complete a BLAKE3-based PoW challenge to register.
- Difficulty adjustable via configuration.

---

## 9. Observability

### 9.1 Metrics (Prometheus)
- `stage_requests_total{endpoint, code}`
- `stage_db_queries_total{table}`
- `stage_bridge_requests_total{endpoint, code}`
- `stage_feed_events_total{type}`

### 9.2 Logging
- Structured JSON logs (no PII).
- Include request IDs and envelope hashes (not content).

### 9.3 Health Endpoints
- `GET /health/live` — Liveness probe.
- `GET /health/ready` — Readiness probe (checks DB and Bridge connectivity).

---

## 10. Deployment

### 10.1 Docker Compose Example
```yaml
version: "3.8"
services:
  stage:
    image: chorus/stage:latest
    ports: ["443:443", "9090:9090"]
    environment:
      - DATABASE_URL=postgresql://chorus:password@db:5432/chorus
      - BRIDGE_BASE_URL=https://bridge.chorus.local
      - BRIDGE_INSTANCE_ID=stage-1
    depends_on: [db]
    volumes:
      - ./keys:/app/keys
      - ./stage.yaml:/app/stage.yaml

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=chorus
      - POSTGRES_USER=chorus
      - POSTGRES_PASSWORD=password
    volumes:
      - stage_db:/var/lib/postgresql/data

volumes:
  stage_db:
```

---

## 11. Testing

- Unit tests for API endpoints.
- Integration tests with mock Bridge.
- Load tests for rate limiting and concurrency.
- Privacy audits: ensure no timestamps leak.

---

## 12. Future Directions

- **Multi-tenant Stage**: Support multiple instances per deployment.
- **Advanced Moderation Tools**: AI-assisted flagging.
- **Enhanced Privacy**: Onion routing for federation.

---

## 13. Licensing

**GPLv3**

---

## 14. Conclusion

Chorus Stage is the privacy-first, FastAPI-based gateway to the Chorus network. By strictly enforcing anonymity, data minimization, and seamless Bridge integration, Stage ensures users can participate in a decentralized social network without compromising their privacy.

---

**Document Status:** Technical Specification v1.0  
**Contact:** chorus-team@chorus.social
