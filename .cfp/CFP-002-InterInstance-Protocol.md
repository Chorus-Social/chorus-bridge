# CFP-002: Inter-Instance Communication Protocol

**Version:** 1.0.0
**Status:** Draft
**Date:** October 23, 2025
**Authors:** Chorus Federation Protocol Team

---

## Abstract
This document specifies the communication protocol for federated Chorus Stage instances. It covers message format, authentication between instances, federation API endpoints, content propagation, and the wire protocol for decentralized communication.
---

## 1. Inter-Instance Communication Overview
Chorus Stage uses a federation model to connect multiple independent servers (instances). These instances must be able to:
- Discover and authenticate one another
- Propagate posts, moderation events, and user registrations
- Exchange proofs and synchronize states
---

## 2. Message Format Specifications
Chorus Federation messages are serialized using Protocol Buffers for efficiency and extensibility.

### 2.1 Example Schema (Proto3)
```proto
syntax = "proto3";
package chorus;

message FederationEnvelope {
  string sender_instance = 1;
  uint64 timestamp = 2;
  string message_type = 3; // e.g., "PostAnnouncement"
  bytes message_data = 4; // Nested message content
  bytes signature = 5;
}

message PostAnnouncement {
  bytes post_id = 1;
  bytes author_pubkey = 2;
  bytes content_hash = 3;
  uint32 order_index = 4;
  int32 creation_day = 5;
}
```

### 2.2 Canonical Message Types
- **PostAnnouncement**: Announces new post by ID and day
- **UserRegistration**: Shares new user pubkey and day proof
- **DayProof**: Distributes daily VDF proof for consensus
- **ModerationEvent**: Notifies about flagged or removed content
- **InstanceJoinRequest**: Requests to join federation

All messages are signed by instance private key (Ed25519).

---

## 3. API Endpoints for Federation
Instances expose RESTful and WebSocket APIs for federated inter-instance actions.

### 3.1 REST Endpoints
- **POST /federation/message**
  - Accepts a signed FederationEnvelope
  - Verifies Ed25519 signature and message type
  - Enqueues for processing

- **GET /federation/day-proof/{day_number}**
  - Returns canonical day proof for the specified day

- **GET /federation/peers**
  - Returns list of trusted peers

### 3.2 WebSocket Events
- **/ws/federation**
  - Real-time subscription to post, moderation, and proof events

---

## 4. Authentication Between Instances
- Each instance generates a long-term Ed25519 keypair
- All federation messages are signed using the instance key
- Peers verify signatures and whitelist trusted/federated public keys
- Optional: Mutual TLS (mTLS) for channel encryption

---

## 5. Content Propagation Algorithms
### 5.1 Push Model (Default)
- Instance A creates post → signs PostAnnouncement → pushes to all linked peers
- Peers receive → validate signature/proof → announce to their users

### 5.2 Pull Model (Privacy)
- Instance A announces new content hash on DHT
- Peers may query for new posts by hash only as needed, reducing metadata leakage

---

## 6. Wire Protocol Definition
- Core protocol: Protocol Buffers (compact binary serialization)
- Transport: HTTP/2 for REST API, WebSockets for real-time, libp2p for peer-to-peer

### 6.1 Example FederationEnvelope Transmission
```python
import requests
from nacl.signing import SigningKey
import base64

SIGN_KEY = SigningKey.generate()

# Build envelope
env = FederationEnvelope(
    sender_instance="chorus1.example.net",
    timestamp=int(time.time()),
    message_type="PostAnnouncement",
    message_data=b"...",  # Serialized PostAnnouncement
)
# Sign
env.signature = SIGN_KEY.sign(env.message_data).signature

# Serialize
payload = env.SerializeToString()

# POST to peer instance
requests.post(
    "https://chorus2.example.net/federation/message",
    data=payload,
    headers={"Content-Type": "application/octet-stream"})
```

---

## 7. Federation Policies
- Instances specify trusted peers by public key in federation config
- May require manual approval for cross-instance federation
- Non-trusted messages are dropped or quarantined

---

## 8. Example Federation Config File
```yaml
federation:
  instance_id: "chorus1.example.net"
  private_key_path: "/etc/chorus/private_ed25519.pem"
  trusted_peers:
    - "chorus2.example.net"
    - "chorus3.example.net"
  endpoints:
    - "https://chorus2.example.net/federation/message"
    - "wss://chorus2.example.net/ws/federation"
  wire_protocol: "protobuf"
```
---

## 9. Security and Privacy Considerations
- All messages authenticated via Ed25519 signature
- Channel encryption (TLS or mTLS) recommended for all federation links
- Minimal metadata: only day numbers, no timestamps
- No user-level linking across instances

---

## 10. Troubleshooting & Diagnostics
- Federation logs record all inbound/outbound message hashes
- Message replays rejected via nonce/hash cache
- Peers can request live federation health/status via /federation/peers
---

**Document Status**: Draft v1.0.0
**Contact**: chorus-federation@example.com