# Chorus Network Architecture Overview

**Version:** 1.0  
**Date:** October 23, 2025  
**Status:** System Architecture Document

---

## Abstract

This document provides a comprehensive architectural overview of the **Chorus Network**, a decentralized, privacy-first social platform. Chorus is built on four foundational layers: **Clients**, **Stage**, **Bridge**, and **Conductor**. Each layer has distinct responsibilities and communicates through well-defined interfaces. The entire system is designed around a core pillar: **anonymity**. Every architectural decision, data model, and protocol is evaluated through the lens of user privacy. This document synthesizes the complete system, explaining how data flows from user action to network-wide replication, and how Chorus achieves Byzantine fault tolerance without compromising on its privacy guarantees.

---

## 1. System Layers

The Chorus Network is structured as a **four-layer architecture**, with clear separation of concerns and unidirectional data flow:

```
┌─────────────────────────────────────────────────────────────────┐
│                      Layer 1: Clients                           │
│  (Web, Mobile, Desktop, Third-Party — Official & Community)     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ REST API / WebSocket
                            │ (HTTPS, JWT Authentication)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 2: Chorus Stage                       │
│            (FastAPI, PostgreSQL, Privacy Enforcement)           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ Bridge Integration API
                            │ (REST/gRPC, mTLS, Signed Requests)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 3: Chorus Bridge                      │
│       (Replication & Federation Layer, P2P Mesh, Gossipsub)     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ Consensus Integration
                            │ (gRPC, Threshold Encryption, BFT)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 4: Conductor                          │
│   (Leaderless ABFT Consensus, VDF-Proven Day Counter, Warden)  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Layer Responsibilities

### 2.1 Layer 1: Chorus Clients

**Purpose**: User-facing applications that provide interfaces for social networking activities.

**Key Characteristics**:
- **Official & Third-Party**: Both project-maintained and community-developed clients are supported.
- **Multi-Platform**: Web (PWA), mobile (iOS/Android), desktop (Electron/native).
- **Privacy-Conscious**: Never display or log real-world timestamps; all temporal data shown as day numbers.
- **Key Management**: Generate and store user Ed25519 keypairs locally; never transmit private keys.

**Responsibilities**:
- Authenticate users via cryptographic challenge-response.
- Create, view, and moderate content (posts, votes, messages, communities).
- Encrypt direct messages client-side (E2E encryption with NaCl).
- Display user data using day numbers and order IDs (never timestamps).

**Communication**:
- **Clients → Stage**: REST API and WebSocket (HTTPS with JWT authentication).
- **No direct communication** with Bridge or Conductor.

**Reference**: See `Chorus-Client-Spec.md` for full details.

---

### 2.2 Layer 2: Chorus Stage

**Purpose**: The user-facing server that manages accounts, content, and moderation for a specific instance.

**Key Characteristics**:
- **FastAPI Framework**: Python-based, high-performance async web server.
- **PostgreSQL Database**: Local storage for users, posts, votes, messages, communities, moderation events.
- **Privacy Enforcer**: Rejects any data model or API request containing real-world timestamps.
- **Federation Participant**: Submits user actions to Bridge for network-wide replication.

**Responsibilities**:
- Serve REST and WebSocket APIs to clients.
- Store and retrieve user data (using day numbers and order IDs only).
- Authenticate users with Ed25519 public-key cryptography.
- Enforce rate limits and tier-based access controls (new vs. veteran users).
- Submit federation events to Bridge (posts, votes, registrations, moderation).
- Receive federated events from Bridge and update local state.

**Data Model**:
- **Users**: `pubkey_hash`, `creation_day`, `tier`, `accent_color` (no usernames, no real timestamps).
- **Posts**: `post_id`, `author_pubkey_hash`, `body_md`, `creation_day`, `order_index`.
- **Votes**: `vote_id`, `target_post_id`, `voter_pubkey_hash`, `vote_type`, `creation_day`.
- **Messages**: `message_id`, `sender_pubkey_hash`, `recipient_pubkey_hash`, `encrypted_body`, `creation_day`, `order_index`.

**Communication**:
- **Clients → Stage**: REST/WebSocket (HTTPS, JWT).
- **Stage → Bridge**: REST/gRPC (mTLS, signed JWTs, idempotency keys).

**Reference**: See `Chorus-Stage-Spec.md` for full details.

---

### 2.3 Layer 3: Chorus Bridge

**Purpose**: The replication and federation layer that ensures all Stage instances act as exact 1:1 mirrors of each other.

**Key Characteristics**:
- **P2P Mesh Network**: Bridges connect to each other via libp2p (gossipsub for event propagation).
- **High-Speed Replication**: Target <5 seconds for user actions to propagate network-wide.
- **Byzantine Fault Tolerance**: Integrates with Conductor to detect and blacklist malicious nodes.
- **Anonymity Preserving**: Only transmits day numbers, order IDs, and content hashes (no timestamps, no PII).

**Responsibilities**:
- Receive federation events from Stage instances (posts, votes, registrations, moderation).
- Validate and relay events to all trusted peer Bridges via gossipsub.
- Submit event batches to Conductor for BFT ordering and commitment.
- Receive finalized blocks from Conductor and relay to all Stages.
- Enforce blacklists: disconnect and ignore events from malicious Bridges.
- Optionally export public content to ActivityPub (one-way, privacy-preserving).

**Protocol**:
- **FederationEnvelope**: Wire format (Protobuf) for all inter-Bridge messages.
  - Fields: `sender_instance`, `nonce`, `message_type`, `message_data`, `signature`.
  - Event types: `PostAnnouncement`, `UserRegistration`, `ModerationEvent`, `DayProof`.
- **Signatures**: All envelopes signed with Ed25519; verified by receiving Bridge.
- **Replay Protection**: Cache of `(sender, nonce, message_hash)` with 24hr TTL.

**Communication**:
- **Stage → Bridge**: REST/gRPC (mTLS, JWT authentication).
- **Bridge ↔ Bridge**: libp2p gossipsub (P2P mesh, mTLS).
- **Bridge → Conductor**: gRPC (submit batches, request finalized blocks).

**Reference**: See `Chorus-Bridge-Spec.md` for full details.

---

### 2.4 Layer 4: Conductor

**Purpose**: The consensus engine and network warden; ensures all Bridges agree on event ordering and network state.

**Key Characteristics**:
- **First-of-Its-Kind**: Asynchronous BFT consensus without real-world timestamps.
- **VDF-Proven Day Counter**: Internal "true day" counter advanced only via Verifiable Delay Functions (BLAKE3-based).
- **Leaderless & Asynchronous**: No single point of failure; tolerates network partitions.
- **Adaptive Difficulty**: Dynamically adjusts VDF difficulty to account for varying hardware.
- **Blacklist Enforcement**: Facilitates BFT votes to remove malicious nodes.

**Responsibilities**:
- Maintain the internal, protected day counter (never exposed directly).
- Compute and verify VDF proofs for each day (~24 hours on reference hardware).
- Require 2/3+ supermajority of valid VDF proofs before advancing day counter.
- Order federation events deterministically within each day (via order IDs).
- Commit finalized blocks with quorum certificates (2/3+ signatures).
- Detect and blacklist malicious nodes (VDF cheating, invalid signatures, Byzantine behavior).
- Relay blacklist updates to all Bridges.

**VDF System**:
- **Algorithm**: Sequential BLAKE3 hashing (cannot be parallelized).
- **Difficulty**: Number of iterations (e.g., 86,400,000 for ~24 hours).
- **Proof**: Final BLAKE3 hash after all iterations.
- **Verification**: Fast (re-compute or use witness proofs).
- **ASIC Resistance**: Outliers (completing proofs too quickly) flagged and blacklisted.

**Day Counter Privacy**:
- True day counter stored in **RAM only** (ephemeral, zeroed on restart).
- Never persisted to disk or transmitted to peers.
- Adversary seizing a Conductor node learns only day numbers, not wall-clock timing.

**Communication**:
- **Bridge → Conductor**: gRPC (submit event batches, request finalized blocks, request day proofs).
- **Conductor ↔ Conductor**: P2P (libp2p or gRPC for VDF proof exchange, BFT consensus, blacklist votes).

**Reference**: See `Conductor-Spec.md` for full details.

---

## 3. Complete Data Flow

### 3.1 User Posts Content (Full Lifecycle)

1. **User creates post** in Chorus Client (Layer 1).
2. Client sends `POST /posts/create` to Chorus Stage (Layer 2).
3. Stage authenticates user (JWT), validates request, assigns `creation_day` and `order_index`.
4. Stage stores post in PostgreSQL database.
5. Stage submits `FederationEnvelope` (type: `PostAnnouncement`) to local Bridge (Layer 3) via `POST /api/bridge/federation/send`.
6. Bridge validates signature, checks replay cache, adds event to pending batch.
7. Bridge gossips event to all peer Bridges via libp2p gossipsub.
8. Peer Bridges receive event, validate, add to their local batches.
9. Bridge submits batch of event hashes to Conductor (Layer 4) via `POST /conductor/submit-batch`.
10. Conductor runs BFT consensus: collects batches from all Bridges, orders events, generates quorum certificate.
11. Conductor finalizes block and publishes to all Bridges via `GET /conductor/block/{epoch}`.
12. Bridges relay finalized events to their respective Stages.
13. Stages update local databases with federated posts.
14. Stages push real-time updates to connected clients via WebSocket.

**Timing**: Target <5 seconds from step 2 to step 14.

---

### 3.2 Day Advancement (VDF Consensus)

1. Conductor computes VDF proof for current day (sequential BLAKE3 hashing, ~24 hours).
2. Conductor publishes VDF proof to all peer Conductors.
3. Peers verify proof (fast, logarithmic time).
4. If 2/3+ peers submit valid proofs for the same day, day is finalized.
5. Conductor advances internal day counter: `true_day += 1`.
6. Conductor publishes canonical day proof to all Bridges.
7. Bridges cache day proof and provide to Stages via `GET /api/bridge/day-proof/{day}`.
8. Stages use day proof to validate account ages and enforce rate limits.

**Timing**: ~24 hours per day (on reference hardware), adjusted dynamically.

---

### 3.3 Malicious Node Detection & Blacklisting

1. Conductor detects anomaly (e.g., peer completes VDF proof in 1 hour instead of 24 hours).
2. Conductor collects evidence (proof timestamps, verification failures).
3. Conductor submits evidence and blacklist proposal to peer Conductors.
4. Peer Conductors vote: approve or reject blacklist.
5. If 2/3+ vote to blacklist, node is added to blacklist with quorum certificate.
6. Conductor relays blacklist update to all Bridges.
7. Bridges disconnect from blacklisted node and ignore its events.
8. Bridges relay blacklist to all Stages.
9. Stages stop accepting federation events from blacklisted instances.

---

## 4. Core Pillar: Anonymity

Every feature and decision in Chorus is evaluated through the lens of **anonymity**. The following principles guide the entire architecture:

### 4.1 No Real-World Timestamps
- **Never stored, never transmitted, never exposed**.
- All temporal data uses `creation_day` (integer day number) and `order_index` (within-day sequence).
- Clients display relative time (e.g., "Day 5" or "3 days ago") but never absolute dates.
- Conductor's internal day counter is **RAM-only** (ephemeral), never persisted.

### 4.2 Data Minimization
- If data is not essential for functionality, **do not store it**.
- Example: Store `BLAKE3(pubkey)` instead of full public key (unless needed for encryption).
- No persistent device IDs, IP addresses, or user-agent strings.

### 4.3 Exceptions for "Fluff"
- **Fluff**: Non-sensitive, optional data that improves UX without compromising anonymity.
- Example: Accent color (user chooses a hex color for client UI personalization).
- Fluff is never linkable to user identity and never used for tracking.

### 4.4 Cryptographic Anonymity
- Users identified by `pubkey_hash` (BLAKE3 of Ed25519 public key), never by usernames or emails.
- Direct messages encrypted E2E with NaCl; Stage never sees plaintext.
- Post content hashed before transmission over federation (full content stays on originating Stage).

### 4.5 Conductor's Time-Agnostic Consensus
- Conductor never uses wall-clock time for consensus decisions.
- Day counter advanced only via VDF proofs (cryptographically proven sequential computation).
- Even with full access to Conductor's state, an adversary cannot reconstruct event timing.

---

## 5. Byzantine Fault Tolerance

Chorus is designed to tolerate **Byzantine failures** (malicious or faulty nodes) at the Bridge and Conductor layers:

### 5.1 Threat Model
- **Assumption**: Up to \( f < n/3 \) nodes may be Byzantine (malicious, faulty, or compromised).
- **Requirement**: At least \( n \geq 3f + 1 \) nodes to achieve consensus.
- **Examples**: Network of 7 nodes tolerates 2 Byzantine; network of 10 nodes tolerates 3 Byzantine.

### 5.2 Consensus Guarantees
- **Safety**: No two honest nodes finalize conflicting blocks.
- **Liveness**: Network continues to advance even if \( f \) nodes crash or are malicious.
- **Finality**: Once a block is finalized (2/3+ quorum certificate), it is irreversible.

### 5.3 Attack Resistance
- **VDF ASIC Cheating**: Nodes using ASICs to complete VDFs faster are detected as outliers and blacklisted.
- **Replay Attacks**: Anti-replay caches at Bridge and Conductor layers (24hr TTL).
- **Sybil Attacks**: Ed25519 keypairs required for all instances; PoW challenges for user registration.
- **Eclipse Attacks**: P2P mesh network (libp2p) with bootstrap peers and DHT-based discovery.
- **DoS Attacks**: Rate limiting at Stage (per-user tier) and Bridge (per-peer quotas).

---

## 6. Open & Extensible Network

### 6.1 Third-Party Clients
- Anyone can build a Chorus client (web, mobile, desktop, CLI).
- Clients adhere to the API contract in `Chorus-Client-Spec.md`.
- No approval process; clients simply connect to any Stage instance.
- Third-party clients must respect privacy principles (no telemetry, no timestamp leakage).

### 6.2 Self-Hosted Stages & Bridges
- Anyone can deploy their own Stage and Bridge instances.
- New instances submit join requests to existing network.
- Conductor facilitates BFT vote; if approved (2/3+ majority), new instance joins federation.
- Encourages decentralization and censorship resistance.

### 6.3 ActivityPub Bridge (Optional)
- Stage instances can optionally export public content to ActivityPub (Mastodon, etc.).
- **One-way only**: No inbound content from ActivityPub (prevents metadata contamination).
- Exported content uses pseudonymous actor URIs (no user PII).
- Timestamps derived from day numbers (not real-world time).

---

## 7. Deployment Topology

### 7.1 Single-Instance Deployment (Smallest)
```
┌─────────────┐
│   Clients   │
└──────┬──────┘
       │
