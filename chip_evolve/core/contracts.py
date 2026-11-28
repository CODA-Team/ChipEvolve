"""Immutable business values; wire dictionaries remain transport evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias

if TYPE_CHECKING:
    from chip_evolve.core.config import Deployment

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | Mapping[str, "JSONValue"] | Sequence["JSONValue"]
JSONObject: TypeAlias = Mapping[str, JSONValue]
SpecialistKind: TypeAlias = Literal["flow", "dpl", "goal", "eco"]
Capability: TypeAlias = Literal["orfs", "flow", "dpl", "goal", "eco"]
Operation: TypeAlias = Literal["evolve", "replay", "framework"]
FlowRecipe: TypeAlias = Literal["legacy", "source"]
ExecutionState: TypeAlias = Literal["succeeded", "failed", "timed_out"]
DeliveryState: TypeAlias = Literal["completed"]


class BusinessInputError(ValueError):
    """An input failure with a stable category and an exact field location."""

    def __init__(self, code: str, path: str, detail: str):
        self.code, self.path, self.detail = code, path, detail
        super().__init__(f"{code}: {path}: {detail}")


@dataclass(frozen=True)
class FileRef:
    path: Path
    sha256: str


@dataclass(frozen=True)
class FinalMetrics:
    setup_tns: float
    setup_ws: float
    hold_tns: float
    power_w: float
    cell_area: float
    core_area: float
    die_area: float
    max_slew: int
    max_cap: int
    placement: int
    hold_ws: float | None = None
    fanout: int | None = None

    def quantities(self) -> tuple[float, ...]:
        return (
            self.setup_tns,
            self.setup_ws,
            self.hold_tns,
            self.power_w,
            self.cell_area,
            self.core_area,
            self.die_area,
        )


@dataclass(frozen=True)
class FinalConstraints:
    setup_tns_min: float
    hold_tns_min: float
    max_slew: int
    max_cap: int
    placement: int
    route_drc: int
    power_w: float
    cell_area: float
    core_area: float
    die_area: float


@dataclass(frozen=True)
class ObjectiveRef:
    origin: FileRef
    objective_id: str
    condition_id: str
    design_id: str
    constraints: FinalConstraints
    conditions: JSONObject

    @property
    def path(self) -> Path:
        return self.origin.path


@dataclass(frozen=True)
class PhysicalFiles:
    odb: Path | None = None
    sdc: Path | None = None
    v: Path | None = None
    def_path: Path | None = None
    spef: Path | None = None
    metrics: Path | None = None

    def require(self, name: str) -> Path:
        values = {
            "odb": self.odb,
            "sdc": self.sdc,
            "v": self.v,
            "def": self.def_path,
            "spef": self.spef,
            "metrics": self.metrics,
        }
        value = values.get(name)
        if value is None:
            raise BusinessInputError(
                "missing_field", "$.files." + name, "physical input required"
            )
        return value


@dataclass(frozen=True)
class RegisteredFileRef:
    producer_run_id: str
    artifact_id: str
    sha256: str
    local_path: Path | None = None


@dataclass(frozen=True)
class NativeEvidence:
    kind: str
    physical_stage: str | None
    route_drc: int | None
    iterations: int | None
    route_drc_evidence: RegisteredFileRef | None
    wire: JSONObject = field(repr=False, compare=False)


@dataclass(frozen=True)
class MeasurementConditions:
    # Missing historical observations remain unknown; known fields are validated.
    corner: str | None
    clock_period_ns: float | None
    sdc_sha256: str | None
    library_sha256: tuple[str, ...] | None
    toolchain: JSONObject | None
    propagated_clock: bool | None
    parasitics: str | None
    units: Mapping[str, str] | None


@dataclass(frozen=True)
class QualificationEvidence:
    producer_run_id: str | None
    input_odb_sha256: str | None
    routing_action: str | None
    route_drc_method: str | None
    route_drc: int | None
    wire: JSONObject = field(repr=False, compare=False)


@dataclass(frozen=True)
class MeasuredResult:
    origin: FileRef
    design_id: str
    run_id: str
    objective: ObjectiveRef
    metrics: FinalMetrics
    route_drc: int
    conditions: MeasurementConditions
    wire: JSONObject = field(repr=False, compare=False)

    @property
    def objective_id(self) -> str:
        return self.objective.objective_id

    @property
    def condition_id(self) -> str:
        return self.objective.condition_id


@dataclass(frozen=True)
class ExportEvidence:
    view: str
    producer_run_id: str
    artifacts: tuple[RegisteredFileRef, ...]
    wire: JSONObject = field(repr=False, compare=False)


@dataclass(frozen=True)
class PhysicalResult(MeasuredResult):
    files: PhysicalFiles
    physical_run_id: str | None
    snapshot_ids: Mapping[str, str]
    exports: Mapping[str, ExportEvidence]
    native_inputs: Path | None
    native_method: NativeEvidence | None
    qualification: QualificationEvidence | None


SingleResult: TypeAlias = MeasuredResult | PhysicalResult


@dataclass(frozen=True)
class CandidateRef:
    origin: FileRef
    result: SingleResult
    constraint_violations: tuple[str, ...]
    final_feasible: bool


@dataclass(frozen=True)
class CandidateCollection:
    origin: FileRef
    design_id: str
    objective_id: str
    condition_id: str
    candidates: tuple[CandidateRef, ...]
    execution_state: ExecutionState
    delivery_state: DeliveryState
    native_campaign: JSONObject | None
    wire: JSONObject = field(repr=False, compare=False)


RootResult: TypeAlias = SingleResult | CandidateCollection


@dataclass(frozen=True)
class ContextScope:
    design_id: str
    run_id: str
    snapshot_id: str
    revision_id: str | None = None
    stage: str | None = None


@dataclass(frozen=True)
class ConfirmedFact:
    text: str
    evidence_ids: tuple[str, ...]
    kind: str | None = None
    certainty: str | None = None


@dataclass(frozen=True)
class EvidenceScope:
    design_id: str
    run_id: str
    snapshot_id: str


@dataclass(frozen=True)
class EvidenceLocator:
    uri: str
    line_start: int | None
    line_end: int | None
    section: str | None


@dataclass(frozen=True)
class EvidencePointer:
    evidence_id: str
    scope: EvidenceScope
    locator: EvidenceLocator
    source_hash: str


@dataclass(frozen=True)
class DiagnosisContextRef:
    origin: FileRef
    context_id: str
    scope: ContextScope
    confirmed_facts: tuple[ConfirmedFact, ...]
    evidence: tuple[EvidencePointer, ...]
    wire: JSONObject = field(repr=False, compare=False)

    @property
    def path(self) -> Path:
        return self.origin.path


@dataclass(frozen=True)
class EcoInputs:
    odb: RegisteredFileRef
    sdc: RegisteredFileRef
    spef: RegisteredFileRef


@dataclass(frozen=True)
class GoalInputs:
    odb: RegisteredFileRef
    sdc: RegisteredFileRef
    v: RegisteredFileRef
    def_ref: RegisteredFileRef


@dataclass(frozen=True)
class DplInputs:
    flow_archive: RegisteredFileRef


@dataclass(frozen=True)
class RegisteredRecipeRef:
    origin: FileRef
    source_run_id: str
    source_result_sha256: str


@dataclass(frozen=True)
class FlowSourceInputs:
    source: FileRef
    recipe: RegisteredRecipeRef | None


@dataclass(frozen=True)
class FlowLegacyInputs:
    sdc: RegisteredFileRef


ProfessionalInputs: TypeAlias = (
    EcoInputs | GoalInputs | DplInputs | FlowSourceInputs | FlowLegacyInputs
)


@dataclass(frozen=True)
class Handoff:
    source_run_id: str
    design_id: str
    objective_id: str
    condition_id: str
    receiver: SpecialistKind
    inputs: ProfessionalInputs
    transformations: str
    acceptance: str
    wire: JSONObject = field(repr=False, compare=False)


@dataclass(frozen=True)
class SearchBudget:
    seconds: int
    rounds: int
    candidates: int | None

    def __post_init__(self) -> None:
        for name, value in (
            ("seconds", self.seconds),
            ("rounds", self.rounds),
            ("candidates", self.candidates),
        ):
            if name == "candidates" and value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise BusinessInputError(
                    "invalid_budget", "$." + name, "positive integer required"
                )


@dataclass(frozen=True)
class QualifiedEnvironmentRef:
    origin: FileRef
    environment_id: str


@dataclass(frozen=True)
class SpecialistRequest:
    design: str
    key: str
    capability: SpecialistKind
    operation: Operation
    budget: SearchBudget
    code_source: Path | None = None
    flow_recipe: FlowRecipe = "legacy"
    environment: QualifiedEnvironmentRef | None = None

    def __post_init__(self) -> None:
        if self.capability not in {"flow", "dpl", "goal", "eco"}:
            raise BusinessInputError(
                "invalid_capability", "$.capability", "unknown specialist"
            )
        if self.operation not in {"evolve", "replay", "framework"}:
            raise BusinessInputError("invalid_mode", "$.operation", "unknown operation")
        if self.operation == "framework" and self.capability != "dpl":
            raise BusinessInputError(
                "invalid_mode", "$.operation", "framework is DPL only"
            )
        if self.capability in {"flow", "dpl"} and self.budget.candidates is None:
            raise BusinessInputError(
                "invalid_budget", "$.candidates", "candidate count required"
            )
        if self.code_source and (
            self.capability not in {"dpl", "goal"} or self.operation != "replay"
        ):
            raise BusinessInputError(
                "invalid_mode", "$.code_source", "fixed source requires DPL/Goal replay"
            )
        if self.capability == "goal" and self.budget.candidates != 4:
            raise BusinessInputError(
                "invalid_budget", "$.candidates", "Goal keeps four Students"
            )
        if self.capability == "eco" and self.budget.candidates is not None:
            raise BusinessInputError(
                "invalid_budget", "$.candidates", "ECO has no candidate-count option"
            )
        if self.capability != "flow" and self.flow_recipe != "legacy":
            raise BusinessInputError(
                "invalid_mode", "$.flow_recipe", "source recipe is Flow only"
            )

    @property
    def seconds(self) -> int:
        return self.budget.seconds

    @property
    def rounds(self) -> int:
        return self.budget.rounds

    @property
    def candidates(self) -> int | None:
        return self.budget.candidates


@dataclass(frozen=True)
class NativeSessionRef:
    producer_run_id: str
    receipt: FileRef | None


@dataclass(frozen=True)
class SpecialistReply:
    capability: SpecialistKind
    output: RootResult
    outcome: Literal["delivered", "evidence_only"]
    native_session: NativeSessionRef | None = None


class SpecialistAdapter(Protocol):
    def __call__(
        self,
        deployment: Deployment,
        request: SpecialistRequest,
        experiment: Path,
        source: PhysicalResult,
        objective: ObjectiveRef,
        context: DiagnosisContextRef,
    ) -> SpecialistReply: ...


@dataclass(frozen=True)
class NativeCheckpoint:
    """Saved native stage input; it is deliberately not a measured Result."""

    origin: FileRef
    design_id: str
    producer_run_id: str
    objective_path: Path
    odb: Path
    input_hashes: Mapping[str, str]
    wire: JSONObject = field(repr=False, compare=False)


CodeCapability: TypeAlias = Literal["dpl", "goal"]
CandidateStatus: TypeAlias = Literal[
    "native_rejected",
    "already_delivered",
    "prepared",
    "pending",
    "delivery_failed",
    "completed",
]


@dataclass(frozen=True)
class NativeCampaignBinding:
    capability: CodeCapability
    design_id: str
    native_design: str
    experiment_id: str
    operations_root: Path
    platform: str | None = None
    case_id: str | None = None
    round_id: str | None = None


@dataclass(frozen=True)
class NativeCandidateEvidence:
    candidate_id: str
    native_record: FileRef
    native_verdict_record: FileRef | None
    checkpoint: FileRef | None
    eligible_for_common_measurement: bool
    native_artifact_problems: tuple[str, ...]
    wire: JSONObject = field(repr=False, compare=False)


@dataclass(frozen=True)
class NativeCandidateExport:
    origin: FileRef
    binding: NativeCampaignBinding
    candidates: tuple[NativeCandidateEvidence, ...]
    wire: JSONObject = field(repr=False, compare=False)


@dataclass(frozen=True)
class VerifiedNativeProducer:
    producer_run_id: str
    checkpoint: FileRef
    registry_evidence: tuple[RegisteredFileRef, ...]
    verification: Literal["direct_artifact", "snapshot_member"]


@dataclass(frozen=True)
class CandidateDeliverySummary:
    inventory: FileRef
    additional_results: FileRef | None
    candidate_counts: Mapping[CandidateStatus, int]
    all_eligible_candidates_delivered: bool
    interpretation: str

    def to_wire(self) -> dict[str, JSONValue]:
        def ref(value: FileRef) -> dict[str, JSONValue]:
            return {"path": str(value.path), "sha256": value.sha256}

        counts: dict[str, JSONValue] = {
            key: value for key, value in self.candidate_counts.items()
        }
        return {
            "inventory": ref(self.inventory),
            "additional_results": ref(self.additional_results)
            if self.additional_results
            else None,
            "candidate_counts": counts,
            "all_eligible_candidates_delivered": self.all_eligible_candidates_delivered,
            "interpretation": self.interpretation,
        }
