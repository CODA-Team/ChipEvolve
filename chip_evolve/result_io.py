"""Strict file boundaries for measured facts, without task submission or mutation."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import cast

from eda_toolkits.context import load_context
from eda_toolkits.objectives import (
    condition_id,
    load_objective,
    verify_conditions,
)
from openroad_platform_contracts import validate_identifier, validate_sha256

from .contracts import (
    BusinessInputError,
    CandidateCollection,
    CandidateRef,
    ConfirmedFact,
    ContextScope,
    DiagnosisContextRef,
    EvidenceLocator,
    EvidencePointer,
    EvidenceScope,
    ExecutionState,
    DeliveryState,
    ExportEvidence,
    FileRef,
    FinalConstraints,
    FinalMetrics,
    JSONObject,
    JSONValue,
    MeasuredResult,
    MeasurementConditions,
    NativeCheckpoint,
    NativeEvidence,
    NativeSessionRef,
    ObjectiveRef,
    PhysicalFiles,
    PhysicalResult,
    QualificationEvidence,
    RegisteredFileRef,
    RootResult,
    SingleResult,
    SpecialistKind,
    SpecialistReply,
    SpecialistRequest,
)

from .selection import result_violations

COLLECTION_SCHEMA = "chip-evolve.candidate-delivery.v1"


def freeze(value: object, path: str = "$") -> JSONValue:
    """Validate untrusted JSON primitives before constructing typed objects."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise BusinessInputError(
                "non_finite_metric", path, "finite number required"
            )
        return value
    if isinstance(value, Mapping):
        result: dict[str, JSONValue] = {}
        for key, item in cast(Mapping[object, object], value).items():
            if not isinstance(key, str):
                raise BusinessInputError(
                    "invalid_type", path, "string object keys required"
                )
            result[key] = freeze(item, path + "." + key)
        return MappingProxyType(result)
    if isinstance(value, (list, tuple)):
        return tuple(
            freeze(item, f"{path}[{i}]")
            for i, item in enumerate(cast(Sequence[object], value))
        )
    raise BusinessInputError("invalid_type", path, "JSON value required")


def to_wire(value: JSONValue) -> JSONValue:
    """Thaw transport evidence; never rewrite its source file."""
    if isinstance(value, Mapping):
        return {key: to_wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_wire(item) for item in value]
    return value


def wire_object(value: JSONObject) -> dict[str, JSONValue]:
    return {key: to_wire(item) for key, item in value.items()}


def object_at(value: JSONValue, path: str) -> JSONObject:
    if not isinstance(value, Mapping):
        raise BusinessInputError("invalid_type", path, "object required")
    return value


def required(value: JSONObject, key: str, path: str = "$") -> JSONValue:
    if key not in value:
        raise BusinessInputError("missing_field", path + "." + key, "required field")
    return value[key]