┌──────▼──────┐
│    Stage    │◄─┐
└──────┬──────┘  │
       │         │
┌──────▼──────┐  │
│   Bridge    │──┘
└──────┬──────┘
       │
┌──────▼──────┐
│  Conductor  │
└─────────────┘
```
- **Use Case**: Development, testing, small private communities.
- All components run on a single server or Docker Compose stack.

### 7.2 Multi-Instance Federation (Production)
```
┌───────────┐        ┌───────────┐        ┌───────────┐
│ Clients A │        │ Clients B │        │ Clients C │
└─────┬─────┘        └─────┬─────┘        └─────┬─────┘
      │                    │                    │
┌─────▼─────┐        ┌─────▼─────┐        ┌─────▼─────┐
│  Stage A  │        │  Stage B  │        │  Stage C  │
└─────┬─────┘        └─────┬─────┘        └─────┬─────┘
      │                    │                    │
┌─────▼─────┐        ┌─────▼─────┐        ┌─────▼─────┐
│  Bridge A │◄──────►│  Bridge B │◄──────►│  Bridge C │
└─────┬─────┘   P2P  └─────┬─────┘   P2P  └─────┬─────┘
      │                    │                    │
      └────────────────────┼────────────────────┘
                           │
                   ┌───────▼────────┐
                   │   Conductor    │
                   │  (BFT Cluster) │
                   └────────────────┘
