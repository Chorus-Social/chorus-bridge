# CFP-011: Conductor — Leaderless, Time-Agnostic, Asynchronous BFT Consensus for Chorus Federation

**Version:** 1.0 
**Date:** October 23, 2025 
**Authors:** Chorus Federation Protocol Team, Hailey

---

## Abstract

Conductor is a leaderless, time-agnostic, asynchronous Byzantine Fault-Tolerant (ABFT) consensus protocol specifically engineered for the Chorus federated social network. By leveraging Verifiable Delay Functions (VDFs) and a unique Day Counter system, Conductor enables distributed Stage instances to maintain federated state and consensus without reliance on real-world timestamps—preserving user anonymity against temporal correlation threats. This CFP captures the entire protocol design, threat model, integration blueprint, and parameters for implementation.

---

## 1. Rationale & Core Goals

- **Purpose-built for Chorus:** Conductor addresses privacy requirements unique to Chorus—removing dependencies on wall-clock time and preserving operational anonymity. 
- **No real-world time:** The protocol is agnostic to real-time, using cryptographic day increments rather than human-readable timestamps. 
- **Byzantine resistance:** Supports full asynchronous operation with f < n/3 BFT, even if network partitions or adversarial nodes are present.
- **Operational integrity:** Guarantees that no instance can advance the Day Counter faster than allowed by the VDF and the federation majority.

---

## 2. System Architecture & Components

### Three-Layer Model

- **Stage Instances:** User-facing Chorus nodes; host users/posts, API.
- **Bridge Protocol:** Interconnects Stage Instances and routes/federates consensus messages.
- **Conductor Consensus Layer:** Sits beneath Bridge; validates state transitions, produces/validates VDF proofs.

### Day Counter System

- Monotonic (Day 0, 1, 2...); not correlated to calendar dates.
- Intra-day: Ordered by Order IDs (not timestamps).
- “Day” increments via VDF; all consensus is against Day Counter, not time.

#### Privacy Guarantee
- Unable to deduce wall-clock date/time from Day or Order ID.
- Even with full protocol data, adversary cannot reconstruct event timing.

---

## 3. Verifiable Delay Functions (VDFs)

- All instances solve a sequential BLAKE3 hash VDF per day.
- VDF is calibrated for ~24h on reference hardware (adjustable).
- Proof is fast to verify (logarithmic time), impossible to shortcut.
- VDF difficulty auto-adjusts across federation as median node speed changes.
- proofs exchanged to validate progression and finality.

---

## 4. Consensus Protocol & Fork Choice

- Tolerates f < n/3 byzantine nodes; 2/3+ required for finality.
- No leader; all nodes communicate proofs, vote/validate state collectively.
- "True day" is finalized via supermajority of valid proofs (with difficulty check).
- Malicious (e.g. ASIC-accelerated) nodes running ahead/behind are detected as outliers, added to blacklist after federated agreement.
- Fork choice: always follow day state backed by 2/3+ federation supermajority.
- Finalized days are irreversible.

---

## 5. Difficulty Adjustment
- Monitors federation-wide median Day Counter advancement.
- Recalibrates VDF iteration target as needed; avoids penalizing honest users.
- Moves steadily (e.g., every 10 days) with smoothing window.
- Single outliers can’t manipulate global settings.

---

## 6. Memory-only Timestamp Validation

- Each node maintains a RAM-only clock to check local VDF duration.
- Used for threat detection (e.g., ASIC cheating detection), not consensus.
- Timestamps never federated, never stored persistently or exposed to API users.
- Survives node restarts with zero forensic trace.

---

## 7. Blacklist, Recovery & Synchronization

- Byzantine nodes (VDF cheating, malicious, or erratic) are voted onto federation-wide blacklist (2/3+ required).
- Node recovery: Pulls missing Days, VDFs, and checkpoints from healthy peers, verifying cryptographically each step.
- Full recovery checkpoints and VDF chains for rapid sync after downtime.

---

## 8. Attack Resilience<br>
- Handles ASIC-powered malicious nodes and coordinated attacks.
- Honest nodes unaffected by malicious outliers thanks to supermajority fork rule.
- Consensus layer cannot be used to fast-forward account ages or manipulate federation time.

---

## 9. Integration with Bridge

- Bridge handles P2P and message routing.
- Conductor runs BFT, VDF, fork-choice logic below.
- Bridge relays only finalized content/events consistent with consensus Day/OrderID.

---

## 10. Implementation Parameters

| Parameter                | Value / Note                                  |
|--------------------------|-----------------------------------------------|
| VDF Hash                 | BLAKE3                                        |
| Iteration Target         | ~24hr / median, configurable                  |
| Proof Size               | ~1KB, fast verification                       |
| Byzantine Tolerance      | f < n/3                                       |
| Finality Threshold       | 2/3+ nodes                                    |
| Difficulty Adjustment    | Every 10 days, exponential scaling allowed    |
| Checkpoint Interval      | Every 10 days                                 |
| Max Proof Window         | Last 30 days                                  |
| Blacklist Consensus      | 2/3+ affirmative vote                         |

---

## 11. Privacy & Anonymity
- No real-world time or correlated metadata leaves node.
- All external values are Day Counter/Order IDs.
- Attacker seizing a node only learns local progression, not federation global or user-unique info.
- Application-layer privacy (e.g., user reminders, posts) must consciously avoid reintroducing time.

---

## 12. Implementation Roadmap

**Phase 1:** BLAKE3 VDF, proof gen/verification, target calibration.
**Phase 2:** BFT fork-choice, blacklist logic, supermajority voting.
**Phase 3:** Difficulty self-tuning and checkpointing system.
**Phase 4:** Bridge integration—message routing and large-scale federation testing.
**Phase 5:** Multi-region security, attack simulations, and internal/external audits.

---

## 13. Technical Appendices

- Full VDF code (see upstream Chorus-bridge repo)
- Consensus message/blacklist schemas
- Recovery/fast-sync state diagrams
- Sample threat model scenarios (ASIC, botnet, byzantine outages)
- Detailed difficulty adjustment formulas

---

## 14. Licensing & Community

- Licensed GPLv3 (consistent with Chorus core)
- Contributor License Agreement (CLA) required: ensures that contributors affirm code is original, and grants Chorus Federation rights to reuse/distribute as GPLv3.

---

## 15. Conclusion

Conductor delivers a unique privacy-anchored consensus protocol for Chorus that replaces timestamps with proof-driven time and delivers robust federation integrity regardless of adversarial or asynchronous environments. This approach not only fits but enhances the democratic, anonymity-first philosophy of Chorus.

---

For practical implementation details, consult the full Conductor specification, reference code, and the Chorus Protocol documentation suite.