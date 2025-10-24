# Conductor Production-Readiness Implementation Plan

**Status:** Implementation Guide  
**Owner:** Conductor Development Team  
**Target:** Take current prototype to production-ready state  
**Reference Specs:** CFP-010, CFP-011, Chorus-Stage-Bridge-Integration.md

---

## Executive Summary

The current Conductor implementation provides a solid foundation with working VDF computation, configuration management, and simulated multi-validator testing. However, several critical components require completion before production deployment:

1. Replace simulated DHT with real libp2p networking
2. Complete Byzantine Fault Tolerant consensus implementation
3. Add external API surface for Bridge/Stage integration
4. Implement production-grade error handling and observability
5. Add comprehensive test coverage

---

## Phase 1: Core Consensus Implementation

### 1.1 Complete Threshold Cryptography

**Current State:** Stubbed with placeholder comments in `node.py`

**Requirements:**
- Implement BLS threshold signatures using `py_ecc` or `blspy` library
- Key generation: Each validator generates BLS keypair, shares are distributed via Shamir Secret Sharing
- Signing: Validators sign event batches, producing signature shares
- Aggregation: Collect `threshold` signature shares (2f+1 of 3f+1), aggregate into single valid signature
- Verification: Any party can verify aggregated signature against combined public key

**Deliverables:**

Create new file `conductor/crypto.py`:

```python
class ThresholdCrypto:
    def __init__(self, n: int, t: int):
        # Initialize threshold crypto for n validators with threshold t
        pass

    def generate_shares(self, secret: bytes) -> List[bytes]:
        # Generate n shares of secret using Shamir Secret Sharing
        pass

    def sign_share(self, message: bytes, share_index: int, private_key: bytes) -> bytes:
        # Sign message with validator share, return signature share
        pass

    def aggregate_signatures(self, shares: List[bytes]) -> bytes:
        # Combine t+1 signature shares into aggregated signature
        pass

    def verify_aggregated(self, message: bytes, signature: bytes, public_keys: List[bytes]) -> bool:
        # Verify aggregated signature
        pass
```

**References:**
- BLS signatures: https://github.com/ethereum/py_ecc
- Shamir Secret Sharing: `secretsharing` library or implement from scratch
- CFP-010 Section 3.2: Threshold Cryptography Parameters

### 1.2 Implement Reliable Broadcast (RBC)

**Current State:** Basic propose/echo/ready pattern exists but incomplete

**Requirements:**
- Erasure coding: Use Reed-Solomon to encode event batch into N fragments, any K can reconstruct
- Echo phase: Validators broadcast echo with their fragment, wait for 2f+1 matching echos
- Ready phase: Send ready message after 2f+1 echos OR f+1 ready messages
- Delivery: Reconstruct batch from K fragments after 2f+1 ready messages
- Anti-entropy: Validators request missing fragments from peers

**Implementation Changes:**

Create new file `conductor/consensus.py`:

```python
from reedsolo import RSCodec

class ReliableBroadcast:
    def __init__(self, n: int, f: int):
        self.n = n  # Total validators
        self.f = f  # Max Byzantine nodes
        self.k = n - 2*f  # Reconstruction threshold
        self.rs = RSCodec(2*f)  # Reed-Solomon with 2f redundancy

    async def rbc_propose(self, batch: EventBatch) -> str:
        # 1. Serialize batch
        # 2. Erasure encode into n fragments
        # 3. Send PROPOSE(batch_id, fragment_i, merkle_root) to each validator
        # 4. Transition to ECHO phase
        pass

    async def handle_echo(self, sender: str, batch_id: str, fragment: bytes):
        # 1. Verify merkle proof
        # 2. Store fragment
        # 3. If 2f+1 echos received, send READY
        pass

    async def handle_ready(self, sender: str, batch_id: str):
        # 1. Count ready messages
        # 2. If f+1 readys, send READY if not sent
        # 3. If 2f+1 readys, deliver batch
        pass

    def reconstruct_batch(self, fragments: List[bytes]) -> EventBatch:
        # Reconstruct batch from k-of-n fragments
        pass
```

