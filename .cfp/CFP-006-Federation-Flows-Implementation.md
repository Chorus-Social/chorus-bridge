# Implementation Plan: CFP-006 Federation Flows

Status: Draft
Owners: Federation Platform Team
Scope: Sequence-to-implementation mapping, queues, processors, feature flags

---

## Flow-to-Component Mapping

### 1) User Registration
- Inputs: registration envelope + PoW + signed challenge.
- Steps:
  - Validate PoW, verify signature, derive pubkey hash.
  - Fetch canonical day proof; set `creation_day` only.
  - Persist identity (hash-only), issue token.

### 2) Cross-Instance Post Propagation
- Producer: Instance A → `PostAnnouncement` to peers.
- Consumer: Instance B → validate → enqueue local feed update.
- Fanout: internal WS `/ws/feed` and local consumers.

### 3) Day Proof Consensus
- Validators publish individual proofs.
- Consensus module aggregates → publishes canonical to DHT.
- Instances fetch canonical on demand/cache.

### 4) Instance Join
- Join request message → validate signature → manual/auto approval policy.
- Update trust store and broadcast membership change (optionally anchored).

### 5) Moderation Across Federation
- ModerationEvent flow → validate → update queue → local policy enforcement.
- No personal data propagation.

---

## Internal Queues & Topics
- `federation.inbound` — validated envelopes for processing.
- `feed.updates` — post announcements to local feed.
- `moderation.events` — moderation signals across communities.

---

## Feature Flags
```yaml
features:
  federation_post_announce: true
  federation_user_registration: false
  federation_moderation_events: true
  federation_day_proof_consumption: true
```

---

## Error Handling
- Reject unknown peers and malformed messages with structured errors.
- Quarantine envelopes that fail schema validation for operator review.

---

## Testing Strategy
- Integration tests with two instances and a local validator stub.
- Golden flow replays for post propagation and moderation.

