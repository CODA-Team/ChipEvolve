"""Deterministic and unavailable analysis adapters."""

from .fixture import FixtureAnalysisProvider
from .unavailable import UnavailableAnalysisProvider

__all__ = ["FixtureAnalysisProvider", "UnavailableAnalysisProvider"]
