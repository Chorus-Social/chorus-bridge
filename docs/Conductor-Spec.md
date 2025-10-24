# Conductor Technical Specification

**Version:** 1.0  
**Date:** October 23, 2025  
**Status:** Technical Specification

---

## Abstract

**Conductor** is the warden and consensus engine of the Chorus network. It is an asynchronous, leaderless Byzantine Fault-Tolerant (ABFT) consensus system designed to ensure that all **Chorus Bridge** instances remain in perfect agreement on the ordering and validity of federation events. Conductor is **the first of its kind** in that it functions without relying on real-world timestamps, instead using a protected internal "true day" counter that is never exposed directly. This day counter is advanced only through cryptographically verified Verifiable Delay Functions (VDFs) combined with BLAKE3 hashing to prove that a day has passed. Conductor dynamically adjusts VDF difficulty for varying computational capabilities, identifies and blacklists malicious instances, and ensures the entire Chorus network operates with unbreakable temporal integrity and anonymity.

---

## 1. Purpose & Scope

**Conductor** serves as:
- The **consensus layer** that orders and commits federation events across the network.
- The **timekeeping authority** that advances the internal day counter via VDFs (without exposing real-world time).
- The **Byzantine fault detector** that identifies malicious nodes attempting to manipulate time or consensus.
- The **network guardian** that facilitates blacklisting and removal of bad actors.

**Design Goals:**
- **Asynchronous BFT**: Tolerates network partitions and delays; liveness achieved via randomization.
- **Time-Agnostic**: No dependency on wall-clock time; all consensus keyed to VDF-proven day numbers.
- **Leaderless**: No single point of failure or censorship.
- **Privacy-Preserving**: Internal day counter never exposed; only VDF proofs and day numbers shared.
- **Adaptive**: Dynamically adjusts VDF difficulty to account for varying hardware capabilities.

**Out of Scope:**
- Direct client interaction (handled by Stage).
- Federation event propagation (handled by Bridge).

---

## 2. Core Responsibilities

### 2.1 Day Counter Management
- Maintain an internal, protected "true day" counter (monotonic, starting from Day 0).
- Advance the day counter **only** when a valid VDF proof is verified.
- Never expose the true day counter directly; only publish day proofs.

### 2.2 VDF Proof Generation & Verification
- Each Conductor instance (or Bridge with Conductor module) computes a VDF proof for the current day.
- VDF uses sequential BLAKE3 hashing (cannot be parallelized or shortcut).
- Proofs are fast to verify (logarithmic time) but slow to compute (~24 hours on reference hardware).

### 2.3 Consensus on Day Advancement
- Collect VDF proofs from all participating Conductor instances.
- Require 2/3+ supermajority agreement before finalizing a day.
- Detect outliers (ASIC-accelerated or lagging nodes) and flag for blacklisting.

### 2.4 Event Ordering & Commitment
- Accept batches of federation events from Bridge instances.
- Order events deterministically within each day (via order IDs, not timestamps).
- Commit finalized blocks with quorum certificates.

### 2.5 Blacklist Management
- Identify malicious nodes (VDF cheating, invalid signatures, Byzantine behavior).
- Facilitate BFT vote (2/3+ required) to blacklist bad actors.
- Relay blacklist updates to all Bridge instances.

---

## 3. Architecture Overview

```
┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
│   Bridge A        │       │   Bridge B        │       │   Bridge C        │
└─────────┬─────────┘       └─────────┬─────────┘       └─────────┬─────────┘
          │                           │                           │
          │ gRPC/libp2p               │ gRPC/libp2p               │ gRPC/libp2p
          ▼                           ▼                           ▼
    ┌──────────────┐            ┌──────────────┐            ┌──────────────┐
    │ Conductor A  │◄──────────►│ Conductor B  │◄──────────►│ Conductor C  │
    └──────────────┘  P2P Mesh  └──────────────┘  P2P Mesh  └──────────────┘
           │                           │                           │
           │                           │                           │
           └───────────────────────────┴───────────────────────────┘
                             VDF Proofs & Consensus
```

### Key Components:
- **VDF Engine**: Computes sequential BLAKE3-based proofs.
- **Consensus Module**: Implements leaderless ABFT with threshold cryptography.
- **Day Counter**: Protected internal state, incremented only via verified VDF.
- **Blacklist Store**: Tracks malicious nodes voted out by BFT consensus.
- **Event Ledger**: Stores ordered, finalized events with quorum certificates.

---

## 4. Technology Stack

