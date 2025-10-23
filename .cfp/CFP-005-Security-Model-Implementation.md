# Implementation Plan: CFP-005 Security Model

Status: Draft
Owners: Security & Platform
Scope: Threat mitigations, policy enforcement points, configs

---

## Controls Mapping

- Temporal Integrity
  - Dependency: canonical DayProof per day from validator network.
  - Enforcement: account age increments only when submitted day proof matches canonical.

- Sybil Resistance
  - Ed25519 per account; store BLAKE3(pubkey) only.
  - PoW challenges on registration and sensitive actions; difficulty from settings.
  - Federation whitelist for instance keys.

- BFT Tolerance
  - Consensus threshold configurable; reject proofs without majority.
  - Blacklist validators on repeated divergence.

- DoS/Abuse
  - Rate limits per account tier and per IP (defense-in-depth).
  - Replay caches for federation envelopes and client nonces.
  - Federation API quotas per peer.

- Privacy
  - Replace timestamps with day numbers in all public data models.
  - No cross-instance user linkage; hash-only references.
  - E2E encryption for DMs; no plaintext handling.

---

## Policy Configuration
```yaml
security:
  consensus_threshold: 0.67
  replay_cache_ttl_seconds: 86400
  federation_rate_limits:
    default_rps: 10
    burst: 50
  client_pow:
    register_difficulty: medium
    post_difficulty: low
```

---

## Auditing & Alerts
- Log canonical proof changes and validator divergence events.
- Alert on:
  - Clock drift > 5s
  - DHT peers < minimum
  - Replay cache hit spikes
  - Federation signature failures

---

## Testing
- Red-team replay attempts against federation ingress.
- Load tests across rate limiting tiers.
- Privacy lint: schemas must not include timestamps.

