import abc
import asyncio
import dataclasses
import logging
import time
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None

try:
    import grpc
except ImportError:
    grpc = None

try:
    from prometheus_client import Counter, Histogram
except ImportError:
    Counter = Histogram = None

# from libp2p import new_host
# from libp2p.peer.id import ID as PeerID
# from libp2p.host.host import Host
# from libp2p.pubsub.pubsub import Pubsub
# from libp2p.pubsub.gossipsub import GossipSub
# from libp2p.typing import TProtocol

from chorus_bridge.schemas import DayProofResponse
from chorus_bridge.proto import federation_pb2 as pb2
from chorus_bridge.proto import federation_pb2_grpc as pb2_grpc


logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def can_execute(self) -> bool:
        """Check if the circuit breaker allows execution."""
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if (
                self.last_failure_time is not None
                and time.time() - self.last_failure_time > self.recovery_timeout
            ):
                self.state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True

    def on_success(self):
        """Handle successful execution."""
        self.failure_count = 0
        self.state = "CLOSED"

    def on_failure(self):
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


@dataclasses.dataclass
class ConductorEvent:
    """Represents an event to be submitted to the Conductor network."""

    event_type: str
    epoch: int
    payload: bytes
    metadata: dict


@dataclasses.dataclass
class ConductorReceipt:
    """Represents a receipt for a submitted Conductor event."""

    event_hash: str
    epoch: int


