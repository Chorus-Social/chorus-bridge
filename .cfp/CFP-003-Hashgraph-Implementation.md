# Implementation Plan: CFP-003 Hashgraph Integration

Status: Draft
Owners: Federation Platform Team
Scope: Anchoring critical federation events to a consensus layer

---

## Objectives
- Anchor critical events (canonical day proofs, membership changes, disputes) to a BFT ledger.
- Provide an abstraction to support Hedera (public) and Tendermint (private) backends.
- Preserve privacy by submitting only event hashes.

## Deliverables
- Provider abstraction: `hashgraph provider = hedera | tendermint` (configured).
- Event format definition and hashing policy.
- Submit/confirm query interface (idempotent operations).
- Operator documentation and compose snippets for local Tendermint.

---

## Event Format (serialized JSON prior to hashing)
```json
{
  "type": "DayProof",
  "instance": "chorus1.example.net",
  "day": 123,
  "proof_hash": "hex",
  "validators": ["hex-pubkey"],
  "timestamp": 1729670400
}
```

Hashing: `BLAKE3(json_canonical_bytes)` → `event_hash` (hex)

---

## Provider Abstraction

### Config
```yaml
hashgraph:
  provider: hedera # or tendermint
  hedera:
    network: testnet
    topic_id: 0.0.XXXX
    operator_account: 0.0.1234
    operator_key_path: /secrets/hedera_operator.key
  tendermint:
    rpc_url: http://localhost:26657
```

### Operations
- `submit(event_hash)` → returns `tx_id`
- `confirm(tx_id)` → returns `confirmed | timeout`
- `query(event_hash)` → returns `tx_id | not_found`

---

## Anchoring Policy
- DayProof: single event per day post-consensus; submitted by any validator observing consensus.
- Membership: joins/leaves recorded with peer identity and quorum evidence.
- Disputes: conflict description object; resolved status recorded afterward.

---

## Deployment

### Tendermint Local (dev/test)
```yaml
version: "3.8"
services:
  tendermint:
    image: tendermint/tendermint
    command: ["node", "--proxy_app=kv"]
    ports: ["26657:26657", "26656:26656"]
```

### Hedera
- Use testnet for development with operator credentials stored in secrets.

---

## Rollout Plan
1. Implement provider abstraction with no-op/stub provider.
2. Add Tendermint submit/query path for local testing.
3. Integrate DayProof anchoring post-consensus.
4. Add Hedera provider integration feature-flagged.

## Testing
- Deterministic canonical JSON and hash computation.
- Idempotent submission and confirm logic.
- Failure handling: transient RPC errors, timeouts.

## Risks
- Public ledger costs (Hedera) and rate limits.
- Privacy: ensure only hashes leave the system.

