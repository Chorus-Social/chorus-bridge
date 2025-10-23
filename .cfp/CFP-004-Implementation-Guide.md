# CFP-004: Implementation Guide

**Version:** 1.0.0
**Status:** Draft
**Date:** October 23, 2025
**Authors:** Chorus Federation Protocol Team

---

## Abstract
This guide provides a step-by-step workflow for deploying and running a Chorus validator node and joining the federation network. Also included are Docker compose setup, configuration files, and troubleshooting advice for new federation operators.

---

## 1. Prerequisites
- Python 3.14+
- Docker (latest recommended)
- Access to at least one federation peer instance for bootstrapping
- Registered Ed25519 keypair for validator

---

## 2. Step-By-Step Deployment
### 2.1 Initialize Environment
- Clone the Chorus Stage repository
- Install necessary dependencies:
```
git clone https://github.com/Chorus-Social/chorus-stage
cd chorus-stage
pip install -r requirements.txt
```

### 2.2 Generate Validator Keypair
- Run the provided script
```
python generate_keys.py --output ./keys/validator_key.pem
```

### 2.3 Configure Validator
- Edit `validator.yaml` to specify keys, bootstrap peers, DHT options, and storage

### 2.4 Launch Validator Node with Docker Compose
- Example files:
```yaml
version: "3.8"
services:
 validator:
   build: .
   ports:
     - "4001:4001"
     - "9090:9090"
   volumes:
     - ./validator_data:/app/validator_data
     - ./keys:/app/keys
     - ./validator.yaml:/app/validator.yaml
```
Run:
```
docker compose up -d
```

---

## 3. Joining Federation Network
- Specify trusted peers in `validator.yaml`
- Submit a signed join request via `/federation/message`
- Wait for consensus via hashgraph/DHT
- Check `/federation/peers` for status

---

## 4. Running & Monitoring
- Validator auto-starts at midnight UTC, computing proofs daily
- Prometheus metrics on port 9090
- Logs saved to `/app/logs` directory

### 4.1 Restart Node
```
docker compose restart validator
```

---

## 5. Common Pitfalls & Troubleshooting
- Ports 4001 (P2P) and 9090 (metrics) must be open
- Ensure NTP time synchronization is active on host
- Keypair corruption: regenerate and re-register
- DHT sync issues: Check bootstrap peer availability
---

## 6. Configuration Example
```yaml
validator:
  keypair_path: "./keys/validator_key.pem"
  network:
    listen_address: "0.0.0.0:4001"
    bootstrap_peers:
      - "/ip4/1.2.3.4/tcp/4001/p2p/QmABC123"
  vdf:
    iterations: 86400000
  storage:
    backend: "rocksdb"
    path: "./validator_data"
  consensus:
    min_validators: 3
    threshold: 0.67
  monitoring:
    prometheus_port: 9090
    log_level: "INFO"
```
---

## 7. Updating and Maintaining
- Periodically update from GitHub
- Validate node with testnet daily
- Publish proofs automatically

---

**Document Status:** Draft v1.0.0
**Contact:** chorus-federation@example.com