- **Language**: Rust (for VDF performance) or Python (for prototype)
- **VDF**: Sequential BLAKE3 hashing (no parallelization possible)
- **Cryptography**: Ed25519 (signatures), BLS (threshold signatures), BLAKE3 (hashing)
- **Networking**: libp2p (gossipsub for proofs) or gRPC (for RPC)
- **Storage**: RocksDB or LMDB (for event ledger, checkpoints, day proofs)
- **Observability**: Prometheus metrics, structured logging

---

## 5. Day Counter System

### 5.1 True Day vs. Exposed Day
- **True Day**: Internal monotonic counter (never exposed, never correlated with real time).
- **Exposed Day**: Day numbers published to Bridge (e.g., Day 0, Day 1, Day 2...).
- **Isolation**: True day is stored in RAM only (ephemeral), never persisted to disk.
- **Purpose**: Prevents forensic reconstruction of timing from seized nodes.

### 5.2 Day Advancement Flow
1. Conductor computes VDF proof for `current_day`.
2. Conductor publishes proof to peer Conductors.
3. Peers verify proof (fast, logarithmic time).
4. If 2/3+ peers submit valid proofs for `current_day`, day is finalized.
5. Conductor advances internal counter: `true_day += 1`.
6. Publish canonical day proof to Bridge.

### 5.3 Day Proof Format
```json
{
  "day_number": 1234,
  "vdf_proof": "hex-bytes",
  "difficulty": 86400000,
  "computed_by": "conductor-1",
  "signature": "hex-signature"
}
```

### 5.4 Privacy Guarantee
- Even with full access to Conductor's state, an adversary cannot deduce:
  - What calendar date a day corresponds to.
  - How long a day took in real time.
  - When events occurred in wall-clock time.

---

## 6. Verifiable Delay Functions (VDFs)

### 6.1 Purpose
- Prove that a certain amount of time has passed **without relying on timestamps**.
- Force sequential computation (cannot be parallelized or accelerated without detection).

### 6.2 Algorithm: Sequential BLAKE3
```python
def compute_vdf(day_number, difficulty):
    seed = BLAKE3(f"chorus-day-{day_number}")
    proof = seed
    for i in range(difficulty):
        proof = BLAKE3(proof)
    return proof
```

- **Difficulty**: Number of iterations (e.g., 86,400,000 for ~24 hours on reference hardware).
- **Proof**: Final BLAKE3 hash after all iterations.
- **Verification**: Fast; re-compute and compare (or use short witness proofs).

### 6.3 Calibration
- **Reference Hardware**: Defined standard (e.g., AWS c5.large instance).
- **Calibration Target**: VDF should take ~24 hours on reference hardware.
- **Dynamic Adjustment**: If federation-wide median completion time drifts, recalibrate difficulty.

### 6.4 ASIC Resistance
- Sequential BLAKE3 is hard to accelerate with ASICs (limited parallelization).
- Nodes running ASICs will be detected as outliers (completing proofs too quickly).
- Outliers flagged for blacklisting via BFT vote.

---

## 7. Consensus Protocol

### 7.1 Leaderless ABFT
- **No leader**: All Conductor instances participate equally.
- **Asynchronous**: No timing assumptions; consensus achieved via randomization and threshold crypto.
- **Byzantine Tolerance**: Tolerates \( f < n/3 \) malicious nodes (requires \( n \geq 3f + 1 \)).

### 7.2 Epochs
- Epochs aligned with day numbers: `epoch = current_day`.
- Each epoch produces one finalized block of ordered events.

### 7.3 Reliable Broadcast (RBC)
- Conductor broadcasts VDF proof to all peers.
- Proofs are erasure-coded and distributed as fragments.
- Peers reconstruct proofs without trusting any single node.

### 7.4 Threshold Encryption
- Event batches encrypted with threshold encryption.
- No single Conductor can decrypt; requires \( t \) out of \( n \) decryption shares.
- Ensures privacy until consensus is reached.

### 7.5 Common Coin
- Randomness source for liveness (breaks ties).
- Derived from threshold BLS signature or external randomness (drand).

### 7.6 Quorum Certificates (QC)
- Finalized blocks include a QC: aggregated signatures from 2/3+ Conductors.
- QC proves that the block is committed and irreversible.

### 7.7 Fork Choice Rule
- Always follow the chain with 2/3+ supermajority.
- Ignore forks with fewer supporters (Byzantine minority).

---

## 8. Difficulty Adjustment

### 8.1 Goal
- Maintain ~24-hour VDF computation time across the federation.
- Adapt to changes in hardware (faster CPUs, more nodes, etc.).

### 8.2 Mechanism
- Every 10 days, Conductor calculates median VDF completion time across all participants.
- If median drifts from target (e.g., 20 hours or 28 hours), adjust difficulty:
  ```
  new_difficulty = current_difficulty * (target_time / median_time)
  ```
