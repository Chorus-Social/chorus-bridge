# CFP-003: Hashgraph Integration

**Version:** 1.0.0
**Status:** Draft
**Date:** October 23, 2025
**Authors:** Chorus Federation Protocol Team

---

## Abstract
This document specifies consensus integration for critical events using a hashgraph layer over the default DHT, such as for day proofs, dispute resolution, and network configuration. It discusses when to use the hashgraph, technical integration of Hedera Hashgraph or Tendermint, critical event transaction formats, cost and performance analysis, and security considerations.

---

## 1. Background & Motivation

DHT achieves eventual consistency, but certain events—like canonical day proof publishing and network disputes—require stronger distributed consensus guarantees. A hashgraph provides:
- Immutable record for critical events
- Byzantine Fault Tolerance (BFT)
- Rapid dispute resolution

---

## 2. When To Use Consensus Layer

Only significant events are anchored to the hashgraph, such as:
- Canonical day proof publishing
- Federation membership changes (join/leave)
- Dispute/conflict events between instances

Routine data (posts, votes) remains on the DHT for efficiency and privacy.

---

## 3. Hashgraph Technology Selection

### 3.1 Options
- **Hedera Hashgraph:** Public ledger, high throughput, cryptographically fair
- **Tendermint:** Private, permissioned, well-supported (used by Cosmos)

Chorus recommends:
- **Tier 3 federation:** Use Hedera or public hashgraph
- **Tier 2:** Tendermint cluster by trusted instances

---

## 4. Transaction Format

All events to be anchored are turned into hashgraph transactions:
```json
{
  "type": "DayProof",
  "instance": "chorus1.example.net",
  "day": 123,
  "proof_hash": "...",
  "validators": ["pubkey1", "pubkey2", ...],
  "timestamp": 1729670400
}
```

Events are hashed and the hash submitted to the hashgraph. Each instance retains local event data for privacy.

---

## 5. Example Implementation

### 5.1 Using Hedera SDK (Python)
```python
from hedera import (Client, AccountId, PrivateKey, Transaction)

client = Client.forTestnet()
operator_account = AccountId("0.0.1234")
operator_key = PrivateKey.fromString("<private-key>")
client.setOperator(operator_account, operator_key)

message_hash = blake3(transaction_json.encode()).digest()
transaction = (
    Transaction()
    .setTopicId("<topic-id>")
    .setMessage(message_hash)
    .execute(client)
)
```

### 5.2 Using Tendermint (Simple REST)
```bash
curl -X POST http://localhost:26657/broadcast_tx_commit \
  -d '{ "tx": "<transaction-hash>" }'
```

---

## 6. Costs
- **Hedera:** Public; cost per transaction; has testnet and mainnet ($)
- **Tendermint:** Free; requires consensus node operation

---

## 7. Security and Resilience

- **Partial Trust Model:** Only anchors critical events
- **Byzantine Tolerant:** Resistant to malicious collusion up to ~33%
- **Immutable Timeline:** All anchored events are publicly visible and auditable

---

## 8. Dispute Resolution Process

1. Instance(s) submit conflict event to hashgraph
2. All parties verify canonical hash
3. Federation policy determines resolution (e.g., majority vote)

---

## 9. Diagnostics and Monitoring
- All hashgraph submissions logged to local validator node
- Admin UI shows anchored events for audit

---

**Document Status:** Draft v1.0.0
**Contact:** chorus-federation@example.com