class ConductorClient(abc.ABC):
    """Abstract base class for Conductor client implementations.

    Defines the interface for interacting with the Conductor network.
    """

    @abc.abstractmethod
    async def get_day_proof(self, day_number: int) -> Optional[DayProofResponse]:
        """Retrieves a day proof from the Conductor network."""
        pass

    @abc.abstractmethod
    async def submit_event(self, event: ConductorEvent) -> ConductorReceipt:
        """Submits an event to the Conductor network."""
        pass

    @abc.abstractmethod
    async def aclose(self) -> None:
        """Closes the Conductor client and releases resources."""
        pass

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Performs a health check on the Conductor connection."""
        pass

    @abc.abstractmethod
    async def submit_events_batch(
        self, events: list[ConductorEvent]
    ) -> list[ConductorReceipt]:
        """Submits multiple events in a single batch operation for efficiency."""
        pass


class HttpConductorClient(ConductorClient):
    """Enhanced Conductor client implementation using HTTP with connection pooling, retries, and circuit breaker."""

    def __init__(
        self,
        base_url: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 30.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
    ):
        """Initializes the enhanced HttpConductorClient.

        Args:
            base_url: The base URL of the Conductor HTTP API.
            max_retries: Maximum number of retries for failed requests.
            retry_delay: Delay between retries in seconds.
            timeout: Request timeout in seconds.
            circuit_breaker_threshold: Number of failures before opening circuit.
            circuit_breaker_timeout: Time to wait before attempting recovery.
        """
        if httpx is None:
            raise ImportError("httpx is required for HttpConductorClient")
        self.base_url = base_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

        # Initialize circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            recovery_timeout=circuit_breaker_timeout,
        )

        # Create HTTP client with optimized settings
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            http2=True,  # Enable HTTP/2 for better performance
        )

        # Health check
        self._last_health_check = 0
        self._health_check_interval = 30.0  # seconds
        self._is_healthy = True

    async def _execute_with_retry(
        self, operation_name: str, operation_func, *args, **kwargs
    ):
        """Execute HTTP operation with retry logic and circuit breaker."""
        if not self.circuit_breaker.can_execute():
            logger.warning("Circuit breaker is OPEN for %s", operation_name)
            raise Exception("Circuit breaker is open")

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await operation_func(*args, **kwargs)
                self.circuit_breaker.on_success()
                return result

            except Exception as e:
                last_exception = e
                logger.warning(
                    "Attempt %s failed for %s: %s", attempt + 1, operation_name, e
                )

                if attempt < self.max_retries:
                    await asyncio.sleep(
                        self.retry_delay * (2**attempt)
                    )  # Exponential backoff
                else:
                    self.circuit_breaker.on_failure()
                    raise

        raise last_exception

    async def get_day_proof(self, day_number: int) -> Optional[DayProofResponse]:
        """Retrieves a day proof via HTTP GET request with retry logic."""

        async def _get_day_proof_impl():
            response = await self.client.get(f"/day-proof/{day_number}")
            response.raise_for_status()
            data = response.json()
            return DayProofResponse(**data)

        try:
            return await self._execute_with_retry("GetDayProof", _get_day_proof_impl)
        except Exception as e:
            logger.error(
                "Failed to get day proof for day %s after retries: %s", day_number, e
            )
            return None

    async def submit_event(self, event: ConductorEvent) -> ConductorReceipt:
        """Submits an event via HTTP POST request with retry logic."""

        async def _submit_event_impl():
            response = await self.client.post("/events", json=dataclasses.asdict(event))
            response.raise_for_status()
            data = response.json()
            return ConductorReceipt(**data)

        try:
            return await self._execute_with_retry("SubmitEvent", _submit_event_impl)
        except Exception as e:
            logger.error(
                "Failed to submit event %s after retries: %s", event.event_type, e
            )
            raise

    async def health_check(self) -> bool:
        """Perform health check on the Conductor connection."""
        current_time = time.time()
        if current_time - self._last_health_check < self._health_check_interval:
            return self._is_healthy

        try:
            response = await self.client.get("/health")
            self._is_healthy = response.status_code == 200
            self._last_health_check = current_time
            return self._is_healthy
        except Exception as e:
            logger.warning("Health check failed: %s", e)
            self._is_healthy = False
            self._last_health_check = current_time
            return False

    async def submit_events_batch(
        self, events: list[ConductorEvent]
    ) -> list[ConductorReceipt]:
        """Submits multiple events in a single batch operation for efficiency."""

        async def _submit_batch_impl():
            response = await self.client.post(
                "/events/batch", json=[dataclasses.asdict(event) for event in events]
            )
            response.raise_for_status()
            data = response.json()
            return [ConductorReceipt(**receipt) for receipt in data]

        try:
            return await self._execute_with_retry(
                "SubmitEventsBatch", _submit_batch_impl
            )
        except Exception as e:
            logger.error(
                "Failed to submit batch of %s events after retries: %s", len(events), e
            )
            raise

    async def aclose(self) -> None:
        """Closes the underlying HTTP client."""
        await self.client.aclose()


class GrpcConductorClient(ConductorClient):
    """Enhanced Conductor client implementation using gRPC with connection pooling, retries, and circuit breaker."""

    def __init__(
        self,
        target: str,
        requests_total_metric: Counter,
        latency_metric: Histogram,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        connection_timeout: float = 30.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
    ):
        """Initializes the enhanced GrpcConductorClient.

        Args:
            target: The address of the Conductor gRPC server (e.g., 'localhost:50051').
            requests_total_metric: Prometheus counter for request metrics.
            latency_metric: Prometheus histogram for latency metrics.
            max_retries: Maximum number of retries for failed requests.
            retry_delay: Delay between retries in seconds.
            connection_timeout: Connection timeout in seconds.
            circuit_breaker_threshold: Number of failures before opening circuit.
            circuit_breaker_timeout: Time to wait before attempting recovery.
        """
        if grpc is None:
            raise ImportError("grpc is required for GrpcConductorClient")
        self.target = target
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connection_timeout = connection_timeout

        # Initialize circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            recovery_timeout=circuit_breaker_timeout,
        )

        # Initialize metrics
        self.requests_total_metric = requests_total_metric
        self.latency_metric = latency_metric

        # Connection management
        self._channel = None
        self._stub = None
        self._connection_lock = asyncio.Lock()

        # Health check
        self._last_health_check = 0
        self._health_check_interval = 30.0  # seconds
        self._is_healthy = True

    async def _ensure_connection(self):
        """Ensure gRPC connection is established with proper error handling."""
        async with self._connection_lock:
            if (
                self._channel is None
                or self._channel.get_state() == grpc.ChannelConnectivity.SHUTDOWN
            ):
                try:
                    # Create channel with options for better performance
                    options = [
                        ("grpc.keepalive_time_ms", 10000),
                        ("grpc.keepalive_timeout_ms", 5000),
                        ("grpc.keepalive_permit_without_calls", True),
                        ("grpc.http2.max_pings_without_data", 0),
                        ("grpc.http2.min_time_between_pings_ms", 10000),
                        ("grpc.http2.min_ping_interval_without_data_ms", 300000),
                        ("grpc.max_connection_idle_ms", 30000),
                        ("grpc.max_connection_age_ms", 300000),
                        ("grpc.max_connection_age_grace_ms", 5000),
                    ]

                    self._channel = grpc.aio.insecure_channel(
                        self.target, options=options
                    )
                    self._stub = pb2_grpc.ConductorBridgeStub(self._channel)

                    # Wait for channel to be ready
                    await grpc.aio.channel_ready(
                        self._channel, timeout=self.connection_timeout
                    )
                    self._is_healthy = True
                    logger.info("gRPC connection established to %s", self.target)

                except Exception as e:
                    logger.error(
                        "Failed to establish gRPC connection to %s: %s", self.target, e
                    )
                    self._is_healthy = False
                    raise

    async def _execute_with_retry(
        self, operation_name: str, operation_func, *args, **kwargs
    ):
        """Execute operation with retry logic and circuit breaker."""
        if not self.circuit_breaker.can_execute():
            logger.warning("Circuit breaker is OPEN for %s", operation_name)
            self.requests_total_metric.labels(
                method=operation_name, status="circuit_breaker_open"
            ).inc()
            raise Exception("Circuit breaker is open")

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                await self._ensure_connection()
                result = await operation_func(*args, **kwargs)
                self.circuit_breaker.on_success()
                return result

            except Exception as e:
                last_exception = e
                logger.warning(
                    "Attempt %s failed for %s: %s", attempt + 1, operation_name, e
                )

                if attempt < self.max_retries:
                    await asyncio.sleep(
                        self.retry_delay * (2**attempt)
                    )  # Exponential backoff
                else:
                    self.circuit_breaker.on_failure()
                    self.requests_total_metric.labels(
                        method=operation_name, status="error"
                    ).inc()
                    raise

        raise last_exception

    async def get_day_proof(self, day_number: int) -> Optional[DayProofResponse]:
        """Retrieves a day proof via gRPC request with retry logic and circuit breaker."""
        start_time = time.time()

        async def _get_day_proof_impl():
            request = pb2.DayProofRequest(day_number=day_number)
            response = await self._stub.GetDayProof(request)
            return DayProofResponse(
                day_number=response.day_number,
                proof=response.proof,
                proof_hash=response.proof_hash,
                canonical=response.canonical,
                source=response.source,
            )

        try:
            result = await self._execute_with_retry("GetDayProof", _get_day_proof_impl)
            self.requests_total_metric.labels(
                method="GetDayProof", status="success"
            ).inc()
            return result
        except Exception as e:
            logger.error(
                "Failed to get day proof for day %s after retries: %s", day_number, e
            )
            self.requests_total_metric.labels(
                method="GetDayProof", status="error"
            ).inc()
            return None
        finally:
            self.latency_metric.labels(method="GetDayProof").observe(
                time.time() - start_time
            )

    async def submit_event(self, event: ConductorEvent) -> ConductorReceipt:
        """Submits an event via gRPC request with retry logic and circuit breaker."""
        start_time = time.time()

        async def _submit_event_impl():
            request = pb2.ConductorEvent(
                event_type=event.event_type,
                epoch=event.epoch,
                payload=event.payload,
                metadata=event.metadata,
            )
            response = await self._stub.SubmitEvent(request)
            return ConductorReceipt(
                event_hash=response.event_hash,
                epoch=response.epoch,
            )

        try:
            result = await self._execute_with_retry("SubmitEvent", _submit_event_impl)
            self.requests_total_metric.labels(
                method="SubmitEvent", status="success"
            ).inc()
            return result
        except Exception as e:
            logger.error(
                "Failed to submit event %s after retries: %s", event.event_type, e
            )
            self.requests_total_metric.labels(
                method="SubmitEvent", status="error"
            ).inc()
            raise
        finally:
            self.latency_metric.labels(method="SubmitEvent").observe(
                time.time() - start_time
            )

    async def health_check(self) -> bool:
        """Perform health check on the Conductor connection."""
        current_time = time.time()
        if current_time - self._last_health_check < self._health_check_interval:
            return self._is_healthy

        try:
            await self._ensure_connection()
            # Try a simple operation to verify connection
            request = pb2.DayProofRequest(day_number=0)  # Use day 0 as health check
            await self._stub.GetDayProof(request)
            self._is_healthy = True
            self._last_health_check = current_time
            return True
        except Exception as e:
            logger.warning("Health check failed: %s", e)
            self._is_healthy = False
            self._last_health_check = current_time
            return False

    async def submit_events_batch(
        self, events: list[ConductorEvent]
    ) -> list[ConductorReceipt]:
        """Submits multiple events in a single batch operation for efficiency."""
        start_time = time.time()

        async def _submit_batch_impl():
            # Convert events to protobuf format
            conductor_events = [
                pb2.ConductorEvent(
                    event_type=event.event_type,
                    epoch=event.epoch,
                    payload=event.payload,
                    metadata=event.metadata,
                )
                for event in events
            ]

            # Create batch request
            batch_request = pb2.ConductorEventBatch(events=conductor_events)
            response = await self._stub.SubmitEventsBatch(batch_request)

            # Convert response to receipts
            return [
                ConductorReceipt(
                    event_hash=receipt.event_hash,
                    epoch=receipt.epoch,
                )
                for receipt in response.receipts
            ]

        try:
            result = await self._execute_with_retry(
                "SubmitEventsBatch", _submit_batch_impl
            )
            self.requests_total_metric.labels(
                method="SubmitEventsBatch", status="success"
            ).inc()
            return result
        except Exception as e:
            logger.error(
                "Failed to submit batch of %s events after retries: %s", len(events), e
            )
            self.requests_total_metric.labels(
                method="SubmitEventsBatch", status="error"
            ).inc()
            raise
        finally:
            self.latency_metric.labels(method="SubmitEventsBatch").observe(
                time.time() - start_time
            )

    async def aclose(self) -> None:
        """Closes the gRPC channel and cleans up resources."""
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stub = None
            self._is_healthy = False
            logger.info("gRPC connection closed")


# class Libp2pConductorClient(ConductorClient):
#     """Conductor client implementation using libp2p for communication.