- Adjustment is smooth (exponential moving average) to avoid volatility.

### 8.3 Protection Against Outliers
- Single fast or slow node cannot skew adjustment (uses median, not mean).
- Outliers (e.g., ASIC users) are flagged and blacklisted before influencing adjustment.

---

## 9. Blacklist & Malicious Node Removal

### 9.1 Detection Criteria
- **VDF cheating**: Node completes proofs significantly faster than median (ASIC suspected).
- **Invalid proofs**: Node submits proofs that fail verification.
- **Byzantine behavior**: Node submits conflicting data or votes.
- **Replay attacks**: Node resubmits old proofs.

### 9.2 Evidence Collection
- Conductor monitors peer behavior and collects evidence (proof timestamps, invalid signatures, etc.).
- Evidence includes cryptographic proofs (cannot be forged).

### 9.3 BFT Vote
1. Conductor submits evidence to peers.
2. Peers review evidence and vote (approve/reject).
3. If 2/3+ vote to blacklist, node is added to blacklist.
4. Blacklist update is signed with quorum certificate.

### 9.4 Enforcement
- Blacklisted nodes excluded from:
  - VDF consensus (proofs ignored).
  - Event ordering (batches rejected).
  - P2P network (disconnected by peers).
- Bridge instances relay blacklist to Stages (stop federating with bad actors).

### 9.5 Recovery
- Blacklisted nodes can appeal via governance (2/3+ vote to unblock).
- Must provide evidence of corrected behavior.

---

## 10. Memory-Only Timestamp Validation

### 10.1 Purpose
- Detect ASIC cheating or clock drift (without leaking timestamps).
- Used for threat detection only (not consensus).

### 10.2 Mechanism
- Each Conductor maintains a RAM-only clock (ephemeral, non-persistent).
- When VDF completes, Conductor checks: `true_day == computed_day`.
- If mismatch (e.g., VDF finished too fast), flag as outlier.

### 10.3 Privacy
- Clock exists only in RAM; zeroed on restart.
- Never persisted to disk or transmitted to peers.
- Cannot be forensically recovered from seized nodes.

---

## 11. Event Ordering & Commitment

### 11.1 Event Batches
- Bridge instances submit batches of federation events to Conductor.
- Events include: posts, votes, registrations, moderation actions.

### 11.2 Ordering
- Events ordered deterministically within each day:
  - Primary: `creation_day` (day number).
  - Secondary: `order_index` (within-day sequence, assigned by Conductor).
- No timestamps used.

### 11.3 Commitment
- Conductor runs BFT consensus on event order.
- Finalized blocks include:
  - Merkle root of events.
  - Quorum certificate (2/3+ signatures).
- Blocks are immutable once finalized.

### 11.4 Relay to Bridge
- Conductor publishes finalized block to Bridge instances.
- Bridge relays events to Stages.
- Stages update local databases.

---

## 12. Network Participation

### 12.1 Joining as a Conductor
1. Deploy Conductor instance.
2. Generate Ed25519 keypair.
3. Submit join request to existing Conductors.
4. Existing Conductors vote (2/3+ required).
5. If approved, new Conductor receives bootstrap data (recent blocks, VDF chain).

### 12.2 Bootstrap & Synchronization
- New Conductor requests:
  - Historical VDF proofs (verify day chain).
  - Finalized blocks (reconstruct state).
  - Current blacklist.
- Verification: Each day proof must chain to previous proof; all blocks must have valid QCs.

---

## 13. API Surface

### 13.1 Bridge-to-Conductor API

#### `POST /conductor/submit-batch`
- **Purpose**: Submit batch of events for ordering.
- **Request**:
  ```json
  {
    "epoch": 1234,
    "events": [
      { "type": "PostAnnouncement", "hash": "hex" },
      { "type": "UserRegistration", "hash": "hex" }
    ]
  }
  ```
- **Response**:
  ```json
  {
    "batch_id": "hex",
    "status": "pending"
  }
  ```

#### `GET /conductor/block/{epoch}`
- **Purpose**: Retrieve finalized block for an epoch.
- **Response**:
  ```json
  {
    "epoch": 1234,
    "block_hash": "hex",
    "merkle_root": "hex",
    "events": ["hex-1", "hex-2"],
    "quorum_cert": "hex"
  }
  ```

#### `GET /conductor/day-proof/{day}`
- **Purpose**: Retrieve canonical VDF proof for a day.
- **Response**:
  ```json
  {
    "day_number": 1234,
    "vdf_proof": "hex",
    "difficulty": 86400000,
    "quorum_cert": "hex"
  }
  ```