**Testing:**
- Unit test: Verify reconstruction from k fragments, failure with <k fragments
- Adversarial test: Validators send conflicting fragments, ensure safety
- Network test: Simulate dropped echo messages, verify eventual delivery

### 1.3 Common Coin Implementation

**Current State:** Returns static 0/1, not actually random or Byzantine-resistant

**Requirements:**
- Use threshold signatures to generate shared random beacon
- Each validator signs day_number + round_number with BLS share
- Aggregate threshold signatures, deterministic output mod 2 = coin flip
- Prevents single Byzantine validator from biasing coin

**Implementation:**

Add to `conductor/consensus.py`:

```python
class CommonCoin:
    def __init__(self, threshold_crypto: ThresholdCrypto):
        self.crypto = threshold_crypto

    async def coin_share(self, day: int, round: int) -> bytes:
        # Validator contribution to coin for this round
        message = f"COIN_{day}_{round}".encode()
        return self.crypto.sign_share(message, self.validator_index, self.private_key)

    async def compute_coin(self, day: int, round: int, shares: List[bytes]) -> int:
        # Aggregate shares, extract coin value (0 or 1)
        if len(shares) < self.crypto.threshold:
            raise ValueError("Insufficient shares for coin")
        message = f"COIN_{day}_{round}".encode()
        signature = self.crypto.aggregate_signatures(shares)
        # Extract LSB of aggregated signature as coin value
        return int.from_bytes(signature[:1], 'big') % 2
```

---

## Phase 2: Real Network Transport

### 2.1 Replace Simulated DHT with libp2p

**Current State:** `SimulatedDHTNode` for testing only

**Requirements:**
- Use `py-libp2p` for actual peer-to-peer networking
- Implement Kademlia DHT for validator discovery
- GossipSub for message dissemination (batch proposals, votes)
- Direct streams for large payloads (event batches, day proofs)

**Implementation:**

Create new file `conductor/network.py`:

```python
from libp2p import new_host
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.network.stream.net_stream_interface import INetStream

class Libp2pNetwork:
    def __init__(self, listen_address: str, bootstrap_peers: List[str]):
        self.host = None
        self.pubsub = None

    async def start(self):
        # Initialize libp2p host and pubsub
        self.host = await new_host(listen_addr=self.listen_address)
        self.pubsub = GossipSub(self.host, strict_signing=True)
        await self.pubsub.subscribe("chorus-consensus")

    async def broadcast_message(self, message: bytes):
        # Broadcast to all validators via GossipSub
        await self.pubsub.publish("chorus-consensus", message)

    async def send_direct(self, peer_id: str, message: bytes):
        # Send direct message to specific validator
        stream = await self.host.new_stream(peer_id, ["/chorus/1.0.0"])
        await stream.write(message)

    async def request_fragment(self, peer_id: str, batch_id: str, fragment_index: int) -> bytes:
        # Request missing RBC fragment from peer
        pass
```

**Configuration Changes:**

Update `validator.yaml`:

```yaml
network:
  listen_address: "/ip4/0.0.0.0/tcp/4001"
  bootstrap_peers:
    - "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
  gossipsub:
    heartbeat_interval: 0.7
    history_length: 5
    mesh_size: 6
```

**Testing:**
- Local test: 3 validators on different ports, verify discovery
- WAN test: Validators across geographic regions, measure latency
- Partition test: Split network, verify eventual consistency

### 2.2 Bootstrap and Peer Discovery

**Requirements:**
- Initial bootstrap from config file or DNS seed
- DHT crawl to discover all active validators
- Periodic health checks, remove unresponsive peers
- Implement peer scoring (reputation system for CFP-010)

---

## Phase 3: External API Layer

### 3.1 Add gRPC Service Implementation

**Current State:** Proto definitions exist, no server implementation

**Requirements:**
- Implement `ConductorService` defined in `conductor.proto`
- Serve on separate port from p2p network (e.g., 50051)
- mTLS authentication for Bridge clients
- Rate limiting per client

