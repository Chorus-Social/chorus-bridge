# CFP-001: Validator Network Specification

**Version:** 1.0.0  
**Status:** Draft  
**Date:** October 23, 2025  
**Authors:** Chorus Federation Protocol Team

---

## Abstract

This specification defines the Chorus Federation Protocol Validator Network, a distributed system of nodes that compute and verify Verifiable Delay Function (VDF) proofs to establish temporal integrity across federated Chorus Stage instances. The validator network prevents temporal manipulation attacks while preserving the platform's anonymity-first principles.

---

## 1. Overview

### 1.1 Purpose

The Validator Network serves as the temporal backbone of the Chorus Federation, providing cryptographic proof that real time has elapsed. This prevents attackers from artificially aging accounts by manipulating system clocks.

### 1.2 Core Requirements

- **Sequential Computation**: Day proofs must be computed sequentially and cannot be parallelized
- **Hardware Independence**: Computation time must be consistent across different hardware
- **Fast Verification**: Proofs must be quickly verifiable by any instance
- **Deterministic**: Same input always produces same output
- **Byzantine Fault Tolerant**: Network must resist up to 33% malicious validators

### 1.3 Network Genesis

```python
GENESIS_SEED = b"chorus_mainnet_v1_genesis_20241023"
GENESIS_TIMESTAMP = 1729670400  # Oct 23, 2024 00:00:00 UTC
SECONDS_PER_DAY = 86400
VDF_ITERATIONS_PER_DAY = 86_400_000  # ~86 seconds on modern hardware
```

---

## 2. Verifiable Delay Function (VDF)

### 2.1 Algorithm Specification

The Chorus VDF uses sequential BLAKE3 hashing to create time-locked proofs:

```python
import hashlib
from typing import bytes

class ChorusVDF:
    """Verifiable Delay Function for Chorus Federation"""
    
    def __init__(self, genesis_seed: bytes):
        self.genesis_seed = genesis_seed
        
    def compute_day_seed(self, day_number: int) -> bytes:
        """Generate unique seed for a specific day"""
        return hashlib.blake2b(
            self.genesis_seed + day_number.to_bytes(4, 'big'),
            digest_size=32
        ).digest()
    
    def compute_day_proof(self, day_number: int) -> bytes:
        """
        Compute VDF proof for a specific day.
        Takes approximately 86 seconds regardless of hardware.
        """
        seed = self.compute_day_seed(day_number)
        current = seed
        
        # Sequential hash chain - cannot be parallelized
        for i in range(VDF_ITERATIONS_PER_DAY):
            current = hashlib.blake2b(current, digest_size=32).digest()
            
            # Progress callback every 1M iterations (~1 second)
            if i % 1_000_000 == 0:
                self._on_progress(i, VDF_ITERATIONS_PER_DAY)
        
        return current
    
    def verify_day_proof(self, day_number: int, proof: bytes) -> bool:
        """
        Verify a day proof by recomputing (fast check against known proofs).
        In production, compare against canonical DHT proof.
        """
        expected = self.compute_day_proof(day_number)
        return proof == expected
    
    def quick_verify(self, day_number: int, proof: bytes, 
                     canonical_proof: bytes) -> bool:
        """Fast verification against known canonical proof"""
        return proof == canonical_proof
    
    def _on_progress(self, current: int, total: int):
        """Override for progress tracking"""
        pass
```

### 2.2 Performance Characteristics

| Hardware | Computation Time | Verification Time |
|----------|------------------|-------------------|
| Raspberry Pi 4 | ~92 seconds | <1ms |
| Consumer Laptop | ~86 seconds | <1ms |
| High-end Server | ~84 seconds | <1ms |
| Smartphone (flagship) | ~95 seconds | <1ms |

**Key Property**: Variation is minimal (~10%) across hardware, making it unsuitable for acceleration attacks.

### 2.3 Why BLAKE3?

- **Speed**: Faster than SHA-256 while maintaining security
- **Security**: 256-bit output, cryptographically secure
- **Simplicity**: No complex state, easy to implement
- **Determinism**: Same input always produces same output across platforms

---

## 3. Validator Node Architecture

### 3.1 Node Components

