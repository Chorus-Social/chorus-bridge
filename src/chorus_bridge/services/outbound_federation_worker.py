from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Optional
import binascii
import uuid

import httpx
from nacl.signing import SigningKey
from nacl.exceptions import BadSignatureError
from jose import jwt

from chorus_bridge.core.settings import BridgeSettings
from chorus_bridge.db.repository import BridgeRepository
from chorus_bridge.proto import federation_pb2 as pb2

if TYPE_CHECKING:
    from chorus_bridge.db.models import OutboundFederationLedger


logger = logging.getLogger(__name__)


class OutboundFederationWorker:
    """Background worker to push outbound federation messages to other Stage instances."""

    def __init__(
        self,
        settings: BridgeSettings,
        repository: BridgeRepository,
    ):
        self.settings = settings
        self.repository = repository
        self.running = False
        self.client = httpx.AsyncClient()

        if self.settings.bridge_private_key:
            try:
                self.signing_key = SigningKey(
                    binascii.unhexlify(self.settings.bridge_private_key)
                )
            except (binascii.Error, ValueError, BadSignatureError) as exc:
                logger.error(f"Invalid bridge_private_key configured: {exc}")
                raise ValueError("Invalid bridge_private_key configured") from exc
        else:
            logger.warning(
                "bridge_private_key not configured. Outbound federation messages will not be signed."
            )
            self.signing_key = None

        if self.settings.bridge_jwt_signing_key:
            try:
                self.jwt_signing_key = SigningKey(
                    binascii.unhexlify(self.settings.bridge_jwt_signing_key)
                )
            except (binascii.Error, ValueError, BadSignatureError) as exc:
                logger.error(f"Invalid bridge_jwt_signing_key configured: {exc}")
                raise ValueError("Invalid bridge_jwt_signing_key configured") from exc
        else:
            logger.warning(
                "bridge_jwt_signing_key not configured. Outbound federation messages will not be authenticated with JWT."
            )
            self.jwt_signing_key = None

    async def start(self):
        self.running = True
        logger.info("Outbound Federation Worker started.")
        while self.running:
            try:
                await self._process_queued_messages()
            except Exception as e:
                logger.error(f"Error in Outbound Federation Worker: {e}")
            await asyncio.sleep(self.settings.outbound_worker_interval_seconds)

    async def stop(self):
        self.running = False
        await self.client.aclose()
        logger.info("Outbound Federation Worker stopped.")

    async def _process_queued_messages(self):
        queued_messages = self.repository.get_queued_outbound_federation_messages()

        for message_item in queued_messages:
            await self._send_message(message_item)

    def _sign_envelope(
        self, envelope: pb2.FederationEnvelope
    ) -> pb2.FederationEnvelope:
        """Signs a FederationEnvelope with the Bridge's private key."""
        if not self.signing_key:
            logger.warning(
                "Attempted to sign outbound envelope but bridge_private_key is not configured."
            )
            return envelope  # Return unsigned if no key

        # The message_data is already bytes, so we sign over that.
        signed = self.signing_key.sign(envelope.message_data)
        envelope.signature = signed.signature
        return envelope

    async def _send_message(self, message_item: OutboundFederationLedger):
        try:
            # Reconstruct FederationEnvelope from raw_envelope
            envelope = pb2.FederationEnvelope.FromString(message_item.raw_envelope)

            # Sign the envelope with the Bridge's private key
            signed_envelope = self._sign_envelope(envelope)

            headers = {
                "Content-Type": "application/octet-stream",
                "X-Chorus-Instance-Id": self.settings.instance_id,  # Bridge's own instance ID
                "Idempotency-Key": str(
                    uuid.uuid4()
                ),  # Generate a new idempotency key for each outbound message
            }

            # Generate JWT for authentication if signing key is configured
            jwt_token = self._generate_jwt(
                message_item.target_instance_url
            )  # Assuming target_instance_url can be used as audience
            if jwt_token:
                headers["Authorization"] = f"Bearer {jwt_token}"

            # Send the envelope to the target Stage instance
            target_url = (
                f"{message_item.target_instance_url}/api/bridge/federation/send"
            )
            logger.info(
                f"Attempting to send outbound federation message {message_item.id} to {target_url}"
            )

            response = await self.client.post(
                target_url,
                content=signed_envelope.SerializeToString(),
                headers=headers,
            )
            response.raise_for_status()

            self.repository.update_outbound_federation_message_status(
                message_item.id, "delivered"
            )
            logger.info(
                f"Successfully sent outbound federation message {message_item.id} to {target_url}"
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error sending outbound federation message {message_item.id}: {e}"
            )
            self._handle_send_failure(message_item)
        except Exception as e:
            logger.error(
                f"Error sending outbound federation message {message_item.id}: {e}"
            )
            self._handle_send_failure(message_item)

    def _generate_jwt(self, target_instance_id: str) -> Optional[str]:
        """Generates a JWT for outbound authentication to a target Stage instance."""
        if not self.jwt_signing_key:
            return None

        now = int(time.time())
        payload = {
            "iss": self.settings.instance_id,  # Issuer is the Bridge's instance ID
            "aud": target_instance_id,  # Audience is the target Stage's instance ID
            "exp": now + 300,  # Token expires in 5 minutes
            "iat": now,
            "jti": str(uuid.uuid4()),  # Unique JWT ID for replay protection
        }
        # Use the raw private key bytes for signing
        private_key_bytes = self.jwt_signing_key.to_signing_key()._signing_key
        encoded_jwt = jwt.encode(payload, private_key_bytes, algorithm="EdDSA")
        return encoded_jwt