**Implementation:**

Create new file `conductor/api.py`:

```python
import grpc.aio
import conductor_pb2_grpc

class ConductorServicer(conductor_pb2_grpc.ConductorServiceServicer):
    def __init__(self, node: ValidatorNode):
        self.node = node

    async def GetDayProof(self, request, context):
        # Fetch canonical day proof for given day number
        try:
            proof = await self.node.storage.get_day_proof(request.day_number)
            if proof is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Day proof not found for day {request.day_number}")
                return conductor_pb2.DayProofResponse()

            return conductor_pb2.DayProofResponse(
                day_number=proof.day_number,
                vdf_output=proof.vdf_output,
                validator_signatures=[sig.hex() for sig in proof.signatures],
                timestamp=int(proof.timestamp.timestamp())
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return conductor_pb2.DayProofResponse()

    async def SubmitEventBatch(self, request, context):
        # Bridge submits event batch for consensus
        # Verify Bridge is authorized (check mTLS cert)
        # Validate batch schema
        # Initiate RBC consensus
        # Return batch_id for polling
        pass

    async def GetConsensusStatus(self, request, context):
        # Query status of submitted batch
        # Return: pending, committed, failed
        pass
```

Add to `conductor/main.py`:

```python
async def serve_grpc(node: ValidatorNode, config: Config):
    server = grpc.aio.server()
    conductor_pb2_grpc.add_ConductorServiceServicer_to_server(
        ConductorServicer(node), server
    )

    # Configure mTLS
    with open(config.api.tls_cert, 'rb') as f:
        cert = f.read()
    with open(config.api.tls_key, 'rb') as f:
        key = f.read()
    with open(config.api.tls_ca, 'rb') as f:
        ca = f.read()

    server_credentials = grpc.ssl_server_credentials(
        [(key, cert)],
        root_certificates=ca,
        require_client_auth=True
    )
    server.add_secure_port(f'[::]:{config.api.port}', server_credentials)
    await server.start()
    await server.wait_for_termination()
```

### 3.2 Add REST API for Integration Tests

**Requirements:**
- FastAPI wrapper around core gRPC service
- Endpoints for health checks, metrics, day proofs
- OpenAPI spec generation
- CORS configuration for web clients

**Implementation:**

Create new file `conductor/rest_api.py`:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Conductor API", version="1.0.0")

class DayProofResponse(BaseModel):
    day_number: int
    vdf_output: str
    validator_signatures: List[str]
    timestamp: int

@app.get("/health")
async def health_check():
    # Health check endpoint for load balancers
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/day-proof/{day_number}", response_model=DayProofResponse)
async def get_day_proof(day_number: int):
    # Fetch canonical day proof
    # Query gRPC service internally
    pass

@app.get("/metrics")
async def prometheus_metrics():
    # Prometheus-compatible metrics
    pass
```

---

## Phase 4: Production Error Handling

### 4.1 Replace Broad Exception Handling

**Current Issues:**
- `except Exception` catches everything, masks bugs
- Infinite retry loops without backoff limits
- No alerting when consensus repeatedly fails

**Requirements:**
- Define specific exception types for each failure mode
- Implement exponential backoff with jitter
- Circuit breaker pattern for external dependencies
- Dead letter queue for unprocessable events

**Implementation:**

Create new file `conductor/errors.py`:

```python
class ConductorError(Exception):
    # Base class for Conductor errors
    pass

class ConsensusTimeoutError(ConductorError):
    # Consensus round failed to complete within timeout
    pass

class InsufficientValidatorsError(ConductorError):
    # Not enough validators online for quorum
    pass

class InvalidSignatureError(ConductorError):
    # Signature verification failed
    pass

class NetworkPartitionError(ConductorError):
    # Network partition detected
    pass
```

Create new file `conductor/retry.py`:

```python
import asyncio
from typing import Callable, TypeVar

T = TypeVar('T')

