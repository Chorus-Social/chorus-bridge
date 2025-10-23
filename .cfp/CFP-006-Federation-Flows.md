# CFP-006: Federation Flows

**Version:** 1.0.0
**Status:** Draft
**Date:** October 23, 2025
**Authors:** Chorus Federation Protocol Team

---

## Abstract
This document provides sequence diagrams and descriptions for key federation flows in Chorus: user registration, cross-instance post propagation, day proof consensus, instance join, and distributed moderation actions.

---

## 1. User Registration Flow
```
User        Instance        Validator Network
 |              |                |
 |---register-->|                |
 |              |                |
 |<-day_proof---|                |
 |              |<---get_day-----|
 |              |---verify------>|
 |              |<--valid ok-----|
 |--use app-----|                |
```

---

## 2. Cross-Instance Post Propagation
```
User     Instance A     Instance B       Federation Network
 |          |                 |                 |
 |--post--->|                 |                 |
 |          |---announce----->|                 |
 |          |                 |---relay-------->|
 |          |                 |<--acknowledge---|
 |<--feed----|                 |                 |
```

---

## 3. Day Proof Consensus
```
Validator 1    Validator 2    DHT      Consensus Module
    |              |            |              |
    |--compute---->|            |              |
    |              |---push---->|              |
    |---send------>|---send--->|              |
    |<-----aggregate--------------< reach >-----|
    |---publish canonical proof---|              |
```

---

## 4. Instance Joining Federation
```
Instance    Federation Gateway   Validator
   |               |                |
   |--join req---->|                |
   |               |--validate----->|
   |               |<--ok-----------|
   |<-----join status----------------|
```

---

## 5. Moderation Actions Across Federation
```
Moderator    Instance A    Instance B
   |             |             |
   |--flag------>|             |
   |             |---relay---> |
   |             |<--ack------>|
   |<--------status------------|
```

---

## 6. Sequence Diagram Notes
- All communication uses signed messages by Ed25519 keys
- No user metadata leaked in any federation cross-flow

---

**Document Status:** Draft v1.0.0
**Contact:** chorus-federation@example.com