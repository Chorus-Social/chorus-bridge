# Implementation Plan: CFP-001 Validator Network

Status: Draft
Owners: Federation Platform Team
Scope: Validator service, proofs storage, DHT, consensus surface, observability

---

## Objectives
- Provide a deterministic, hardware-agnostic day-proof generation and verification surface.
- Expose a canonical proof retrieval interface to Chorus instances without leaking timestamps.
- Operate in a separate service (container) to isolate resource usage and simplify deployment.

## Deliverables
- Containerized validator service image and compose snippet.
- Config file `validator.yaml` (+ env overrides) with DHT/consensus/storage.
- DHT publication/retrieval interface and canonicalization protocol hooks.
- Local proof archive using an embedded KV store (RocksDB or LMDB).
- Prometheus/health endpoints for liveness and metrics.

## Non-Goals
- No integration of Python-based VDF here; actual computation engine chosen later.
- No validator rewards/leader election; altruistic operation only for now.

---

## Architecture
- Process boundaries:
  - Validator Service (separate container) publishes day proofs to DHT and archives locally.
  - Chorus Stage instances read canonical proofs via REST/DHT, cache, and validate account ages.
- Networking:
  - libp2p DHT (Kademlia) with bootstrap peers configured.
  - Optional IPFS pinning for historical snapshots.
- Consensus:
  - Majority threshold configurable (default 0.67). Canonicalization achieved via network majority.

### Components
- Proof Engine: sequential VDF runner (pluggable; CLI or subprocess).
- DHT Layer: publish `<key=/chorus/proofs/day/{N}>` with validator-signed proof objects.
- Consensus Coordinator: aggregates peer proofs, compares, publishes canonical record.
- Storage: key `proof:day:{N}` => serialized proof record.
- Observability: Prometheus exporter, readiness/liveness probes.

---

## Interfaces

### Storage Keys
- `proof:day:{day_number}` → serialized proof record
- `canonical:day:{day_number}` → serialized canonical proof pointer/record

### DHT Keys
- `/chorus/proofs/day/{day}` → canonical proof record (when available)
- `/chorus/proofs/day/{day}/validator/{pubkey}` → individual validator proof

### Proof Object (canonical JSON shape)
```json
{
  "day_number": 1234,
  "proof": "hex-bytes",
  "computed_at": 1729670400,
  "validator_id": "hex-pubkey",
  "signature": "hex-signature"
}
```

---

## Configuration

### validator.yaml
```yaml
validator:
  keypair_path: ./keys/validator_key.pem
  network:
    listen_address: 0.0.0.0:4001
    bootstrap_peers: []
    dht:
      protocol: kademlia
      replication_factor: 20
      query_timeout: 60
  vdf:
    iterations: 86400000
    progress_interval: 1000000
  storage:
    backend: rocksdb
    path: ./validator_data
  consensus:
    min_validators: 3
    threshold: 0.67
    timeout: 120
  monitoring:
    prometheus_port: 9090
    log_level: INFO
```

### Env Overrides
```sh
VALIDATOR_KEYPAIR_PATH=./keys/validator_key.pem
VALIDATOR_BOOTSTRAP_PEERS=/ip4/1.2.3.4/tcp/4001/p2p/QmABC
VALIDATOR_STORAGE_PATH=./validator_data
CONSENSUS_THRESHOLD=0.67
```

---

## Deployment

### Dockerfile (language-agnostic base)
```Dockerfile
FROM debian:stable-slim
WORKDIR /app
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY validator.yaml ./
# Copy binaries/scripts later; no language-specific runtime committed yet
EXPOSE 4001 9090
CMD ["/app/validator", "--config", "/app/validator.yaml"]
```

### docker-compose.yaml
```yaml
version: "3.8"
services:
  validator:
    image: chorus/validator:dev
    container_name: chorus-validator
    ports: ["4001:4001", "9090:9090"]
    volumes:
      - ./validator_data:/app/validator_data
      - ./keys:/app/keys
      - ./validator.yaml:/app/validator.yaml
    restart: unless-stopped
```

---

## Rollout Plan
1. Implement DHT publish/fetch surface (no VDF yet; use fixtures).
2. Add storage layer with canonical record pointers.
3. Integrate consensus aggregation and threshold policy.
4. Wire Prometheus and health checks.
5. Replace fixtures with real VDF engine and key management.

## Testing
- Fixture-based proofs for day `N` with known canonical values.
- Consensus simulation with 3–5 local nodes in docker-compose.
- DHT fault injection (missing/duplicate/conflicting proofs).

## Risks
- DHT churn and slow convergence → longer consensus time windows.
- Storage corruption → multi-file backup and periodic snapshot export.
- Clock drift → rely on host NTP; alert on >5s drift.

## Open Questions
- Final choice of KV backend (RocksDB vs LMDB) for portability.
- Cross-language DHT library compatibility and maintenance.

