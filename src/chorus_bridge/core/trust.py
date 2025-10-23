from __future__ import annotations

import binascii
from dataclasses import dataclass
from typing import Dict

from nacl import exceptions as nacl_exceptions
from nacl.signing import VerifyKey


class UnknownInstanceError(KeyError):
    """Raised when an instance id is not present in the trust store."""


class InvalidPublicKeyError(ValueError):
    """Raised when a configured public key cannot be parsed."""


@dataclass
class TrustStore:
    """In-memory mapping of instance ids to Ed25519 verify keys."""

    _keys: Dict[str, VerifyKey]

    @classmethod
    def from_hex_mapping(cls, mapping: Dict[str, str]) -> "TrustStore":
        parsed: Dict[str, VerifyKey] = {}
        for instance_id, hex_key in mapping.items():
            try:
                raw = binascii.unhexlify(hex_key)
            except (binascii.Error, ValueError) as exc:
                raise InvalidPublicKeyError(f"invalid hex for instance '{instance_id}'") from exc
            try:
                parsed[instance_id] = VerifyKey(raw)
            except nacl_exceptions.CryptoError as exc:
                raise InvalidPublicKeyError(f"invalid Ed25519 key for instance '{instance_id}'") from exc
        return cls(parsed)

    def get(self, instance_id: str) -> VerifyKey:
        try:
            return self._keys[instance_id]
        except KeyError as exc:
            raise UnknownInstanceError(instance_id) from exc

    def contains(self, instance_id: str) -> bool:
        return instance_id in self._keys


__all__ = ["TrustStore", "UnknownInstanceError", "InvalidPublicKeyError"]