#     This client initializes a libp2p host, connects to bootstrap peers, and uses
#     pubsub for requesting day proofs and submitting events.
#     """

#     def __init__(self, base_url: str):
#         """Initializes the Libp2pConductorClient.

#         Args:
#             base_url: A comma-separated string of libp2p multiaddresses for bootstrap peers.
#         """
#         # base_url will be treated as a comma-separated list of bootstrap peers
#         self.bootstrap_peers = [peer.strip() for peer in base_url.split(',') if peer.strip()]
#         self.logger = logging.getLogger(__name__)
#         self.host: Optional[Host] = None
#         self.pubsub: Optional[Pubsub] = None
#         self.topic_day_proof = TProtocol("/chorus/conductor/day_proof")
#         self.topic_events = TProtocol("/chorus/conductor/events")
#         self.listen_address = "/ip4/0.0.0.0/tcp/0" # Configurable listen address
#         self.peer_id: Optional[PeerID] = None # Configurable Peer ID
#         self.response_queue: asyncio.Queue = asyncio.Queue() # Queue for responses
#         self.listener_task: Optional[asyncio.Task] = None # Task for listening to pubsub

#     async def _initialize_libp2p_host(self):
#         """Initializes the libp2p host and connects to bootstrap peers."""
#         from libp2p.crypto.secp25519 import create_new_key_pair