### 13.2 Conductor-to-Conductor API (P2P)

#### `SubmitVDFProof(day, proof, signature)`
- Submit VDF proof to peers for verification and consensus.

#### `RequestVDFProof(day)`
- Request VDF proof from peer (for sync).

#### `VoteBlacklist(node_id, evidence)`
- Submit evidence and vote to blacklist a node.

#### `RequestBlacklist()`
- Request current blacklist.

---

## 14. Implementation Parameters

| Parameter                | Value / Note                          |
|--------------------------|---------------------------------------|
| VDF Hash                 | BLAKE3                                |
| Iteration Target         | ~24 hours on reference hardware       |
| Proof Size               | ~1 KB (fast verification)             |
| Byzantine Tolerance      | \( f < n/3 \)                         |
| Finality Threshold       | 2/3+ nodes                            |
| Difficulty Adjustment    | Every 10 days                         |
| Checkpoint Interval      | Every 10 days                         |
| Max Proof Window         | Last 30 days (older pruned)           |
| Blacklist Consensus      | 2/3+ affirmative vote                 |

---

## 15. Privacy & Anonymity

### 15.1 No Time Leakage
- True day counter never exposed.
- All external values are day numbers (no correlation with calendar dates).
- VDF proofs cannot be used to deduce wall-clock time.

### 15.2 Event Privacy
- Events transmitted as hashes (full content stays on originating Stage).
- Threshold encryption ensures no single Conductor sees event content before consensus.

### 15.3 Forensic Resistance
- RAM-only clock (zeroed on restart).
- No persistent timestamps anywhere in Conductor state.
- Seized node reveals only day numbers and VDF proofs (no timing info).

---

## 16. Observability

### 16.1 Metrics (Prometheus)
- `conductor_vdf_duration_seconds`
- `conductor_day_number_current`
- `conductor_consensus_latency_seconds`
- `conductor_blacklist_size`
- `conductor_peer_count`

### 16.2 Logging
- Structured JSON logs (no PII).
- Log: day advances, VDF completions, blacklist votes, consensus decisions.
- Never log: timestamps, full event content.

### 16.3 Health Endpoints
- `GET /health/live`: Liveness probe.
- `GET /health/ready`: Readiness probe (checks peer connectivity, VDF engine status).

---

## 17. Deployment

### 17.1 Docker Compose Example
```yaml
version: "3.8"
services:
  conductor:
    image: chorus/conductor:latest
    ports: ["9090:9090", "4002:4002"]
    environment:
      - CONDUCTOR_ID=conductor-1
      - VDF_DIFFICULTY=86400000
      - CONSENSUS_THRESHOLD=0.67
    volumes:
      - ./keys:/app/keys
      - ./conductor.yaml:/app/conductor.yaml
      - conductor_data:/app/conductor_data

volumes:
  conductor_data:
```

### 17.2 Configuration (conductor.yaml)
```yaml
conductor:
  instance_id: conductor-1
  keypair_path: /keys/conductor.key

  vdf:
    difficulty: 86400000
    reference_hardware: aws-c5-large
    adjustment_interval_days: 10

  network:
    listen_address: 0.0.0.0:4002
    bootstrap_peers:
      - /ip4/1.2.3.4/tcp/4002/p2p/QmDEF

  consensus:
    min_nodes: 3
    threshold: 0.67
    timeout_seconds: 120

  storage:
    backend: rocksdb
    path: ./conductor_data

  monitoring:
    prometheus_port: 9090
    log_level: INFO
```

---

## 18. Testing

- Unit tests for VDF computation and verification.
- Integration tests with mock Bridge instances.
- Chaos tests: ASIC attackers, Byzantine nodes, network partitions.
- Security audits: ensure no timing leaks.

---

## 19. Future Directions

- **Hardware-Specific VDFs**: Custom VDF per node class (cloud vs. bare metal).
- **Zero-Knowledge Proofs**: Prove VDF completion without revealing intermediate state.
- **Multi-Day Epochs**: Support epochs spanning multiple days for very large networks.

---

## 20. Licensing

**GPLv3**

---

## 21. Conclusion

Conductor is the first-of-its-kind consensus system that operates without real-world timestamps, using VDF-proven day counters to maintain temporal integrity while preserving absolute anonymity. By dynamically adjusting difficulty, detecting and blacklisting malicious actors, and integrating seamlessly with Chorus Bridge, Conductor ensures the Chorus network remains secure, scalable, and true to its privacy-first mission.

---

**Document Status:** Technical Specification v1.0  
**Contact:** chorus-team@chorus.social
