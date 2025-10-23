# CFP-005: Security Model

**Version:** 1.0.0
**Status:** Draft
**Date:** October 23, 2025
**Authors:** Chorus Federation Protocol Team

---

## Abstract
This document details the security threats, mitigations, and guarantees provided by the Chorus Federation Protocol, including Byzantine fault tolerance, Sybil resistance, privacy, and cryptographically enforced temporal integrity.

---

## 1. Threat Analysis

### 1.1 Temporal Manipulation
- **Threat:** Attackers rapidly age accounts by incrementing system clock
- **Mitigation:** VDF proofs (sequential, hardware-agnostic)

### 1.2 Sybil Attacks
- **Threat:** Creation of millions of fake nodes/users
- **Mitigation:** Ed25519 keys per account, proof-of-work barrier, federation whitelist for nodes

### 1.3 Malicious Validators
- **Threat:** Colluding validators submit fake proofs
- **Mitigation:** Byzantine fault tolerant consensus (67% honest nodes required)

### 1.4 DoS Attacks (Network/Node-Level)
- **Threat:** Flooding with federation messages or DHT queries
- **Mitigation:** Rate limiting on APIs, signature checks, DHT query throttling

### 1.5 Privacy Erosion
- **Threat:** Deanonymization through metadata/timestamps
- **Mitigation:** No timestamps in data; only day numbers, minimal metadata, no cross-instance correlation

---

## 2. Byzantine Fault Tolerance
- Consensus threshold set for tolerance up to 33% malicious validators
- Canonical proofs only become active with 67% majority
- Nodes can be blacklisted if detected as malicious

---

## 3. Temporal Integrity
- Sequential VDF ensures real time has elapsed for every account age change
- Day proofs must match network canonical value
- Attackers cannot precompute or speed up chain, must follow wall-clock time

---

## 4. Sybil Resistance
- PoW for every account operation
- Validator nodes have unique Ed25519 identity (public key listed in federation config)
- Instance join requests must be approved and signed by trusted peers

---

## 5. Privacy Guarantees
- No user behavioral or reputation tracking
- No timestamps, only anonymized day numbers
- End-to-end encrypted messaging (NaCl sealed box)
- Federated posts are only linked by anonymized hash

---

## 6. Network Partition & Recovery
- Detects and logs partitioning events
- Instances choose major partition on split
- Anchored hashgraph used to settle disputes post-recovery

---

## 7. Auditability
- Canonical proofs and hashgraph events can be inspected by any party
- Audit tools in the admin UI allow export and public proof validation

---

**Document Status:** Draft v1.0.0
**Contact:** chorus-federation@example.com