#         # Generate a new key pair for the host
#         key_pair = create_new_key_pair()
#         self.host = new_host(key_pair=key_pair)

#         # Listen on a configurable address
#         await self.host.get_network().listen(self.listen_address)
#         self.peer_id = self.host.get_id()
#         self.logger.info("Libp2p host started with Peer ID: %s and address: %s", self.peer_id.to_string(), self.host.get_network().get_peer_info().addrs[0])

#         # Connect to bootstrap peers
#         for peer_addr in self.bootstrap_peers:
#             try:
#                 await self.host.get_network().connect(peer_addr)
#                 self.logger.info("Connected to libp2p bootstrap peer: %s", peer_addr)
#             except Exception as e:
#                 self.logger.warning("Failed to connect to libp2p bootstrap peer %s: %s", peer_addr, e)

#         # Initialize pubsub (Gossipsub)
#         self.pubsub = GossipSub(self.host)
#         self.pubsub.subscribe(self.topic_day_proof)
#         self.pubsub.subscribe(self.topic_events)
#         self.logger.info("Libp2p pubsub initialized and subscribed to topics.")

#         # Start listener task
#         self.listener_task = asyncio.create_task(self._pubsub_listener())

#     async def _pubsub_listener(self):
#         """Listens for incoming pubsub messages and puts them into the response queue."""
#         if not self.pubsub:
#             self.logger.error("Pubsub not initialized for listener.")
#             return

