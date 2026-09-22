"""Deterministic and unavailable diagnosis adapters."""

from .fixture import FixtureDiagnosisProvider
from .unavailable import UnavailableDiagnosisProvider

__all__ = ["FixtureDiagnosisProvider", "UnavailableDiagnosisProvider"]
