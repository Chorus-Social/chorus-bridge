from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol

import httpx

from chorus_bridge.schemas import DayProof

# Mock Conductor and its event models for InMemoryConductorClient
class MockConductorEvent:
    pass

class MockConductor:
    async def propose_batch(self, events: List[MockConductorEvent]):
        pass

    async def handle_day_proof(self, day_proof_event: MockConductorEvent):
        pass

class MockConductorModels:
    class Event(MockConductorEvent):
        pass
    class PostAnnounce(Event):
        pass
    class ModerationEvent(Event):
        pass
    class UserRegistration(Event):
        pass
    class DayProof(Event):
        pass
    class MembershipChange(Event):
        pass
    class APExportNotice(Event):
        pass

conductor_models = MockConductorModels()
Conductor = MockConductor


@dataclass
class ConductorEvent:
    event_type: str
    epoch: int
    payload: bytes
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ConductorReceipt:
    event_type: str
    epoch: int
    event_hash: str


class ConductorClient(Protocol):
    async def submit_event(self, event: ConductorEvent) -> ConductorReceipt:
        ...

    async def get_day_proof(self, day_number: int) -> Optional[DayProof]:
        ...


class InMemoryConductorClient:
    """Lightweight in-memory Conductor implementation for development and tests."""

    def __init__(self, conductor_instance: Conductor = None) -> None:
        self._lock = asyncio.Lock()
        self._conductor = conductor_instance or MockConductor() # Use mock if not provided
        self._events: List[ConductorEvent] = []
        self._day_proofs: Dict[int, DayProof] = {}

    async def submit_event(self, event: ConductorEvent) -> ConductorReceipt:
        async with self._lock:
            self._events.append(event)
            
            # Map ConductorEvent to Conductor's Event types
            conductor_event: Optional[conductor_models.Event] = None
            payload_data = json.loads(event.payload.decode('utf-8'))

            if event.event_type == "PostAnnouncement":
                conductor_event = conductor_models.PostAnnounce(
                    content_cid=payload_data["content_cid"],
                    author_pubkey_hash=payload_data["author_pubkey_hash"],
                    community_id=payload_data["community_id"],
                    creation_day=event.epoch,
                    sig=payload_data["sig"]
                )
            elif event.event_type == "ModerationEvent":
                conductor_event = conductor_models.ModerationEvent(
                    target_ref=payload_data["target_ref"],
                    action=payload_data["action"],
                    reason_hash=payload_data["reason_hash"],
                    creation_day=event.epoch,
                    sig=payload_data["sig"]
                )
            elif event.event_type == "UserRegistration":
                conductor_event = conductor_models.UserRegistration(
                    user_pubkey=payload_data["user_pubkey"],
                    registration_day=event.epoch,
                    day_proof_hash=payload_data["day_proof_hash"],
                    creation_day=event.epoch,
                    sig=payload_data["sig"]
                )
            elif event.event_type == "DayProof":
                conductor_event = conductor_models.DayProof(
                    day_number=payload_data["day_number"],
                    canonical_proof_hash=payload_data["canonical_proof_hash"],
                    validator_quorum_sig=payload_data["validator_quorum_sig"],
                    creation_day=event.epoch,
                    sig=payload_data["sig"]
                )
                await self._conductor.handle_day_proof(conductor_event)
            elif event.event_type == "MembershipChange":
                conductor_event = conductor_models.MembershipChange(
                    change_type=payload_data["change_type"],
                    validator_pubkey=payload_data["validator_pubkey"],
                    effective_day=payload_data["effective_day"],
                    quorum_sig=payload_data["quorum_sig"],
                    creation_day=event.epoch,
                    sig=payload_data["sig"]
                )
            elif event.event_type == "APExportNotice":
                conductor_event = conductor_models.APExportNotice(
                    object_ref=payload_data["object_ref"],
                    policy_hash=payload_data["policy_hash"],
                    creation_day=event.epoch,
                    sig=payload_data["sig"]
                )

            if conductor_event:
                await self._conductor.propose_batch([conductor_event])

            if event.event_type == "DayProof":
                proof = DayProof.model_validate_json(event.payload.decode("utf-8"))
                self._day_proofs[proof.day_number] = proof
        return ConductorReceipt(
            event_type=event.event_type,
            epoch=event.epoch,
            event_hash=base64.urlsafe_b64encode(event.payload).decode("ascii"),
        )

    async def get_day_proof(self, day_number: int) -> Optional[DayProof]:
        async with self._lock:
            return self._day_proofs.get(day_number)


class HttpConductorClient:
    """HTTP-based Conductor adapter following the draft CFP-010 interface."""

    def __init__(self, base_url: str, *, client: Optional[httpx.AsyncClient] = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(base_url=self._base_url, timeout=10.0)
        self._owned_client = client is None

    async def submit_event(self, event: ConductorEvent) -> ConductorReceipt:
        response = await self._client.post(
            "/api/conductor/events",
            json={
                "event_type": event.event_type,
                "epoch": event.epoch,
                "payload": base64.b64encode(event.payload).decode("ascii"),
                "metadata": event.metadata,
            },
        )
        response.raise_for_status()
        data = response.json()
        return ConductorReceipt(
            event_type=data["event_type"],
            epoch=int(data["epoch"]),
            event_hash=str(data["event_hash"]),
        )

    async def get_day_proof(self, day_number: int) -> Optional[DayProof]:
        response = await self._client.get(f"/api/conductor/day-proofs/{day_number}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return DayProof.model_validate(response.json())

    async def aclose(self) -> None:
        if self._owned_client:
            await self._client.aclose()


__all__ = [
    "ConductorClient",
    "ConductorEvent",
    "ConductorReceipt",
    "HttpConductorClient",
    "InMemoryConductorClient",
]
