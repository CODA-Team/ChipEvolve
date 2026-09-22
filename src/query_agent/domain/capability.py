"""Capabilities that a Query Agent provider may expose."""

from enum import StrEnum


class Capability(StrEnum):
    """Named capabilities, separate from question intent."""

    DOMAIN_KNOWLEDGE = "DOMAIN_KNOWLEDGE"
    ARTIFACT_DISCOVERY = "ARTIFACT_DISCOVERY"
    TEXT_SEARCH = "TEXT_SEARCH"
    EXPLICIT_METRIC = "EXPLICIT_METRIC"
    DESIGN_OBJECT_QUERY = "DESIGN_OBJECT_QUERY"
    DESIGN_RELATION_QUERY = "DESIGN_RELATION_QUERY"
    SPECIALIZED_ANALYSIS = "SPECIALIZED_ANALYSIS"
    RUN_EVIDENCE = "RUN_EVIDENCE"

    @property
    def available_in_phase_i(self) -> bool:
        """Whether the capability is intentionally available in Phase I."""

        return self in {
            Capability.DOMAIN_KNOWLEDGE,
            Capability.ARTIFACT_DISCOVERY,
            Capability.TEXT_SEARCH,
            Capability.EXPLICIT_METRIC,
            Capability.RUN_EVIDENCE,
        }
