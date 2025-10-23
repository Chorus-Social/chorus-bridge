from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from chorus_bridge.core.security import decode_hex


class FederationEnvelopeParseError(ValueError):
    """Raised when the provided bytes cannot be parsed as a federation envelope."""


@dataclass
class FederationEnvelope:
    sender_instance: str
    timestamp: int
    message_type: str
    message_data: bytes
    signature: bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> "FederationEnvelope":
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FederationEnvelopeParseError("federation envelope must be JSON bytes") from exc

        required = {"sender_instance", "timestamp", "message_type", "message_data", "signature"}
        missing = required - payload.keys()
        if missing:
            raise FederationEnvelopeParseError(f"missing fields: {', '.join(sorted(missing))}")

        try:
            message_data = decode_hex(payload["message_data"], label="message_data")
            signature = decode_hex(payload["signature"], label="signature")
        except ValueError as exc:
            raise FederationEnvelopeParseError(str(exc)) from exc

        try:
            timestamp = int(payload["timestamp"])
        except (TypeError, ValueError) as exc:
            raise FederationEnvelopeParseError("timestamp must be integer") from exc

        return cls(
            sender_instance=str(payload["sender_instance"]),
            timestamp=timestamp,
            message_type=str(payload["message_type"]),
            message_data=message_data,
            signature=signature,
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "sender_instance": self.sender_instance,
            "timestamp": self.timestamp,
            "message_type": self.message_type,
            "message_data": self.message_data.hex(),
            "signature": self.signature.hex(),
        }