```
- **Use Case**: Production networks with multiple operators.
- Each operator runs their own Stage + Bridge; Conductor is federated (or shared).

---

## 8. Key Innovations

### 8.1 Time-Agnostic Consensus (Conductor)
- **First-of-its-kind**: BFT consensus without wall-clock time.
- Uses VDF-proven day counter to maintain temporal ordering without timestamps.
- Protects against temporal correlation attacks (adversary cannot deduce when events occurred).

### 8.2 Privacy-First Federation (Bridge)
- Only transmits day numbers, order IDs, and content hashes.
- Full content stays on originating Stage; peers request only what they need.
- No PII or metadata leakage across federation boundaries.

### 8.3 Open & Extensible (Clients)
- Welcomes third-party clients with no approval process.
- API is open, documented, and versioned.
- Encourages innovation while maintaining privacy guarantees.

---

## 9. Performance Targets

| Metric                          | Target                  |
|---------------------------------|-------------------------|
| Client → Stage Latency          | <100ms (LAN/CDN)        |
| Stage → Bridge Latency          | <50ms (local)           |
| Federation Propagation Time     | <5 seconds (network-wide) |
| VDF Day Advancement             | ~24 hours (reference HW) |
| Consensus Finality              | 2-3 seconds (BFT)       |
| Database Read Latency           | <10ms (PostgreSQL)      |
| WebSocket Event Delivery        | <100ms (real-time)      |

---

## 10. Security & Privacy Audits

### 10.1 Threat Model
- **Adversary Capabilities**: Compromised client, Stage, Bridge, or Conductor node; network eavesdropping; timing analysis.
- **Goals**: De-anonymize users, correlate events to wall-clock time, censor content, disrupt consensus.

### 10.2 Mitigations
- **No Timestamps**: Eliminate temporal correlation vectors.
- **BFT Consensus**: Tolerate \( f < n/3 \) Byzantine nodes.
- **Cryptographic Signatures**: Ed25519 for all inter-node communication.
- **Replay Protection**: Nonce-based caching with TTL.
- **Rate Limiting**: Per-user and per-instance quotas.
- **Blacklisting**: BFT-voted removal of malicious nodes.

### 10.3 Audit Recommendations
- Regular security audits by third-party firms (focus on cryptography, consensus, privacy).
- Chaos engineering tests (network partitions, Byzantine node injection).
- Privacy audits (ensure no timestamp or PII leakage).

---

## 11. Future Directions

- **Sharding**: Partition network by community or geography for scalability.
- **Zero-Knowledge Proofs**: Prove VDF completion without revealing intermediate state.
- **Differential Privacy**: Add noise to event timing for enhanced anonymity.
- **Inbound ActivityPub**: Carefully consider opt-in inbound federation (privacy risks).
- **Mobile-Optimized Stage**: Lightweight Stage instances for resource-constrained environments.

---

## 12. Licensing

All Chorus components: **GPLv3**

---

## 13. Conclusion

The Chorus Network is a pioneering decentralized social platform that achieves **Byzantine fault tolerance**, **high-speed replication**, and **uncompromising anonymity**. By structuring the system into four distinct layers—Clients, Stage, Bridge, and Conductor—Chorus ensures clear separation of concerns, extensibility, and resilience. The VDF-based day counter in Conductor is a world-first innovation that enables time-agnostic consensus, protecting users from temporal correlation attacks while maintaining network integrity. Chorus is not just a social network; it is a blueprint for building privacy-first, decentralized systems in an era where anonymity is under constant threat.

---

**Document Status:** System Architecture v1.0  
**Authors:** Chorus Federation Protocol Team, Hailey  
**Contact:** chorus-team@chorus.social