async def exponential_backoff(
    func: Callable,
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0
) -> T:
    # Retry with exponential backoff
    for attempt in range(max_retries):
        try:
            return await func()
        except (NetworkPartitionError, ConsensusTimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = delay * 0.1 * (2 * random.random() - 1)  # +/- 10% jitter
            await asyncio.sleep(delay + jitter)
            logger.warning(f"Retry {attempt+1}/{max_retries} after {delay:.2f}s: {e}")
```

### 4.2 Circuit Breaker for Peer Communication

**Requirements:**
- Track failure rate per peer
- Open circuit after threshold failures
- Half-open state to test recovery
- Close circuit when peer recovers

Create new file `conductor/circuit_breaker.py`:

```python
from enum import Enum
from datetime import datetime, timedelta
from typing import Callable, TypeVar

T = TypeVar('T')

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: timedelta = timedelta(minutes=1)):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    async def call(self, func: Callable) -> T:
        if self.state == CircuitState.OPEN:
            if datetime.now() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is open")

        try:
            result = await func()
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
            raise
```

---

## Phase 5: Observability and Monitoring

### 5.1 Structured Logging with Context

**Current State:** Basic JSON logging exists

**Requirements:**
- Add trace IDs for request correlation
- Include validator ID, day number, consensus round in all logs
- Use `structlog` for consistent structured logging
- Log levels: DEBUG for internal state, INFO for events, WARN for retries, ERROR for failures

**Implementation:**

Create new file `conductor/logging_config.py`:

```python
import structlog
import logging

def configure_logging(log_level: str):
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

Usage in `node.py`:

```python
logger = structlog.get_logger()
logger.bind(validator_id=self.node_id, day=day_number)
logger.info("consensus_round_started", round=round_num, batch_id=batch_id)
```

### 5.2 Prometheus Metrics

**Requirements:**
- Consensus round duration histogram
- Event batch size distribution
- Validator participation rate gauge
- RBC message counts by type
- gRPC request latency and error rate

**Implementation:**

Create new file `conductor/metrics.py`:

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Consensus metrics
consensus_rounds = Counter('conductor_consensus_rounds_total', 'Total consensus rounds', ['status'])
consensus_duration = Histogram('conductor_consensus_duration_seconds', 'Consensus round duration')
event_batch_size = Histogram('conductor_event_batch_size_bytes', 'Event batch size in bytes')

# Network metrics
rbc_messages = Counter('conductor_rbc_messages_total', 'RBC messages by type', ['message_type'])
peer_connections = Gauge('conductor_peer_connections', 'Active peer connections')

# API metrics
grpc_requests = Counter('conductor_grpc_requests_total', 'gRPC requests', ['method', 'status'])
grpc_latency = Histogram('conductor_grpc_latency_seconds', 'gRPC request latency', ['method'])

def record_consensus_round(status: str, duration: float):
    consensus_rounds.labels(status=status).inc()
    consensus_duration.observe(duration)
```

### 5.3 Distributed Tracing

**Requirements:**
- OpenTelemetry integration
- Trace consensus rounds from initiation to completion
- Correlate logs and metrics with trace IDs
- Export traces to Jaeger or Zipkin

Create new file `conductor/tracing.py`:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

def configure_tracing(endpoint: str):
    provider = TracerProvider()
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

# Usage
# with tracer.start_as_current_span("consensus_round") as span:
#     span.set_attribute("day_number", day)
#     span.set_attribute("batch_id", batch_id)
```

---

## Phase 6: Testing and Validation

### 6.1 Unit Tests

**Coverage Targets:**
- VDF computation: 100% (already well tested)
- Threshold crypto: 100%
- RBC logic: 95%
- Common coin: 100%
- Storage layer: 90%

**Framework:** pytest with pytest-asyncio

Create `tests/test_consensus.py`:

