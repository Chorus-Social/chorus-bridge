from __future__ import annotations

import asyncio
import logging
from typing import Optional

from libp2p import new_host
from libp2p.host.host import Host
from libp2p.pubsub.pubsub import Pubsub
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.typing import TProtocol
from libp2p.peer.id import ID as PeerID

from chorus_bridge.core.settings import BridgeSettings
from chorus_bridge.proto import federation_pb2 as pb2
from prometheus_client import Counter

logger = logging.getLogger(__name__)


class Libp2pBridgeClient:
    """Manages libp2p host and gossipsub for Bridge-to-Bridge communication."""

    def __init__(
        self,
        settings: BridgeSettings,
        message_queue: asyncio.Queue,
        published_metric: Counter,
        received_metric: Counter,
    ):
        self.settings = settings
        self.message_queue = message_queue
        self.published_metric = published_metric
        self.received_metric = received_metric
        self.host: Optional[Host] = None
        self.pubsub: Optional[Pubsub] = None
        self.peer_id: Optional[PeerID] = None
        self.listener_task: Optional[asyncio.Task] = None

        # Topics for gossipsub, dynamically generated based on day
        self.event_topic_prefix = "/chorus/events/"
        self.proof_topic = TProtocol("/chorus/proofs")
        self.blacklist_topic = TProtocol("/chorus/blacklist")

        # Bootstrap peers from settings (assuming a list of multiaddresses)
        self.bootstrap_peers = [
            peer.strip() for peer in settings.libp2p_bootstrap_peers if peer.strip()
        ]

    async def start(self):
        """Initializes the libp2p host, connects to bootstrap peers, and starts pubsub."""
        if self.host:
            logger.warning("Libp2p host already started.")
            return

        # Generate a new key pair for the host (or load from persistent storage)
        # For now, generating a new one each time. In production, this should be stable.
        from libp2p.crypto.secp25519 import create_new_key_pair

        key_pair = create_new_key_pair()
        self.host = new_host(key_pair=key_pair)

        # Listen on a configurable address
        listen_addr = self.settings.libp2p_listen_address or "/ip4/0.0.0.0/tcp/0"
        await self.host.get_network().listen(listen_addr)
        self.peer_id = self.host.get_id()
        logger.info(
            f"Libp2p host started with Peer ID: {self.peer_id.to_string()} and address: {self.host.get_network().get_peer_info().addrs[0]}"
        )

        # Connect to bootstrap peers
        for peer_addr in self.bootstrap_peers:
            try:
                await self.host.get_network().connect(peer_addr)
                logger.info(f"Connected to libp2p bootstrap peer: {peer_addr}")
            except Exception as e:
                logger.warning(
                    f"Failed to connect to libp2p bootstrap peer {peer_addr}: {e}"
                )

        # Initialize pubsub (Gossipsub)
        self.pubsub = GossipSub(self.host)
        self.pubsub.subscribe(self.proof_topic)
        self.pubsub.subscribe(self.blacklist_topic)
        logger.info("Libp2p pubsub initialized and subscribed to static topics.")

        # Start listener task
        self.listener_task = asyncio.create_task(self._pubsub_listener())

    async def stop(self):
        """Closes the libp2p host and cancels the listener task."""
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass
        if self.host:
            await self.host.close()
            logger.info("Libp2p host closed.")

    async def _pubsub_listener(self):
        """Listens for incoming pubsub messages and puts them into the message queue."""
        if not self.pubsub:
            logger.error("Pubsub not initialized for listener.")
            return

        logger.info("Libp2p pubsub listener started.")
        while True:
            try:
                message = await self.pubsub.read_message()
                if message:
                    self.received_metric.labels(topic=str(message.topic)).inc()
                    logger.debug(
                        f"Received pubsub message on topic {message.topic}: {message.data.decode()}"
                    )
                    await self.message_queue.put(message)
            except Exception as e:
                logger.error(f"Error in pubsub listener: {e}")
            await asyncio.sleep(0.1)  # Prevent busy-waiting

    async def publish_federation_envelope(
        self, envelope: pb2.FederationEnvelope, day_number: int
    ):
        """Publishes a signed FederationEnvelope to the appropriate gossipsub topic."""
        if not self.pubsub:
            logger.warning("Libp2p pubsub not initialized. Cannot publish envelope.")
            return

        topic = TProtocol(f"{self.event_topic_prefix}{day_number}")
        # Ensure we are subscribed to the topic before publishing
        if topic not in self.pubsub.get_topics():
            self.pubsub.subscribe(topic)
            logger.info(f"Subscribed to new event topic: {topic}")

        try:
            await self.pubsub.publish(topic, envelope.SerializeToString())
            self.published_metric.labels(topic=str(topic)).inc()
            logger.debug(f"Published FederationEnvelope to topic {topic}")
        except Exception as e:
            logger.error(f"Error publishing FederationEnvelope to libp2p: {e}")

    async def publish_day_proof(self, day_proof: pb2.DayProof):
        """Publishes a DayProof message to the proofs topic."""
        if not self.pubsub:
            logger.warning("Libp2p pubsub not initialized. Cannot publish day proof.")
            return
        try:
            await self.pubsub.publish(self.proof_topic, day_proof.SerializeToString())
            self.published_metric.labels(topic=str(self.proof_topic)).inc()
            logger.debug(f"Published DayProof for day {day_proof.day_number}")
        except Exception as e:
            logger.error(f"Error publishing DayProof to libp2p: {e}")

    async def publish_blacklist_update(self, blacklist_update: pb2.BlacklistUpdate):
        """Publishes a BlacklistUpdate message to the blacklist topic."""
        if not self.pubsub:
            logger.warning(
                "Libp2p pubsub not initialized. Cannot publish blacklist update."
            )
            return
        try:
            await self.pubsub.publish(
                self.blacklist_topic, blacklist_update.SerializeToString()
            )
            self.published_metric.labels(topic=str(self.blacklist_topic)).inc()
            logger.debug("Published BlacklistUpdate.")
        except Exception as e:
            logger.error(f"Error publishing BlacklistUpdate to libp2p: {e}")
