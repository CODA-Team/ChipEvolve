"""Evidence-first Query Agent foundation."""

from .domain.capability import Capability
from .domain.evidence import (
    ArtifactMetadata,
    Evidence,
    EvidenceLocator,
    EvidenceProvenance,
    EvidenceScope,
    EvidenceSourceKind,
    EvidenceStatus,
)
from .domain.query import (
    EvidenceRequirement,
    QueryContext,
    QueryIntent,
    QueryPlan,
    QueryRequest,
    QueryResponse,
    QuerySource,
    QueryStatus,
)
from .domain.trace import ProviderCall, QueryTrace

__all__ = [
    "ArtifactMetadata",
    "Capability",
    "Evidence",
    "EvidenceLocator",
    "EvidenceProvenance",
    "EvidenceRequirement",
    "EvidenceScope",
    "EvidenceSourceKind",
    "EvidenceStatus",
    "ProviderCall",
    "QueryContext",
    "QueryIntent",
    "QueryPlan",
    "QueryRequest",
    "QueryResponse",
    "QuerySource",
    "QueryStatus",
    "QueryTrace",
]
