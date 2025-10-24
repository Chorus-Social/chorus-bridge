from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Tuple

from chorus_bridge.proto import federation_pb2 as pb2
from chorus_bridge.schemas import ActivityPubNote


@dataclass
class ActivityPubTranslator:
    """Translate Chorus posts into ActivityStreams objects."""

    genesis_timestamp: int
    actor_domain: str

    def _actor_uri(self, pubkey_hash: bytes) -> str:
        digest = hashlib.sha256(pubkey_hash).hexdigest()[:16]
        return f"https://{self.actor_domain}/actors/{digest}"

    def derive_publish_timestamp(self, day_number: int, post_id: bytes) -> int:
        """
        Derive a stable-but-fuzzy timestamp for ActivityPub exports.

        The RNG seed ensures determinism while keeping the timestamp within
        a single day window to protect privacy.
        """
        rng = random.Random()
        rng.seed(f"{post_id.decode('utf-8')}:{day_number}")
        offset = rng.randint(0, 86_400)
        return self.genesis_timestamp + (day_number * 86_400) + offset

    def build_note(
        self, post: pb2.PostAnnouncement, body_md: str
    ) -> Tuple[ActivityPubNote, int]:
        actor_uri = self._actor_uri(post.author_pubkey)
        published_ts = self.derive_publish_timestamp(post.creation_day, post.post_id)
        note = ActivityPubNote(
            attributedTo=actor_uri,
            content=body_md,
            published=self._format_timestamp(published_ts),
        )
        return note, published_ts

    @staticmethod
    def _format_timestamp(timestamp: int) -> str:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