#         self.logger.info("Libp2p pubsub listener started.")
#         while True:
#             try:
#                 # Listen for messages on subscribed topics
#                 # This is a simplified approach. In a real scenario, you'd have specific handlers
#                 # for different message types and topics.
#                 message = await self.pubsub.read_message()
#                 if message:
#                     self.logger.debug("Received pubsub message on topic %s: %s", message.topic, message.data.decode())
#                     # Put message into response queue if it's a response to a request
#                     # For now, just put all messages for demonstration
#                     await self.response_queue.put(message)
#             except Exception as e:
#                 self.logger.error("Error in pubsub listener: %s", e)
#             await asyncio.sleep(0.1) # Prevent busy-waiting

#     async def get_day_proof(self, day_number: int) -> Optional[DayProofResponse]:
#         """Requests a day proof from the Conductor network via libp2p pubsub."""
#         if not self.host:
#             await self._initialize_libp2p_host() # Initialize if not already

#         self.logger.info("Libp2pConductorClient: Requesting day proof for day %s via libp2p.", day_number)
#         request_id = str(uuid.uuid4())
#         request_payload = json.dumps({
#             "type": "request_day_proof",
#             "day_number": day_number,
#             "request_id": request_id,
#             "sender_id": self.peer_id.to_string() if self.peer_id else "unknown"
#         }).encode('utf-8')

#         if self.pubsub:
#             await self.pubsub.publish(self.topic_day_proof, request_payload)
#             self.logger.debug("Published request for day proof %s with request_id %s", day_number, request_id)

#             # Wait for a response
#             try:
#                 while True:
#                     message = await asyncio.wait_for(self.response_queue.get(), timeout=5) # 5 second timeout
#                     try:
#                         response_data = json.loads(message.data.decode('utf-8'))
#                         if response_data.get("type") == "day_proof_response" and response_data.get("request_id") == request_id:
#                             self.logger.info("Received day proof response for day %s.", day_number)
#                             return DayProofResponse(**response_data["proof"])
#                     except json.JSONDecodeError:
#                         self.logger.warning("Received non-JSON pubsub message.")
#                     except Exception as e:
#                         self.logger.error("Error processing pubsub response: %s", e)
#             except asyncio.TimeoutError:
#                 self.logger.warning("Timeout waiting for day proof response for day %s.", day_number)
#         return None

#     async def submit_event(self, event: ConductorEvent) -> ConductorReceipt:
#         """Submits an event to the Conductor network via libp2p pubsub."""
#         if not self.host:
#             await self._initialize_libp2p_host() # Initialize if not already

#         self.logger.info("Libp2pConductorClient: Submitting event %s via libp2p.", event.event_type)
#         event_payload = json.dumps(dataclasses.asdict(event)).encode('utf-8')
#         if self.pubsub:
#             await self.pubsub.publish(self.topic_events, event_payload)
#             self.logger.debug("Published event %s to libp2p topic.", event.event_type)

#         # In a real scenario, Conductor would return a receipt.
#         # For this placeholder, we'll return a dummy receipt.
#         return ConductorReceipt(event_hash=f"libp2p_event_hash_{event.epoch}", epoch=event.epoch)

#     async def aclose(self) -> None:
#         """Closes the libp2p host and cancels the listener task."""
#         if self.listener_task:
#             self.listener_task.cancel()
#             try:
#                 await self.listener_task
#             except asyncio.CancelledError:
#                 pass
#         if self.host:
#             await self.host.close()
#             self.logger.info("Libp2p host closed.")


class InMemoryConductorClient(ConductorClient):
    """In-memory Conductor client for testing and development."""

    async def get_day_proof(self, day_number: int) -> Optional[DayProofResponse]:
        return DayProofResponse(
            day_number=day_number,
            proof="mock_proof",
            proof_hash="mock_hash",
            canonical=True,
            source="in_memory",
        )

    async def submit_event(self, event: ConductorEvent) -> ConductorReceipt:
        return ConductorReceipt(event_hash="mock_event_hash", epoch=event.epoch)

    async def health_check(self) -> bool:
        return True

    async def submit_events_batch(
        self, events: list[ConductorEvent]
    ) -> list[ConductorReceipt]:
        return [
            ConductorReceipt(event_hash=f"mock_batch_hash_{i}", epoch=event.epoch)
            for i, event in enumerate(events)
        ]

    async def aclose(self) -> None:
        pass
