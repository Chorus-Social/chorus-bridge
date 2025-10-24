"""Domain models for Chorus Bridge."""

from .federation import FederationEnvelope, FederationEnvelopeParseError

__all__ = ["FederationEnvelope", "FederationEnvelopeParseError"]