```python
import pytest
from conductor.consensus import ReliableBroadcast

@pytest.mark.asyncio
async def test_rbc_delivery_with_honest_validators():
    # All honest validators should deliver same batch
    # Setup: 4 validators, 1 Byzantine (n=4, f=1)
    # Action: Validator 0 proposes batch
    # Assert: All honest validators deliver identical batch
    pass

@pytest.mark.asyncio
async def test_rbc_delivery_with_byzantine_equivocation():
    # Byzantine validator sends conflicting fragments
    # Setup: 4 validators, validator 3 is Byzantine
    # Action: Validator 0 proposes, validator 3 sends conflicting fragments
    # Assert: Honest validators still deliver correctly or timeout safely
    pass
```

### 6.2 Integration Tests

**Scenarios:**
1. Full Consensus Flow: 3 validators, submit batch, verify all validators reach same decision
2. Validator Join: Start with 3 validators, add 4th mid-consensus, verify it syncs
3. Network Partition: Split 5 validators into 3+2, verify 3-group continues, 2-group stalls
4. Byzantine Behavior: 1 of 4 validators sends invalid signatures, verify others ignore it

**Framework:** Docker Compose + pytest

Create `tests/integration/test_full_consensus.py`:

```python
import pytest
from testcontainers.compose import DockerCompose
import grpc
import conductor_pb2, conductor_pb2_grpc
import time

@pytest.fixture(scope="module")
def conductor_cluster():
    with DockerCompose("tests/docker-compose.test.yml") as compose:
        compose.wait_for("http://localhost:8081/health")
        yield compose

@pytest.mark.integration
def test_consensus_with_real_network(conductor_cluster):
    # Submit event batch, verify consensus across validators

    # Connect to validator 1
    channel = grpc.insecure_channel('localhost:50051')
    stub = conductor_pb2_grpc.ConductorServiceStub(channel)

    # Submit batch
    # response = stub.SubmitEventBatch(conductor_pb2.EventBatch(...))
    # batch_id = response.batch_id

    # Poll for completion
    # for _ in range(30):
    #     status = stub.GetConsensusStatus(conductor_pb2.StatusRequest(batch_id=batch_id))
    #     if status.state == "COMMITTED":
    #         break
    #     time.sleep(1)

    # assert status.state == "COMMITTED"
    pass
```

### 6.3 Chaos Testing

**Tools:** Chaos Mesh or custom failure injection

**Scenarios:**
- Random pod restarts during consensus
- Network latency injection (50-500ms)
- Packet loss (5-20%)
- Byzantine behavior (validator sends garbage)

---

## Phase 7: Deployment and Operations

### 7.1 Docker Image

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY conductor/ conductor/
COPY conductor.proto .

# Generate gRPC code
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. conductor.proto

# Create data directory
RUN mkdir -p /data

EXPOSE 4001 50051 9090

CMD ["python", "-m", "conductor.main"]
```

### 7.2 Kubernetes Deployment

Create `k8s/conductor-statefulset.yaml`:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: conductor-validator
spec:
  serviceName: conductor
  replicas: 5
  selector:
    matchLabels:
      app: conductor
  template:
    metadata:
      labels:
        app: conductor
    spec:
      containers:
      - name: conductor
        image: chorus/conductor:latest
        ports:
        - containerPort: 4001
          name: p2p
        - containerPort: 50051
          name: grpc
        - containerPort: 9090
          name: metrics
        env:
        - name: VALIDATOR_KEYPAIR_PATH
          value: /keys/validator_key.pem
        - name: VALIDATOR_NETWORK_LISTEN_ADDRESS
          value: /ip4/0.0.0.0/tcp/4001
        volumeMounts:
        - name: data
          mountPath: /data
        - name: keys
          mountPath: /keys
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 9090
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 9090
          initialDelaySeconds: 10
          periodSeconds: 5
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
```

### 7.3 Monitoring Stack

**Components:**
- Prometheus for metrics scraping
- Grafana for dashboards
- Loki for log aggregation
- Alertmanager for alerts

**Key Alerts:**
- Consensus timeout rate > 5%
- Validator offline > 5 minutes
- VDF computation lag > 2 hours
- Disk usage > 80%

---

## Implementation Checklist

