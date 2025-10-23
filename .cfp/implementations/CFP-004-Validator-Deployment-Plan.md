# Implementation Guide Delta: CFP-004

Status: Draft
Owners: DevOps & Platform
Scope: Operator runbook, configs, compose, observability

---

## Goals
- Provide a clean operator workflow to deploy/monitor a validator node.
- Align with config structure in CFP-001 and produce reproducible environments.

## Operator Checklist
- Keys:
  - Generate Ed25519 keypair → store encrypted at `./keys/validator_key.pem`.
- Config:
  - Edit `validator.yaml` → bootstrap peers, storage path, thresholds.
- Network:
  - Open ports 4001 (P2P) and 9090 (metrics).
- Time:
  - Ensure NTP sync active; monitor drift.

## Compose Snippet
```yaml
version: "3.8"
services:
  validator:
    image: chorus/validator:dev
    ports: ["4001:4001", "9090:9090"]
    volumes:
      - ./validator_data:/app/validator_data
      - ./keys:/app/keys
      - ./validator.yaml:/app/validator.yaml
    restart: unless-stopped
```

## Health & Metrics
- Liveness: `/healthz` returns 200 when event loop active and last publish < 24h.
- Readiness: `/readyz` checks DHT connectivity and storage writable.
- Prometheus:
  - `chorus_proofs_computed_total`
  - `chorus_proof_computation_seconds`
  - `chorus_consensus_agreement_ratio`
  - `chorus_dht_connected_peers`

## Backup & Recovery
- Snapshot local DB weekly to off-box storage.
- Restore sequence:
  - Stop node → restore DB → start node → resync missing days from DHT/IPFS.

## Troubleshooting
- DHT sync stalls: verify bootstrap peer reachability, firewall.
- Low agreement: compare local proof vs canonical; check clock drift alerts.