def text(value: JSONValue, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BusinessInputError("invalid_type", path, "nonempty string required")
    return value


def identifier(value: JSONValue, path: str) -> str:
    result = text(value, path)
    try:
        validate_identifier(path, result)
    except ValueError as error:
        raise BusinessInputError("invalid_identifier", path, str(error)) from error
    return result


def sha256(value: JSONValue, path: str) -> str:
    result = text(value, path)
    try:
        validate_sha256(path, result)
    except ValueError as error:
        raise BusinessInputError("invalid_sha256", path, str(error)) from error
    return result


def number(value: JSONValue, path: str, *, nonnegative: bool = False) -> float:
    if value is None:
        raise BusinessInputError("missing_metric", path, "number required")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BusinessInputError("invalid_metric", path, "numeric value required")
    try:
        result = float(value)
    except OverflowError as error:
        raise BusinessInputError(
            "non_finite_metric", path, "finite number required"
        ) from error
    if not math.isfinite(result):
        raise BusinessInputError("non_finite_metric", path, "finite number required")
    if nonnegative and result < 0:
        raise BusinessInputError("invalid_metric", path, "nonnegative number required")
    return result


def count(value: JSONValue, path: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    result = number(value, path, nonnegative=True)
    if not result.is_integer():
        raise BusinessInputError("invalid_metric", path, "integer count required")
    return int(result)


def boolean(value: JSONValue, path: str) -> bool:
    if not isinstance(value, bool):
        raise BusinessInputError("invalid_type", path, "boolean required")
    return value


def sequence(value: JSONValue, path: str) -> tuple[JSONValue, ...]:
    if not isinstance(value, (tuple, list)):
        raise BusinessInputError("invalid_type", path, "array required")
    return tuple(value)


def path_value(value: JSONValue, base: Path, location: str) -> Path:
    path = Path(text(value, location))
    return path if path.is_absolute() else (base / path).resolve()


def file_ref(path: Path) -> FileRef:
    with path.open("rb") as stream:
        return FileRef(
            path.resolve(), hashlib.file_digest(stream, "sha256").hexdigest()
        )


def read_document(path: Path) -> tuple[FileRef, JSONObject]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise BusinessInputError("missing_file", "$", str(path)) from error
    try:
        decoded: object = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise BusinessInputError("invalid_json", "$", str(error)) from error
    value = object_at(freeze(decoded), "$")
    return FileRef(path.resolve(), hashlib.sha256(raw).hexdigest()), value


def parse_metrics(value: JSONValue, path: str = "$.metrics") -> FinalMetrics:
    metrics = object_at(value, path)

    def numeric(key: str, positive: bool = False) -> float:
        return number(
            required(metrics, key, path), path + "." + key, nonnegative=positive
        )

    def integer(key: str) -> int:
        return count(required(metrics, key, path), path + "." + key)

    def optional(key: str) -> float | None:
        return numeric(key) if key in metrics else None

    return FinalMetrics(
        numeric("finish__timing__setup__tns"),
        numeric("finish__timing__setup__ws"),
        numeric("finish__timing__hold__tns"),
        numeric("finish__power__total", True),
        numeric("finish__design__instance__area", True),
        numeric("finish__design__core__area", True),
        numeric("finish__design__die__area", True),
        integer("finish__timing__drv__max_slew"),
        integer("finish__timing__drv__max_cap"),
        integer("design__violations"),
        optional("finish__timing__hold__ws"),
        integer("finish__timing__drv__max_fanout")
        if "finish__timing__drv__max_fanout" in metrics
        else None,
    )


def parse_constraints(value: JSONValue) -> FinalConstraints:
    limits = object_at(value, "$.constraints")

    def numeric(key: str) -> float:
        return number(required(limits, key, "$.constraints"), "$.constraints." + key)

    def integer(key: str) -> int:
        return count(required(limits, key, "$.constraints"), "$.constraints." + key)

    return FinalConstraints(
        numeric("setup_tns_ns_min"),
        numeric("hold_tns_ns_min"),
        integer("max_slew_violations"),
        integer("max_cap_violations"),
        integer("placement_violations"),
        integer("route_drc"),
        numeric("power_total_w_max"),
        numeric("cell_area_um2_max"),
        numeric("core_area_um2_max"),
        numeric("die_area_um2_max"),
    )


def load_objective_ref(path: Path) -> ObjectiveRef:
    origin, value = read_document(path)
    if required(value, "schema_version") != "chip-evolve.objective.v1":
        raise BusinessInputError(
            "unsupported_schema", "$.schema_version", "shared objective v1 required"
        )
    design = identifier(required(value, "design_id"), "$.design_id")
    identity = sha256(required(value, "objective_id"), "$.objective_id")
    identifier(required(value, "reference_run_id"), "$.reference_run_id")
    conditions = object_at(required(value, "conditions"), "$.conditions")
    parse_conditions(conditions)
    libraries = sequence(
        required(conditions, "libraries", "$.conditions"), "$.conditions.libraries"
    )
    if not libraries:
        raise BusinessInputError(
            "missing_field", "$.conditions.libraries", "nonempty library list required"
        )
    for i, item in enumerate((*libraries, required(conditions, "sdc", "$.conditions"))):
        binding = object_at(item, f"$.conditions.inputs[{i}]")
        text(required(binding, "path"), "$.conditions.input.path")
        sha256(required(binding, "sha256"), "$.conditions.input.sha256")
    constraints = parse_constraints(required(value, "constraints"))
    # Toolkits remains the authority for canonical identity and actual files.
    try:
        checked = load_objective(path)
        verify_conditions(checked)
    except (ValueError, OSError) as error:
        raise BusinessInputError(
            "identity_mismatch", "$.objective", str(error)
        ) from error
    if file_ref(path) != origin:
        raise BusinessInputError(
            "changed_input", "$", "objective changed while loading"
        )
    return ObjectiveRef(
        origin, identity, condition_id(checked), design, constraints, conditions
    )


def registered_ref(
    value: JSONValue, path: str, base: Path, producer: str | None = None
) -> RegisteredFileRef:
    ref = object_at(value, path)
    run = (
        identifier(required(ref, "run_id", path), path + ".run_id")
        if producer is None
        else producer
    )
    return RegisteredFileRef(
        run,
        identifier(required(ref, "artifact_id", path), path + ".artifact_id"),
        sha256(required(ref, "sha256", path), path + ".sha256"),
        path_value(ref["path"], base, path + ".path") if "path" in ref else None,
    )


def parse_files(value: JSONValue, base: Path) -> PhysicalFiles:
    files = object_at(value, "$.files")

    def item(key: str) -> Path | None:
        return path_value(files[key], base, "$.files." + key) if key in files else None

    return PhysicalFiles(
        item("odb"), item("sdc"), item("v"), item("def"), item("spef"), item("metrics")
    )


def parse_exports(value: JSONValue, base: Path) -> Mapping[str, ExportEvidence]:
    exports = object_at(value, "$.exports")
    result: dict[str, ExportEvidence] = {}
    for view, item in exports.items():
        packet = object_at(item, "$.exports." + view)
        execution = object_at(required(packet, "execution"), "$.exports.execution")
        run = object_at(required(execution, "run"), "$.exports.execution.run")
        producer = identifier(required(run, "run_id"), "$.exports.execution.run.run_id")
        artifacts = sequence(
            required(execution, "artifacts"), "$.exports.execution.artifacts"
        )
        for a in artifacts:
            raw_artifact = object_at(a, "$.exports.artifact")
            text(required(raw_artifact, "store_key"), "$.exports.artifact.store_key")
            if "kind" in raw_artifact:
                text(raw_artifact["kind"], "$.exports.artifact.kind")
            if "size_bytes" in raw_artifact:
                count(raw_artifact["size_bytes"], "$.exports.artifact.size_bytes")
        refs = tuple(
            registered_ref(a, "$.exports.artifact", base, producer) for a in artifacts
        )
        result[view] = ExportEvidence(view, producer, refs, packet)
    return MappingProxyType(result)


def parse_native(value: JSONValue, base: Path) -> NativeEvidence | None:
    if value is None:
        return None
    native = object_at(value, "$.native_method")
    return NativeEvidence(
        text(required(native, "kind"), "$.native_method.kind"),
        text(native["physical_stage"], "$.native_method.physical_stage")
        if "physical_stage" in native
        else None,
        count(native["route_drc"], "$.native_method.route_drc")
        if "route_drc" in native
        else None,
        count(native["iterations"], "$.native_method.iterations")
        if "iterations" in native
        else None,
        registered_ref(
            native["route_drc_evidence"], "$.native_method.route_drc_evidence", base
        )
        if native.get("route_drc_evidence") is not None
        else None,
        native,
    )


def parse_conditions(value: JSONValue) -> MeasurementConditions:
    row = object_at(value, "$.conditions")

    def string(key: str) -> str | None:
        return text(row[key], "$.conditions." + key) if key in row else None

    clock = (
        number(row["clock_period_ns"], "$.conditions.clock_period_ns")
        if "clock_period_ns" in row
        else None
    )
    if clock is not None and clock <= 0:
        raise BusinessInputError(
            "invalid_metric", "$.conditions.clock_period_ns", "positive clock required"
        )
    units = object_at(row["units"], "$.conditions.units") if "units" in row else None
    return MeasurementConditions(
        string("corner"),
        clock,
        sha256(row["sdc_sha256"], "$.conditions.sdc_sha256")
        if "sdc_sha256" in row
        else None,
        tuple(
            sha256(v, "$.conditions.library_sha256[]")
            for v in sequence(row["library_sha256"], "$.conditions.library_sha256")
        )
        if "library_sha256" in row
        else None,
        object_at(row["toolchain"], "$.conditions.toolchain")
        if "toolchain" in row
        else None,
        boolean(row["propagated_clock"], "$.conditions.propagated_clock")
        if "propagated_clock" in row
        else None,
        string("parasitics"),
        MappingProxyType(
            {
                k: text(required(units, k), "$.conditions.units." + k)
                for k in ("time", "power", "area")
            }
        )
        if units is not None
        else None,
    )


def parse_qualification(value: JSONValue) -> QualificationEvidence | None:
    if value is None:
        return None
    row = object_at(value, "$.qualification")
    return QualificationEvidence(
        identifier(row["producer_run_id"], "$.qualification.producer_run_id")
        if "producer_run_id" in row
        else None,
        sha256(row["input_odb_sha256"], "$.qualification.input_odb_sha256")
        if "input_odb_sha256" in row
        else None,
        text(row["routing_action"], "$.qualification.routing_action")
        if "routing_action" in row
        else None,
        text(row["route_drc_method"], "$.qualification.route_drc_method")
        if "route_drc_method" in row
        else None,
        count(row["route_drc"], "$.qualification.route_drc")
        if "route_drc" in row
        else None,
        row,
    )


def _single(origin: FileRef, value: JSONObject, *, physical: bool) -> SingleResult:
    base = origin.path.parent
    design = identifier(required(value, "design_id"), "$.design_id")
    run = identifier(required(value, "run_id"), "$.run_id")
    metrics = parse_metrics(required(value, "metrics"))
    drc = count(required(value, "route_drc"), "$.route_drc")
    goal = load_objective_ref(
        path_value(required(value, "objective"), base, "$.objective")
    )
    if (design, required(value, "objective_id"), required(value, "condition_id")) != (
        goal.design_id,
        goal.objective_id,
        goal.condition_id,
    ):
        raise BusinessInputError(
            "identity_mismatch",
            "$.objective_id",
            "result differs from the shared objective/conditions",
        )
    conditions = parse_conditions(value.get("conditions", {}))
    for field, observed, expected in (
        ("corner", conditions.corner, goal.conditions.get("corner")),
        (
            "clock_period_ns",
            conditions.clock_period_ns,
            goal.conditions.get("clock_period_ns"),
        ),
    ):
        if observed is not None and expected is not None and observed != expected:
            raise BusinessInputError(
                "identity_mismatch",
                "$.conditions." + field,
                "observation differs from objective",
            )
    if not physical:
        return MeasuredResult(
            origin, design, run, goal, metrics, drc, conditions, value
        )
    files = parse_files(value.get("files", {}), base)
    snapshots = object_at(value.get("snapshot_ids", {}), "$.snapshot_ids")
    views = MappingProxyType(
        {k: identifier(v, "$.snapshot_ids." + k) for k, v in snapshots.items()}
    )
    return PhysicalResult(
        origin,
        design,
        run,
        goal,
        metrics,
        drc,
        conditions,
        value,
        files,
        identifier(value["physical_run_id"], "$.physical_run_id")
        if value.get("physical_run_id") is not None
        else None,
        views,
        parse_exports(value.get("exports", {}), base),
        path_value(value["native_inputs"], base, "$.native_inputs")
        if value.get("native_inputs") is not None
        else None,
        parse_native(value.get("native_method"), base),
        parse_qualification(value.get("qualification")),
    )


def load_result(
    path: Path, *, physical: bool = False, _seen: frozenset[Path] = frozenset()
) -> RootResult:
    origin, value = read_document(path)
    if origin.path in _seen:
        raise BusinessInputError(
            "cyclic_reference", "$", "candidate collection references itself"
        )
    schema = value.get("schema_version")
    if schema == COLLECTION_SCHEMA:
        return _collection(origin, value, _seen | {origin.path})
    if schema is not None:
        raise BusinessInputError(
            "unsupported_schema", "$.schema_version", "unknown result format"
        )
    return _single(origin, value, physical=physical)


def load_single_result(path: Path, *, physical: bool = False) -> SingleResult:
    value = load_result(path, physical=physical)
    if isinstance(value, CandidateCollection):
        raise BusinessInputError(
            "candidate_collection",
            "$",
            "Choose an explicit result from candidate_results",
        )
    return value


def load_physical_result(path: Path) -> PhysicalResult:
    result = load_single_result(path, physical=True)
    if not isinstance(result, PhysicalResult):
        raise BusinessInputError("invalid_type", "$", "physical result required")
    return result


def execution_state(value: JSONValue) -> ExecutionState:
    if value not in ("succeeded", "failed", "timed_out"):
        raise BusinessInputError(
            "invalid_state", "$.execution_state", "terminal native state required"
        )
    return value


def delivery_state(value: JSONValue) -> DeliveryState:
    if value != "completed":
        raise BusinessInputError(
            "invalid_state", "$.delivery_state", "measured delivery must be complete"
        )
    return "completed"


def _collection(
    origin: FileRef, value: JSONObject, seen: frozenset[Path]
) -> CandidateCollection:
    design = identifier(required(value, "design_id"), "$.design_id")
    objective = sha256(required(value, "objective_id"), "$.objective_id")
    condition = sha256(required(value, "condition_id"), "$.condition_id")
    rows = sequence(required(value, "candidate_results"), "$.candidate_results")
    if not rows:
        raise BusinessInputError(
            "missing_field", "$.candidate_results", "nonempty collection required"
        )
    refs: list[CandidateRef] = []
    identities: set[tuple[Path, str]] = set()
    runs: set[str] = set()
    for i, row in enumerate(rows):
        item = object_at(row, f"$.candidate_results[{i}]")
        path = path_value(
            required(item, "result"), origin.path.parent, "$.candidate.result"
        )
        expected = sha256(required(item, "sha256"), "$.candidate.sha256")
        child = load_result(path, _seen=seen)
        if isinstance(child, CandidateCollection):
            raise BusinessInputError(
                "invalid_type", "$.candidate.result", "single result required"
            )
        if child.origin.sha256 != expected:
            raise BusinessInputError(
                "changed_input", "$.candidate.sha256", "Delivered candidate changed"
            )
        if (child.design_id, child.objective_id, child.condition_id) != (
            design,
            objective,
            condition,
        ):
            raise BusinessInputError(
                "identity_mismatch",
                "$.candidate",
                "collection mixes objectives or conditions",
            )
        for name, expected_id in (
            ("run_id", child.run_id),
            ("design_id", design),
            ("objective_id", objective),
            ("condition_id", condition),
        ):
            if required(item, name) != expected_id:
                raise BusinessInputError(
                    "identity_mismatch",
                    "$.candidate." + name,
                    "candidate summary differs",
                )
        if parse_metrics(required(item, "metrics")) != child.metrics:
            raise BusinessInputError(
                "identity_mismatch", "$.candidate.metrics", "candidate summary differs"
            )
        if (
            (path, child.run_id) in identities
            or child.run_id in runs
            or any(r.origin.path == path for r in refs)
        ):
            raise BusinessInputError(
                "duplicate_candidate", "$.candidate_results", "duplicate result/run"
            )
        identities.add((path, child.run_id))
        runs.add(child.run_id)
        failures = tuple(
            text(v, "$.candidate.constraint_violations")
            for v in sequence(
                required(item, "constraint_violations"),
                "$.candidate.constraint_violations",
            )
        )
        feasible = boolean(
            required(item, "final_feasible"), "$.candidate.final_feasible"
        )
        if failures != tuple(result_violations(child)):
            raise BusinessInputError(
                "identity_mismatch",
                "$.candidate.constraint_violations",
                "candidate constraint summary differs from measured facts",
            )
        if feasible == bool(failures):
            raise BusinessInputError(
                "identity_mismatch",
                "$.candidate.final_feasible",
                "inconsistent constraint summary",
            )
        refs.append(CandidateRef(child.origin, child, failures, feasible))
    for key in ("selected_source", "validation"):
        if required(value, key) is not None:
            raise BusinessInputError(
                "invalid_state", "$." + key, "collection does not select automatically"
            )
    if boolean(required(value, "adopted"), "$.adopted"):
        raise BusinessInputError(
            "invalid_state", "$.adopted", "choose an explicit candidate"
        )
    return CandidateCollection(
        origin,
        design,
        objective,
        condition,
        tuple(refs),
        execution_state(required(value, "execution_state")),
        delivery_state(required(value, "delivery_state")),
        object_at(value["native_campaign"], "$.native_campaign")
        if value.get("native_campaign") is not None
        else None,
        value,
    )


def parse_evidence_scope(value: JSONValue) -> EvidenceScope:
    row = object_at(value, "$.evidence.scope")
    return EvidenceScope(
        *(
            identifier(required(row, k, "$.evidence.scope"), "$.evidence.scope." + k)
            for k in ("design_id", "run_id", "snapshot_id")
        )
    )


def parse_locator(value: JSONValue) -> EvidenceLocator:
    row = object_at(value, "$.evidence.locator")
    first = (
        count(row["line_start"], "$.evidence.locator.line_start")
        if row.get("line_start") is not None
        else None
    )
    last = (
        count(row["line_end"], "$.evidence.locator.line_end")
        if row.get("line_end") is not None
        else None
    )
    if first is not None and last is not None and last < first:
        raise BusinessInputError(
            "invalid_range", "$.evidence.locator.line_end", "end precedes start"
        )
    return EvidenceLocator(
        text(required(row, "uri"), "$.evidence.locator.uri"),
        first,
        last,
        text(row["section"], "$.evidence.locator.section")
        if row.get("section") is not None
        else None,
    )


def load_context_ref(path: Path) -> DiagnosisContextRef:
    origin, packet = read_document(path)
    if required(packet, "schema_version") != "chip-evolve.design-context.v1":
        raise BusinessInputError(
            "unsupported_schema", "$.schema_version", "professional context v1 required"
        )
    identity = sha256(required(packet, "context_id"), "$.context_id")
    raw_scope = object_at(required(packet, "scope"), "$.scope")
    scope = ContextScope(
        identifier(required(raw_scope, "design_id"), "$.scope.design_id"),
        identifier(required(raw_scope, "run_id"), "$.scope.run_id"),
        identifier(required(raw_scope, "snapshot_id"), "$.scope.snapshot_id"),
        text(raw_scope["revision_id"], "$.scope.revision_id")
        if raw_scope.get("revision_id") is not None
        else None,
        text(raw_scope["stage"], "$.scope.stage")
        if raw_scope.get("stage") is not None
        else None,
    )
    evidence: list[EvidencePointer] = []
    for item in sequence(required(packet, "evidence"), "$.evidence"):
        ref = object_at(item, "$.evidence[]")
        evidence.append(
            EvidencePointer(
                identifier(required(ref, "evidence_id"), "$.evidence.evidence_id"),
                parse_evidence_scope(required(ref, "scope")),
                parse_locator(required(ref, "locator")),
                sha256(required(ref, "source_hash"), "$.evidence.source_hash"),
            )
        )
    known = {ref.evidence_id for ref in evidence}
    if len(known) != len(evidence):
        raise BusinessInputError(
            "duplicate_evidence", "$.evidence", "duplicate evidence identity"
        )
    facts: list[ConfirmedFact] = []
    for item in sequence(required(packet, "confirmed_facts"), "$.confirmed_facts"):
        fact = object_at(item, "$.confirmed_facts[]")
        ids = tuple(
            identifier(v, "$.confirmed_facts.evidence_ids")
            for v in sequence(
                required(fact, "evidence_ids"), "$.confirmed_facts.evidence_ids"
            )
        )
        if not ids or not set(ids) <= known:
            raise BusinessInputError(
                "missing_evidence",
                "$.confirmed_facts.evidence_ids",
                "fact has unresolved citations",
            )
        facts.append(
            ConfirmedFact(
                text(required(fact, "text"), "$.confirmed_facts.text"),
                ids,
                text(fact["kind"], "$.confirmed_facts.kind")
                if "kind" in fact
                else None,
                text(fact["certainty"], "$.confirmed_facts.certainty")
                if "certainty" in fact
                else None,
            )
        )
    if not facts or not evidence:
        raise BusinessInputError(
            "missing_evidence", "$.confirmed_facts", "actual supported facts required"
        )
    try:
        load_context(path)
    except ValueError as error:
        raise BusinessInputError(
            "identity_mismatch", "$.context_id", str(error)
        ) from error
    if file_ref(path) != origin:
        raise BusinessInputError("changed_input", "$", "context changed while loading")
    return DiagnosisContextRef(
        origin, identity, scope, tuple(facts), tuple(evidence), packet
    )


def specialist_reply(capability: SpecialistKind, path: Path) -> SpecialistReply:
    result = load_result(path, physical=True)
    evidence_only = (
        isinstance(result, CandidateCollection)
        and result.execution_state != "succeeded"
    )
    session = None
    if isinstance(result, PhysicalResult) and result.native_method is not None:
        execution = result.native_method.wire.get("execution")
        if execution is not None:
            receipt_path = path_value(
                execution, path.parent, "$.native_method.execution"
            )
            # A missing historical local receipt remains unknown; never fabricate it.
            if receipt_path.is_file():
                origin, receipt = read_document(receipt_path)
                run = object_at(required(receipt, "run"), "$.native_session.run")
                session = NativeSessionRef(
                    identifier(required(run, "run_id"), "$.native_session.run.run_id"),
                    origin,
                )
    return SpecialistReply(
        capability, result, "evidence_only" if evidence_only else "delivered", session
    )


def physical_view(origin: FileRef, value: object) -> PhysicalResult:
    """Parse a producer/materialized view; origin remains its immutable source."""
    result = _single(origin, object_at(freeze(value), "$"), physical=True)
    if not isinstance(result, PhysicalResult):
        raise BusinessInputError("invalid_type", "$", "physical result required")
    return result


def load_physical_source(path: Path) -> PhysicalResult | NativeCheckpoint:
    """Explicit ORFS replay accepts the existing unmeasured checkpoint variant."""
    origin, value = read_document(path)
    if value.get("kind") != "qualify":
        return load_physical_result(path)
    hashes = object_at(required(value, "input_hashes"), "$.input_hashes")
    if not hashes:
        raise BusinessInputError(
            "missing_field", "$.input_hashes", "frozen native inputs required"
        )
    native = object_at(required(value, "native_method"), "$.native_method")
    text(required(native, "physical_stage"), "$.native_method.physical_stage")
    return NativeCheckpoint(
        origin,
        identifier(required(value, "design_id"), "$.design_id"),
        identifier(required(value, "producer"), "$.producer"),
        path_value(required(value, "objective"), origin.path.parent, "$.objective"),
        path_value(required(value, "odb"), origin.path.parent, "$.odb"),
        MappingProxyType(
            {k: sha256(v, "$.input_hashes." + k) for k, v in hashes.items()}
        ),
        value,
    )


def check_specialist_call(
    capability: SpecialistKind,
    request: SpecialistRequest,
    source: PhysicalResult,
    objective: ObjectiveRef,
    context: DiagnosisContextRef,
) -> None:
    """Public Python adapters have the same no-submission input boundary as CLI."""
    check_adapter_types(request, source)
    if request.capability != capability or request.design != source.design_id:
        raise BusinessInputError(
            "identity_mismatch", "$.capability", "request differs from adapter/source"
        )
    if (objective.design_id, objective.objective_id, objective.condition_id) != (
        source.design_id,
        source.objective_id,
        source.condition_id,
    ):
        raise BusinessInputError(
            "identity_mismatch", "$.objective_id", "objective differs from source"
        )
    if (context.scope.design_id, context.scope.run_id) != (
        source.design_id,
        source.run_id,
    ) or context.scope.snapshot_id not in source.snapshot_ids.values():
        raise BusinessInputError(
            "identity_mismatch",
            "$.scope.snapshot_id",
            "context differs from source run/snapshot",
        )
    for origin in (source.origin, objective.origin, context.origin):
        if file_ref(origin.path) != origin:
            raise BusinessInputError("changed_input", "$", str(origin.path))


def check_adapter_types(request: object, source: object) -> None:
    if not isinstance(request, SpecialistRequest) or not isinstance(
        source, PhysicalResult
    ):
        raise BusinessInputError(
            "invalid_type",
            "$.source",
            "typed specialist request and physical source required",
        )
