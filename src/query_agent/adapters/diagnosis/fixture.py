"""Deterministic evidence-linked diagnosis fixture for Phase IV."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from query_agent.domain.capability import Capability
from query_agent.domain.design import DesignObjectKind, object_ref
from query_agent.domain.diagnosis import (
    DiagnosisFinding,
    DiagnosisProvenance,
    DiagnosisScope,
    DiagnosisSupport,
)
from query_agent.domain.query import QueryContext


class FixtureDiagnosisProvider:
    """Provider-neutral finding backed by one path and one net relationship."""

    _source_hash = "c" * 64

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.DESIGN_RELATION_QUERY})

    def get_findings(
        self, context: QueryContext, *, symptom: str, limit: int = 10
    ) -> Sequence[DiagnosisFinding]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if context.design_id not in (None, "gcd"):
            return ()
        if not any(token in symptom.lower() for token in ("timing", "slack")):
            return ()
        scope = DiagnosisScope(
            design_id=context.design_id or "gcd",
            run_id=context.run_id,
            stage=context.stage or "routing",
        )
        net = object_ref("gcd", DesignObjectKind.NET, "n1")
        instance = object_ref("gcd", DesignObjectKind.INSTANCE, "u2")
        findings = (
            DiagnosisFinding(
                finding_id="finding-001",
                claim=(
                    "Timing degradation is associated with net n1 driving u2/A "
                    "on a -0.2 ns path."
                ),
                affected_object=instance,
                cause_object=net,
                support=(
                    DiagnosisSupport(
                        evidence_kind="timing_path",
                        locator="analysis://timing/paths/path-001",
                        description="path u1/A -> u2/Y has slack=-0.2 ns",
                        source_hash="b" * 64,
                    ),
                    DiagnosisSupport(
                        evidence_kind="design_relation",
                        locator="design://gcd/net/n1",
                        description="net n1 drives sink pin u2/A",
                        source_hash=self._source_hash,
                    ),
                ),
                scope=scope,
                provenance=DiagnosisProvenance(
                    provider="fixture-diagnosis-provider",
                    locator="diagnosis://timing/finding-001",
                    source_hash=self._source_hash,
                    observed_at=datetime(2026, 9, 22, tzinfo=UTC),
                ),
            ),
        )
        return findings[:limit]