### Phase 1: Core Consensus (Week 1-2)
- [ ] Implement ThresholdCrypto class with BLS signatures
- [ ] Complete ReliableBroadcast with erasure coding
- [ ] Implement proper Common Coin using threshold sigs
- [ ] Unit tests for all consensus components
- [ ] Update node.py to use real crypto (remove stubs)

### Phase 2: Real Network (Week 3)
- [ ] Replace SimulatedDHTNode with Libp2pNetwork
- [ ] Implement GossipSub message dissemination
- [ ] Add peer discovery and bootstrap logic
- [ ] Network integration tests with 3+ validators

### Phase 3: External API (Week 4)
- [ ] Implement ConductorServicer (gRPC)
- [ ] Add mTLS authentication
- [ ] Create FastAPI REST wrapper
- [ ] OpenAPI spec generation
- [ ] API integration tests

### Phase 4: Error Handling (Week 5)
- [ ] Define specific exception types
- [ ] Implement exponential backoff
- [ ] Add circuit breaker per peer
- [ ] Dead letter queue for failed events
- [ ] Error handling unit tests

### Phase 5: Observability (Week 6)
- [ ] Migrate to structlog
- [ ] Add Prometheus metrics
- [ ] Implement OpenTelemetry tracing
- [ ] Create Grafana dashboards
- [ ] Configure alerting rules

### Phase 6: Testing (Week 7)
- [ ] Achieve 90%+ unit test coverage
- [ ] Write integration test suite
- [ ] Docker Compose test environment
- [ ] Chaos testing scenarios
- [ ] Load testing with >1000 events/day

### Phase 7: Deployment (Week 8)
- [ ] Build production Docker image
- [ ] Create Kubernetes manifests
- [ ] Deploy to staging environment
- [ ] Run 7-day soak test
- [ ] Document operational runbooks

---

## Success Criteria

**Before Production Launch:**

### Functional Requirements
- 5-validator network reaches consensus on 100 consecutive day proofs
- Byzantine validator (1 of 5) fails to disrupt consensus
- Network partition resolves without manual intervention
- VDF computation completes within 24 hours consistently

### Performance Requirements
- Consensus latency: p50 < 30s, p99 < 120s
- Event throughput: >10,000 events/day
- Memory footprint: <1GB per validator
- Storage growth: <100MB/day

### Reliability Requirements
- Uptime: >99.9% over 7-day test
- Consensus success rate: >99.5%
- Zero data loss events
- Recovery from any single validator failure <5 minutes

### Security Requirements
- No private key material in logs
- mTLS enforced for all Bridge connections
- Rate limiting prevents DoS
- All cryptographic operations use audited libraries

### Operational Requirements
- All metrics exposed in Prometheus
- Alerting configured with runbooks
- Backup/restore procedures tested
- Rolling update tested without downtime

---

## Critical Gaps for Integration Testing

The biggest blocker for integration with Stage and Bridge:

**No External API Surface:** Bridge needs to call Conductor to fetch day proofs, trigger consensus rounds, query validator status. Currently Conductor is a standalone daemon with no way for other components to interact with it except through the simulated DHT.

**Required Endpoints:**
- `GET /day-proof/{day_number}` - Fetch canonical proof
- `GET /health` - Health check for integration tests
- `POST /events/batch` - Submit event batch for consensus (if Bridge triggers this)
- `GET /consensus/status/{batch_id}` - Poll consensus status

Without these, your integration agent cannot actually test Stage → Bridge → Conductor flows.

---

## References

- **CFP-010:** Conductor BFT specification
- **CFP-011:** VDF and Day Counter protocol  
- **Chorus-Stage-Bridge-Integration.md:** API contracts
- **py-libp2p:** https://github.com/libp2p/py-libp2p
- **py_ecc (BLS):** https://github.com/ethereum/py_ecc
- **Reed-Solomon:** https://github.com/tomerfiliba/reedsolomon

---

## Next Steps

1. Review this document with the development team
2. Prioritize phases based on Bridge integration timeline
3. Set up CI/CD pipeline for automated testing
4. Begin Phase 1 implementation with ThresholdCrypto
