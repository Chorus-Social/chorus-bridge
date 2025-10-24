from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import httpx

from chorus_bridge.core.settings import BridgeSettings
from chorus_bridge.db.repository import BridgeRepository
from chorus_bridge.schemas import ActivityPubExportRequest
from chorus_bridge.proto import federation_pb2 as pb2
from chorus_bridge.services.activitypub import ActivityPubTranslator

if TYPE_CHECKING:
    from chorus_bridge.db.models import ExportLedger


logger = logging.getLogger(__name__)


class ActivityPubDeliveryWorker:
    """Background worker to deliver ActivityPub exports to federated instances."""

    def __init__(
        self,
        settings: BridgeSettings,
        repository: BridgeRepository,
        translator: ActivityPubTranslator,
    ):
        """Initializes the ActivityPubDeliveryWorker.

        Args:
            settings: The BridgeSettings instance.
            repository: The BridgeRepository instance for database operations.
            translator: The ActivityPubTranslator instance for converting Chorus posts.
        """
        self.settings = settings
        self.repository = repository
        self.translator = translator
        self.running = False
        self.client = httpx.AsyncClient()

    async def start(self):
        """Starts the worker's main loop to process queued exports."""
        self.running = True
        logger.info("ActivityPub Delivery Worker started.")
        while self.running:
            try:
                await self._process_queued_exports()
            except Exception as e:
                logger.error(f"Error in ActivityPub Delivery Worker: {e}")
            await asyncio.sleep(self.settings.activitypub_worker_interval_seconds)

    async def stop(self):
        """Stops the worker and closes the HTTP client."""
        self.running = False
        await self.client.aclose()
        logger.info("ActivityPub Delivery Worker stopped.")

    async def _process_queued_exports(self):
        """Fetches and processes queued ActivityPub exports from the repository."""
        # Fetch queued exports from the repository
        # This method needs to be added to BridgeRepository
        queued_exports = self.repository.get_queued_exports()  # Placeholder

        for export_item in queued_exports:
            await self._deliver_export(export_item)

    async def _deliver_export(self, export_item: ExportLedger):
        """Attempts to deliver a single ActivityPub export item.

        Args:
            export_item: The ExportLedger item to deliver.

        Raises:
            httpx.HTTPStatusError: If the HTTP request to the ActivityPub instance fails.
            Exception: For other unexpected errors during delivery.
        """
        try:
            # Reconstruct the original ActivityPubExportRequest from raw_payload
            request = ActivityPubExportRequest.model_validate_json(
                export_item.raw_payload
            )
            chorus_post = pb2.PostAnnouncement.FromString(request.chorus_post)
            body_md = request.body_md

            # Build ActivityPub Note
            note, published_ts = self.translator.build_note(chorus_post, body_md)
            note_json = note.model_dump_json(by_alias=True)

            # Sign and send HTTP request
            # This part needs proper HTTP Signature implementation
            # For now, a placeholder for sending
            logger.info(
                f"Attempting to deliver ActivityPub export for job_id: {export_item.id}"
            )
            response = await self.client.post(
                export_item.target_url,
                content=note_json,
                headers={
                    "Content-Type": "application/activity+json",
                    "Accept": "application/activity+json",
                },
            )
            response.raise_for_status()

            # Update status in repository
            self.repository.update_export_status(export_item.id, "delivered")
            logger.info(
                f"Successfully delivered ActivityPub export for job_id: {export_item.id}"
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error delivering ActivityPub export {export_item.id}: {e}"
            )
            self._handle_delivery_failure(export_item)
        except Exception as e:
            logger.error(f"Error delivering ActivityPub export {export_item.id}: {e}")
            self._handle_delivery_failure(export_item)

    def _handle_delivery_failure(self, export_item: ExportLedger):
        """Handles a failed delivery attempt, implementing retry logic with exponential backoff."""
        # Implement retry logic with exponential backoff
        new_attempts = export_item.attempts + 1
        if new_attempts <= self.settings.activitypub_max_retries:
            retry_at = int(time.time()) + (
                2**new_attempts * self.settings.activitypub_retry_delay_seconds
            )
            self.repository.update_export_for_retry(
                export_item.id, new_attempts, retry_at
            )
            logger.warning(
                f"Retrying ActivityPub export {export_item.id} in {retry_at - int(time.time())} seconds. Attempt {new_attempts}"
            )
        else:
            self.repository.update_export_status(export_item.id, "failed")
            logger.error(
                f"ActivityPub export {export_item.id} failed after {new_attempts} attempts."
            )


# This needs to be added to BridgeSettings
# activitypub_worker_interval_seconds: int = Field(default=60, ge=1)
# activitypub_max_retries: int = Field(default=5, ge=0)
# activitypub_retry_delay_seconds: int = Field(default=60, ge=1)
