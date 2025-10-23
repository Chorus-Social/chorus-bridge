from __future__ import annotations

import binascii
from typing import Iterable

from blake3 import blake3
from nacl import exceptions as nacl_exceptions
from nacl.signing import VerifyKey


class SignatureVerificationError(ValueError):
    """Raised when signature verification fails."""


def decode_hex(value: str, *, label: str) -> bytes:
    """Decode a hex string, raising a descriptive error when invalid."""
    try:
        return binascii.unhexlify(value)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"invalid hex value for {label}") from exc


def envelope_fingerprint(fields: Iterable[bytes]) -> str:
    """
    Produce a deterministic hexadecimal fingerprint for an envelope.

    Using a length-prefix avoids collisions between concatenated field
    boundaries and keeps the hashing contract centralised.
    """
    hasher = blake3()
    for chunk in fields:
        hasher.update(len(chunk).to_bytes(4, "big"))
        hasher.update(chunk)
    return hasher.hexdigest()


def verify_signature(payload: bytes, signature: bytes, verify_key: VerifyKey) -> None:
    """Verify an Ed25519 detached signature."""
    try:
        verify_key.verify(payload, signature)
    except nacl_exceptions.BadSignatureError as exc:
        raise SignatureVerificationError("signature verification failed") from exc


__all__ = ["decode_hex", "envelope_fingerprint", "verify_signature", "SignatureVerificationError"]
