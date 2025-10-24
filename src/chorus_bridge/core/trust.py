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
    """In-memory mapping of instance IDs to Ed25519 verify keys.

    This store is used to verify signatures from trusted Chorus Stage instances.
    """

    _keys: Dict[str, VerifyKey]

    @classmethod
    def from_hex_mapping(cls, mapping: Dict[str, str]) -> "TrustStore":
        """Creates a TrustStore instance from a dictionary of hex-encoded public keys.

        Args:
            mapping: A dictionary where keys are instance IDs and values are hex-encoded Ed25519 public keys.

        Returns:
            A TrustStore instance.

        Raises:
            InvalidPublicKeyError: If any public key is not a valid hex string or Ed25519 key.
        """
        parsed: Dict[str, VerifyKey] = {}
        for instance_id, hex_key in mapping.items():
            try:
                raw = binascii.unhexlify(hex_key)
            except (binascii.Error, ValueError) as exc:
                raise InvalidPublicKeyError(
                    f"invalid hex for instance '{instance_id}'"
                ) from exc
            try:
                parsed[instance_id] = VerifyKey(raw)
            except nacl_exceptions.CryptoError as exc:
                raise InvalidPublicKeyError(
                    f"invalid Ed25519 key for instance '{instance_id}'"
                ) from exc
        return cls(parsed)

    def get(self, instance_id: str) -> VerifyKey:
        """Retrieves the VerifyKey for a given instance ID.

        Args:
            instance_id: The ID of the instance.

        Returns:
            The Ed25519 VerifyKey for the instance.

        Raises:
            UnknownInstanceError: If the instance ID is not found in the trust store.
        """
        try:
            return self._keys[instance_id]
        except KeyError as exc:
            raise UnknownInstanceError(instance_id) from exc

    def contains(self, instance_id: str) -> bool:
        """Checks if the trust store contains a given instance ID.

        Args:
            instance_id: The ID of the instance.

        Returns:
            True if the instance ID is in the store, False otherwise.
        """
        return instance_id in self._keys

    def add_trusted_peer(self, instance_id: str, pubkey_bytes: bytes) -> None:
        """Adds a new trusted peer to the trust store.

        Args:
            instance_id: The ID of the instance to add.
            pubkey_bytes: The raw bytes of the Ed25519 public key.

        Raises:
            InvalidPublicKeyError: If the provided public key is not a valid Ed25519 key.
        """
        try:
            self._keys[instance_id] = VerifyKey(pubkey_bytes)
        except nacl_exceptions.CryptoError as exc:
            raise InvalidPublicKeyError(
                f"invalid Ed25519 key for instance '{instance_id}'"
            ) from exc

    def get_trusted_peers_info(self) -> Dict[str, str]:
        """Returns a dictionary mapping instance IDs to their hex-encoded public keys.

        Returns:
            A dictionary where keys are instance IDs and values are hex-encoded public keys.
        """
        return {
            instance_id: key.to_signing_key().verify_key.hex()
            for instance_id, key in self._keys.items()
        }


__all__ = ["TrustStore", "UnknownInstanceError", "InvalidPublicKeyError"]