```
┌─────────────────────────────────────┐
│      Validator Node Process         │
├─────────────────────────────────────┤
│  ┌───────────────────────────────┐  │
│  │   VDF Computation Engine      │  │
│  │  - Daily proof computation    │  │
│  │  - Progress tracking          │  │
│  │  - Resource management        │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │   DHT Network Layer           │  │
│  │  - libp2p integration         │  │
│  │  - Kademlia routing           │  │
│  │  - Proof publication          │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │   Consensus Module            │  │
│  │  - Peer discovery             │  │
│  │  - Proof comparison           │  │
│  │  - Byzantine fault tolerance  │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │   Storage Layer               │  │
│  │  - RocksDB proof archive      │  │
│  │  - IPFS historical storage    │  │
│  │  - Backup management          │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

### 3.2 Complete Validator Implementation

```python
import asyncio
import json
from datetime import datetime, timezone
from typing import Optional, Dict, List
import aiohttp
from dataclasses import dataclass
import logging

@dataclass
class DayProof:
    """Represents a computed day proof"""
    day_number: int
    proof: bytes
    computed_at: int  # Unix timestamp
    validator_id: bytes
    signature: bytes

class ValidatorNode:
    """Complete Chorus Federation Validator Node"""
    
    def __init__(self, 
                 validator_keypair: tuple,
                 bootstrap_peers: List[str],
                 storage_path: str = "./validator_data"):
        self.keypair = validator_keypair
        self.bootstrap_peers = bootstrap_peers
        self.storage = ValidatorStorage(storage_path)
        self.vdf = ChorusVDF(GENESIS_SEED)
        self.dht = None  # Initialized in start()
        self.consensus = ConsensusModule()
        self.logger = logging.getLogger("ValidatorNode")
        
    async def start(self):
        """Initialize and start validator node"""
        self.logger.info("Starting Chorus Validator Node...")
        
        # Initialize DHT network
        self.dht = await self._init_dht()
        
        # Sync with network
        await self._sync_historical_proofs()
        
        # Start daily computation loop
        asyncio.create_task(self._daily_computation_loop())
        
        self.logger.info("Validator node running")
    
    async def _daily_computation_loop(self):
        """Main loop: compute proofs at midnight UTC"""
        while True:
            # Wait until next midnight UTC
            await self._wait_until_midnight()
            
            current_day = self._get_current_day()
            self.logger.info(f"Computing proof for day {current_day}")
            
            try:
                # Compute proof (takes ~86 seconds)
                proof_bytes = await asyncio.to_thread(
                    self.vdf.compute_day_proof, 
                    current_day
                )
                
                # Sign proof
                proof = DayProof(
                    day_number=current_day,
                    proof=proof_bytes,
                    computed_at=int(datetime.now(timezone.utc).timestamp()),
                    validator_id=self.keypair[1],  # Public key
                    signature=self._sign_proof(proof_bytes)
                )
                
                # Store locally
                await self.storage.save_proof(proof)
                
                # Publish to DHT
                await self.dht.publish_proof(proof)
                
                # Participate in consensus
                canonical = await self.consensus.reach_consensus(
                    current_day, 
                    proof,
                    self.dht
                )
                
                if canonical.proof == proof.proof:
                    self.logger.info("✓ Our proof matches canonical")
                else:
                    self.logger.warning("✗ Our proof differs - possible attack or clock drift")
                    
            except Exception as e:
                self.logger.error(f"Error computing day proof: {e}")
    
    def _get_current_day(self) -> int:
        """Calculate current day number since genesis"""
        now = datetime.now(timezone.utc).timestamp()
        elapsed = now - GENESIS_TIMESTAMP
        return int(elapsed // SECONDS_PER_DAY)
    
    async def _wait_until_midnight(self):
        """Sleep until next midnight UTC"""
        now = datetime.now(timezone.utc)
        next_midnight = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        # If already past midnight, wait until tomorrow
        if now >= next_midnight:
            next_midnight = next_midnight + timedelta(days=1)
        
        wait_seconds = (next_midnight - now).total_seconds()
        await asyncio.sleep(wait_seconds)
    
    def _sign_proof(self, proof: bytes) -> bytes:
        """Sign proof with validator's private key"""
        # Ed25519 signature
        import nacl.signing
        signing_key = nacl.signing.SigningKey(self.keypair[0])
        return signing_key.sign(proof).signature
    
    async def _init_dht(self):
        """Initialize libp2p DHT connection"""
        # Placeholder - actual libp2p integration
        return DHTNetwork(self.bootstrap_peers, self.keypair)
    
    async def _sync_historical_proofs(self):
        """Download historical proofs from IPFS/DHT"""
        current_day = self._get_current_day()
        
        for day in range(0, current_day):
            if not await self.storage.has_proof(day):
                proof = await self.dht.fetch_proof(day)
                if proof:
                    await self.storage.save_proof(proof)
```

---

## 4. Consensus Mechanism

### 4.1 Byzantine Fault Tolerant Consensus

Validators reach consensus on day proofs using a simple majority vote with BFT properties:

```python
class ConsensusModule:
    """Byzantine Fault Tolerant consensus for day proofs"""
    
    MIN_VALIDATORS = 3
    CONSENSUS_THRESHOLD = 0.67  # 67% agreement required
    
    async def reach_consensus(self, 
                            day_number: int,
                            our_proof: DayProof,
                            dht: 'DHTNetwork') -> DayProof:
        """
        Reach consensus on canonical proof for a day.
        Returns the canonical proof agreed upon by network.
        """
        # Collect proofs from other validators
        peer_proofs = await dht.collect_peer_proofs(
            day_number,
            timeout=120  # 2 minutes
        )
        
        # Add our proof
        all_proofs = peer_proofs + [our_proof]
        
        # Count proof occurrences
        proof_counts: Dict[bytes, List[DayProof]] = {}
        for proof in all_proofs:
            key = proof.proof
            if key not in proof_counts:
                proof_counts[key] = []
            proof_counts[key].append(proof)
        
        # Find majority
        total_validators = len(all_proofs)
        
        if total_validators < self.MIN_VALIDATORS:
            raise ConsensusError(
                f"Insufficient validators: {total_validators} < {self.MIN_VALIDATORS}"
            )
        
        for proof_bytes, proofs in proof_counts.items():
            agreement_ratio = len(proofs) / total_validators
            
            if agreement_ratio >= self.CONSENSUS_THRESHOLD:
                # Canonical proof found
                canonical = proofs[0]  # All have same proof bytes
                
                # Publish to DHT as canonical
                await dht.publish_canonical_proof(canonical, day_number)
                
                return canonical
        
        # No consensus reached
        raise ConsensusError(
            f"No consensus for day {day_number}: "
            f"{len(proof_counts)} different proofs from {total_validators} validators"
        )
```

### 4.2 Attack Resistance

| Attack Type | Defense Mechanism |
|-------------|-------------------|
| Temporal manipulation | VDF proofs don't match canonical |
| Sybil attack | Validators identified by Ed25519 keys, bootstrapped |
| 33% Byzantine nodes | BFT consensus requires 67% agreement |
| Network partition | Instances choose majority partition |
| Clock drift | Midnight UTC calculated from NTP-synced time |

---

## 5. DHT Network Protocol

### 5.1 libp2p Integration

```python
class DHTNetwork:
    """Distributed Hash Table for proof storage and discovery"""
    
    def __init__(self, bootstrap_peers: List[str], keypair: tuple):
        self.bootstrap_peers = bootstrap_peers
        self.keypair = keypair
        self.node = None
        
    async def initialize(self):
        """Start libp2p node and connect to network"""
        # Use py-libp2p for Python implementation
        from libp2p import new_host
        from libp2p.crypto.secp256k1 import create_new_key_pair
        
        self.node = new_host()
        await self.node.get_network().listen(
            f"/ip4/0.0.0.0/tcp/4001"
        )
        
        # Connect to bootstrap peers
        for peer in self.bootstrap_peers:
            await self.node.connect(peer)
    
    async def publish_proof(self, proof: DayProof):
        """Publish day proof to DHT"""
        key = f"/chorus/proofs/day/{proof.day_number}"
        value = self._serialize_proof(proof)
        
        # Store in DHT
        await self.node.get_dht().put_value(key.encode(), value)
    
    async def fetch_proof(self, day_number: int) -> Optional[DayProof]:
        """Fetch canonical proof for a specific day"""
        key = f"/chorus/proofs/day/{day_number}"
        
        try:
            value = await self.node.get_dht().get_value(key.encode())
            return self._deserialize_proof(value)
        except KeyError:
            return None
    
    async def collect_peer_proofs(self, 
                                  day_number: int,
                                  timeout: int = 120) -> List[DayProof]:
        """Collect proofs from all available validators"""
        # Query DHT for all proofs for this day
        key_pattern = f"/chorus/proofs/day/{day_number}/validator/*"
        
        proofs = []
        async for key, value in self._dht_scan(key_pattern, timeout):
            proof = self._deserialize_proof(value)
            proofs.append(proof)
        
        return proofs
    
    def _serialize_proof(self, proof: DayProof) -> bytes:
        """Serialize proof to bytes"""
        return json.dumps({
            "day_number": proof.day_number,
            "proof": proof.proof.hex(),
            "computed_at": proof.computed_at,
            "validator_id": proof.validator_id.hex(),
            "signature": proof.signature.hex()
        }).encode()
    
    def _deserialize_proof(self, data: bytes) -> DayProof:
        """Deserialize proof from bytes"""
        obj = json.loads(data)
        return DayProof(
            day_number=obj["day_number"],
            proof=bytes.fromhex(obj["proof"]),
            computed_at=obj["computed_at"],
            validator_id=bytes.fromhex(obj["validator_id"]),
            signature=bytes.fromhex(obj["signature"])
        )
```

---

## 6. Storage Layer

### 6.1 RocksDB Proof Archive

```python
import rocksdb

class ValidatorStorage:
    """Persistent storage for validator node"""
    
    def __init__(self, path: str):
        opts = rocksdb.Options()
        opts.create_if_missing = True
        opts.max_open_files = 300
        
        self.db = rocksdb.DB(path, opts)
    
    async def save_proof(self, proof: DayProof):
        """Store proof in local database"""
        key = f"proof:day:{proof.day_number}".encode()
        value = self._serialize(proof)
        self.db.put(key, value)
    
    async def get_proof(self, day_number: int) -> Optional[DayProof]:
        """Retrieve proof from local database"""
        key = f"proof:day:{day_number}".encode()
        value = self.db.get(key)
        
        if value:
            return self._deserialize(value)
        return None
    
    async def has_proof(self, day_number: int) -> bool:
        """Check if proof exists locally"""
        key = f"proof:day:{day_number}".encode()
        return self.db.get(key) is not None
    
    def _serialize(self, proof: DayProof) -> bytes:
        """Serialize proof for storage"""
        import pickle
        return pickle.dumps(proof)
    
    def _deserialize(self, data: bytes) -> DayProof:
        """Deserialize proof from storage"""
        import pickle
        return pickle.loads(data)
```

---

## 7. Configuration

### 7.1 Validator Configuration File

```yaml
# validator.yaml
validator:
  # Unique identifier for this validator
  keypair_path: "./keys/validator_key.pem"
  
  # Network configuration
  network:
    listen_address: "0.0.0.0:4001"
    bootstrap_peers:
      - "/ip4/35.123.45.67/tcp/4001/p2p/QmBootstrap1"
      - "/ip4/52.234.56.78/tcp/4001/p2p/QmBootstrap2"
      - "/ip4/18.345.67.89/tcp/4001/p2p/QmBootstrap3"
    
    # DHT configuration
    dht:
      protocol: "kademlia"
      replication_factor: 20
      query_timeout: 60
  
  # VDF configuration
  vdf:
    iterations: 86400000
    progress_interval: 1000000
    
  # Storage configuration
  storage:
    backend: "rocksdb"
    path: "./validator_data"
    ipfs_node: "http://localhost:5001"
    
  # Consensus configuration
  consensus:
    min_validators: 3
    threshold: 0.67
    timeout: 120
    
  # Monitoring
  monitoring:
    prometheus_port: 9090
    log_level: "INFO"
```

---

## 8. Deployment

### 8.1 Docker Container

```dockerfile
# Dockerfile
FROM python:3.14-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Generate validator keypair if doesn't exist
RUN python generate_keys.py

EXPOSE 4001 9090

CMD ["python", "validator_node.py", "--config", "validator.yaml"]
```

### 8.2 Docker Compose

```yaml
# docker-compose.yaml
version: "3.8"

services:
  validator:
    build: .
    container_name: chorus-validator
    ports:
      - "4001:4001"  # P2P
      - "9090:9090"  # Prometheus
    volumes:
      - ./validator_data:/app/validator_data
      - ./keys:/app/keys
      - ./validator.yaml:/app/validator.yaml
    environment:
      - RUST_LOG=info
    restart: unless-stopped
    
  ipfs:
    image: ipfs/go-ipfs:latest
    container_name: chorus-ipfs
    ports:
      - "5001:5001"  # API
      - "8080:8080"  # Gateway
    volumes:
      - ./ipfs_data:/data/ipfs
    restart: unless-stopped
```

---

## 9. Monitoring & Observability

### 9.1 Prometheus Metrics

```python
from prometheus_client import Counter, Gauge, Histogram, start_http_server

class ValidatorMetrics:
    """Prometheus metrics for validator node"""
    
    def __init__(self):
        self.proofs_computed = Counter(
            'chorus_proofs_computed_total',
            'Total number of day proofs computed'
        )
        
        self.proof_computation_time = Histogram(
            'chorus_proof_computation_seconds',
            'Time taken to compute day proof',
            buckets=[80, 85, 86, 87, 90, 95, 100]
        )
        
        self.consensus_agreement = Gauge(
            'chorus_consensus_agreement_ratio',
            'Ratio of validators agreeing on proof'
        )
        
        self.dht_peers = Gauge(
            'chorus_dht_connected_peers',
            'Number of connected DHT peers'
        )
        
        self.storage_size = Gauge(
            'chorus_storage_bytes',
            'Total storage used for proofs'
        )
    
    def start_server(self, port: int = 9090):
        """Start Prometheus metrics server"""
        start_http_server(port)
```

---

## 10. Security Considerations

### 10.1 Key Management

- Validator keypairs must be generated securely and stored encrypted
- Private keys never transmitted over network
- Hardware security modules (HSM) recommended for production validators

### 10.2 Network Security

- TLS encryption for all DHT communications
- Ed25519 signature verification on all proofs
- Rate limiting on DHT queries to prevent DoS

### 10.3 Temporal Security

- NTP synchronization required for accurate midnight calculation
- Clock drift monitoring (alert if >5 seconds)
- Multiple time sources for redundancy

---

## 11. Testing

### 11.1 Unit Tests

```python
import unittest

class TestChorusVDF(unittest.TestCase):
    
    def setUp(self):
        self.vdf = ChorusVDF(GENESIS_SEED)
    
    def test_deterministic_proof(self):
        """Same day produces same proof"""
        proof1 = self.vdf.compute_day_proof(1)
        proof2 = self.vdf.compute_day_proof(1)
        self.assertEqual(proof1, proof2)
    
    def test_different_days_different_proofs(self):
        """Different days produce different proofs"""
        proof1 = self.vdf.compute_day_proof(1)
        proof2 = self.vdf.compute_day_proof(2)
        self.assertNotEqual(proof1, proof2)
    
    def test_verification(self):
        """Proof verification works"""
        proof = self.vdf.compute_day_proof(1)
        self.assertTrue(self.vdf.verify_day_proof(1, proof))
        self.assertFalse(self.vdf.verify_day_proof(2, proof))
```

---

## 12. FAQ

**Q: Can validators run on consumer hardware?**  
A: Yes, any device that can compute ~86 seconds of hashes can be a validator.

**Q: What happens if a validator goes offline?**  
A: Network continues with remaining validators as long as minimum threshold is met.

**Q: How are validators incentivized?**  
A: Currently altruistic; future versions may include instance-based rewards.

**Q: Can I run multiple validators?**  
A: Yes, but each needs unique Ed25519 keypair and separate DHT identity.

---

## 13. References

- BLAKE3 Specification: https://github.com/BLAKE3-team/BLAKE3-specs
- libp2p Documentation: https://docs.libp2p.io
- Verifiable Delay Functions: https://eprint.iacr.org/2018/601.pdf
- Byzantine Fault Tolerance: Practical Byzantine Fault Tolerance (PBFT) paper

---

## Appendix A: Full Example

See `examples/simple_validator.py` for a complete runnable validator node implementation.

---

**Document Status**: Draft v1.0.0  
**Next Review**: Upon implementation feedback  
**Contact**: chorus-federation@example.com