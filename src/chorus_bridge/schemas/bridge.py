from __future__ import annotations

from typing import Tuple

from pydantic import BaseModel, Field



class DayProof(BaseModel):
    """Schema for a day proof, representing cryptographic proof of elapsed time."""

    day_number: int = Field(ge=0)
    proof: str = Field(min_length=2, description="Hex-encoded proof bytes.")
    canonical: bool = True
    proof_hash: str = Field(min_length=2)


class DayProofResponse(DayProof):
    """Schema for a day proof response, including the data source identifier."""

    source: str = Field(description="Data source identifier.")


class ModerationEventRequest(BaseModel):
    """Schema for a request to record a moderation event, including the event and its signature."""

    moderation_event: str = Field(
        min_length=2, description="Hex-encoded Protobuf ModerationEvent."
    )
    signature: bytes = Field(min_length=2)


class ActivityPubExportRequest(BaseModel):
    """Schema for a request to export Chorus content to ActivityPub, including the post and its signature."""

    chorus_post: str = Field(
        min_length=2, description="Hex-encoded Protobuf PostAnnouncement."
    )
    body_md: str = Field(
        min_length=1, description="The full markdown content of the post."
    )
    signature: bytes = Field(min_length=2)


class ActivityPubNote(BaseModel):
    """Schema for an ActivityPub Note object, representing a federated post."""

    context: str = Field(
        alias="@context", default="https://www.w3.org/ns/activitystreams"
    )
    type: str = "Note"
    attributedTo: str
    content: str
    published: str
    to: Tuple[str, ...] = ("https://www.w3.org/ns/activitystreams#Public",)
