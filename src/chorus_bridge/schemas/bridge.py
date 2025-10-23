from __future__ import annotations

from typing import Optional, Tuple

from pydantic import BaseModel, Field

from chorus_bridge.proto.federation_messages import ModerationEvent, PostAnnouncement


class DayProof(BaseModel):
    day_number: int = Field(ge=0)
    proof: str = Field(min_length=2, description="Hex-encoded proof bytes.")
    canonical: bool = True
    proof_hash: str = Field(min_length=2)


class DayProofResponse(DayProof):
    source: str = Field(description="Data source identifier.")


class ModerationEventRequest(BaseModel):
    moderation_event: ModerationEvent
    signature: bytes = Field(min_length=2)


class ActivityPubExportRequest(BaseModel):
    chorus_post: PostAnnouncement
    signature: bytes = Field(min_length=2)


class ActivityPubNote(BaseModel):
    context: str = Field(alias="@context", default="https://www.w3.org/ns/activitystreams")
    type: str = "Note"
    attributedTo: str
    content: str
    published: str
    to: Tuple[str, ...] = ("https://www.w3.org/ns/activitystreams#Public",)
