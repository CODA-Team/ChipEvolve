"""Recover deterministic delivery after an original professional has finished."""

from __future__ import annotations

import re
from pathlib import Path
from dataclasses import dataclass, replace
from typing import Literal
from typing import Any

from chip_evolve.core.config import Deployment, business_lock, read, write
from chip_evolve.core.jobs import Jobs, digest
from chip_evolve.facts.design_facts import import_snapshot as import_snapshot
from chip_evolve.execution import physical
from chip_evolve.facts import flow_recipe, code_evidence
from chip_evolve.core.candidates import deliver_candidates
from chip_evolve.core.contracts import (
    BusinessInputError,
    CandidateStatus,
    CodeCapability,
    FileRef,
    JSONObject,
    JSONValue,
    NativeCandidateEvidence,
)
from chip_evolve.core.result_io import (
    wire_object,
    freeze,
    object_at,
    identifier,
    required,
    sha256,
    text,
    sequence,
    path_value,
    boolean,
    file_ref,
    parse_metrics,
    count,
)
from chip_evolve.core.lifecycle import WorkPending, pending


def checkpoint(
    experiment: Path,
    *,
    design_id: str,
    odb: Path,
    producer: str,
    objective: Path,
    native_method: dict[str, Any],
    pdk: Path | None = None,
    source: Path | None = None,
    extra_inputs: tuple[Path, ...] = (),
) -> None:
    inputs = [odb, objective, *extra_inputs]
    if pdk:
        inputs += [pdk / "setRC.tcl", pdk / "rcx_patterns.rules"]
    if source:
        inputs.append(source)
    value = {
        "design_id": design_id,
        "kind": "layout" if source else "qualify",
        "odb": str(odb.resolve()),
        "producer": producer,
        "objective": str(objective.resolve()),
        "pdk": str(pdk.resolve()) if pdk else None,
        "source": str(source.resolve()) if source else None,
        "input_hashes": {str(p.resolve()): digest(p) for p in inputs},
        "native_method": native_method,
    }
    path = experiment / "delivery-checkpoint.json"
    if path.exists() and read(path) != value:
        raise ValueError("A completed professional delivery checkpoint cannot change")
    write(path, value)


def layout_source(
    deployment: Deployment, experiment: Path, source_path: Path
) -> dict[str, Any]:
    """New ORFS handoffs retain submitted scripts and defaults; old jobs stay bound."""
    frame = read(source_path)
    if frame.get("flow_recipe") or not frame.get("native_inputs"):
        return frame
    recipe_path = experiment / "recipe.json"
    preparing = experiment / "jobs/prepare-recipe/task.json"
    if (experiment / "source").exists() and not (
        recipe_path.exists() or preparing.exists()
    ):
        return frame
    if not recipe_path.exists():
        flow_recipe.prepare_flow_recipe(deployment, source_path, experiment)
    recipe = read(recipe_path)
    if (
        recipe["source_run_id"] != frame["run_id"]
        or recipe["result_sha256"] != digest(source_path)
        or recipe["design_id"] != frame["design_id"]
    ):
        raise ValueError("Prepared physical recipe belongs to another source")
    frame.update(
        flow_recipe=str(recipe_path),
        native_config=recipe["config_path"],
        native_flow_dir=str(Path(recipe["source"]) / "flow"),
    )
    return frame


def finish(deployment: Deployment, experiment: Path) -> dict[str, Any]:
    prior_result, prior_status = experiment / "result.json", experiment / "status.json"
    completed_legacy_result = (
        prior_result.is_file()
        and prior_status.is_file()
        and read(prior_status).get("status") == "succeeded"
        and "native_candidate_evidence" not in read(prior_result)
    )
    saved = read(experiment / "delivery-checkpoint.json")
    for name, sha in saved["input_hashes"].items():
        if digest(Path(name)) != sha:
            raise ValueError("Delivery input changed: " + name)
    jobs = Jobs(deployment, saved["design_id"], experiment)
    odb, objective = Path(saved["odb"]), Path(saved["objective"])
    modes: dict[str, Any] = (
        {"fact_modes": ("orfs", "opensta")}
        if saved["native_method"].get("kind") == "native-candidate"
        else {}
    )
    if saved["kind"] == "layout":
        result = physical.resume_layout(
            jobs,
            odb,
            layout_source(deployment, experiment, Path(saved["source"])),
            objective,
            saved["producer"],
            **modes,
        )
    else:
        native = saved["native_method"]
        if native.get("physical_stage") == "global_route":
            modes["preserve_global_route"] = True
        if (
            native.get("physical_stage") == "detailed_route"
            and native.get("route_drc") == 0
        ):
            modes["preserve_routing"] = True
            modes["native_route_drc"] = saved["native_method"].get("route_drc")
        result = physical.qualify(
            jobs, odb, saved["producer"], objective, Path(saved["pdk"]), **modes
        )
    result["native_method"] = saved["native_method"]
    if not completed_legacy_result:
        maybe_collect(deployment, experiment, result, saved)
    write(experiment / "result.json", result)
    return result


def replay_checkpoint(result_path: Path) -> dict[str, Any]:
    """Read a current delivery checkpoint or the exact recorded legacy route input."""
    experiment, frame = result_path.parent, read(result_path)
    saved = experiment / "delivery-checkpoint.json"
    if saved.exists():
        value = read(saved)
        for name, sha in value["input_hashes"].items():
            if digest(Path(name)) != sha:
                raise ValueError("Replay input changed: " + name)
        return value
    request = experiment / "requests/qualification.json"
    if not request.exists():
        raise ValueError("Full routing replay needs a recorded professional checkpoint")
    original = read(request)
    odb = Path(original["capture"][0])
    if digest(odb) != frame["qualification"]["input_odb_sha256"]:
        raise ValueError("Recorded routing checkpoint differs from measured input")
    sources = re.findall(
        r"^source \{([^}]+)\}$", Path(original["command"][-1]).read_text(), re.MULTILINE
    )
    if len(sources) != 1 or Path(sources[0]).name != "setRC.tcl":
        raise ValueError("Cannot identify the recorded PDK routing model")
    return {
        "design_id": frame["design_id"],
        "kind": "qualify",
        "odb": str(odb),
        "pdk": str(Path(sources[0]).parent),
        "source": None,
        "objective": frame["objective"],
        "producer": frame["qualification"]["producer_run_id"],
        "native_method": frame.get("native_method", {}),
    }


@dataclass(frozen=True)
class _DeliveryIdentity:
    design_id: str
    run_id: str
    objective_id: str
    condition_id: str


@dataclass(frozen=True)
class _CheckpointInputs:
    producer: str
    odb: FileRef
    objective: Path
    pdk: Path | None
    source: Path | None
    input_refs: tuple[FileRef, ...]
    native_method: JSONObject


@dataclass(frozen=True)
class _CodeDelivery:
    capability: CodeCapability
    experiment: Path
    output: Path
    pending_experiment: Path
    selected: _DeliveryIdentity
    checkpoint: _CheckpointInputs


@dataclass(frozen=True)
class _CandidateDelivery:
    evidence: NativeCandidateEvidence
    status: CandidateStatus
    producer: str | None = None
    result: FileRef | None = None
    pending_receipt: JSONObject | None = None
    error_type: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class _FrozenManifest:
    origin: FileRef
    candidates: tuple[_CandidateDelivery, ...]


@dataclass(frozen=True)
class _DeliveryProgress:
    candidates: tuple[_CandidateDelivery, ...]
    status: Literal["delivering", "pending", "completed"] = "delivering"
    additional: FileRef | None = None


def _identity(value: object) -> _DeliveryIdentity:
    row = object_at(freeze(value), "$.delivery.result")
    return _DeliveryIdentity(
        identifier(required(row, "design_id"), "$.design_id"),
        identifier(required(row, "run_id"), "$.run_id"),
        sha256(required(row, "objective_id"), "$.objective_id"),
        sha256(required(row, "condition_id"), "$.condition_id"),
    )


def _ref_wire(ref: FileRef) -> dict[str, str]:
    return {"path": str(ref.path), "sha256": ref.sha256}


def _load_ref(value: JSONValue, base: Path) -> FileRef:
    row = object_at(value, "$.delivery.reference")
    path = path_value(required(row, "path"), base, "$.delivery.reference.path")
    expected = sha256(required(row, "sha256"), "$.delivery.reference.sha256")
    try:
        ref = file_ref(path)
    except OSError as error:
        raise BusinessInputError(
            "missing_file", "$.delivery.reference", str(path)
        ) from error
    if ref.sha256 != expected:
        raise BusinessInputError(
            "changed_input",
            "$.delivery.reference",
            "Frozen native candidate evidence changed: " + str(path),
        )
    return ref


def _delivery_inputs(
    experiment: Path, selected: object, saved: object, output: Path | None
) -> _CodeDelivery:
    chosen = _identity(selected)
    row = object_at(freeze(saved), "$.delivery.checkpoint")
    if required(row, "design_id") != chosen.design_id:
        raise BusinessInputError(
            "identity_mismatch",
            "$.delivery.design_id",
            "checkpoint and measured selection differ",
        )
    inputs = object_at(required(row, "input_hashes"), "$.delivery.input_hashes")
    refs = tuple(
        _load_ref({"path": path, "sha256": sha}, experiment)
        for path, sha in inputs.items()
    )
    odb = path_value(required(row, "odb"), experiment, "$.delivery.odb")
    frozen_odb = next((ref for ref in refs if ref.path == odb.resolve()), None)
    if frozen_odb is None:
        raise BusinessInputError(
            "missing_evidence",
            "$.delivery.input_hashes",
            "selected checkpoint must be frozen",
        )
    checkpoint_inputs = _CheckpointInputs(
        identifier(required(row, "producer"), "$.delivery.producer"),
        frozen_odb,
        path_value(required(row, "objective"), experiment, "$.delivery.objective"),
        path_value(row["pdk"], experiment, "$.delivery.pdk")
        if row.get("pdk")
        else None,
        path_value(row["source"], experiment, "$.delivery.source")
        if row.get("source")
        else None,
        refs,
        object_at(required(row, "native_method"), "$.delivery.native_method"),
    )
    capability = code_evidence.code_capability(
        read(experiment / "request.json")["capability"]
    )
    return _CodeDelivery(
        capability,
        experiment,
        output or experiment / "native-candidates",
        output if output is not None else experiment,
        chosen,
        checkpoint_inputs,
    )


def _candidate_status(value: JSONValue) -> CandidateStatus:
    if value not in (
        "native_rejected",
        "already_delivered",
        "prepared",
        "pending",
        "delivery_failed",
        "completed",
    ):
        raise BusinessInputError(
            "invalid_state", "$.delivery.candidate.status", "unknown candidate status"
        )
    return value


def _frozen_entry(value: JSONValue, base: Path) -> _CandidateDelivery:
    """Read our persisted delivery row, retaining native payload as wire evidence."""
    row = object_at(value, "$.delivery.candidate")
    native = object_at(required(row, "candidate"), "$.delivery.candidate.native")
    eligible = boolean(
        required(native, "eligible_for_common_measurement"),
        "$.delivery.candidate.eligible",
    )
    checkpoint_ref = (
        _load_ref(
            {"path": native["checkpoint"], "sha256": native["checkpoint_sha256"]}, base
        )
        if native.get("checkpoint") is not None
        and native.get("checkpoint_sha256") is not None
        else None
    )
    if eligible and checkpoint_ref is None:
        raise BusinessInputError(
            "missing_evidence",
            "$.delivery.candidate.checkpoint",
            "eligible checkpoint is missing",
        )
    evidence = NativeCandidateEvidence(
        identifier(required(native, "candidate_id"), "$.delivery.candidate.id"),
        _load_ref(required(native, "native_record"), base),
        _load_ref(native["native_verdict_record"], base)
        if native.get("native_verdict_record") is not None
        else None,
        checkpoint_ref,
        eligible,
        tuple(
            text(v, "$.delivery.candidate.problem")
            for v in sequence(
                required(native, "native_artifact_problems"),
                "$.delivery.candidate.problems",
            )
        ),
        native,
    )
    return _CandidateDelivery(
        evidence,
        _candidate_status(required(row, "status")),
        identifier(row["producer"], "$.delivery.candidate.producer")
        if row.get("producer") is not None
        else None,
        _load_ref(row["result"], base) if row.get("result") is not None else None,
        object_at(row["pending_receipt"], "$.delivery.candidate.pending_receipt")
        if row.get("pending_receipt") is not None
        else None,
        text(row["error_type"], "$.delivery.candidate.error_type")
        if row.get("error_type") is not None
        else None,
        text(row["detail"], "$.delivery.candidate.detail")
        if row.get("detail") is not None
        else None,
    )


def _entry_wire(row: _CandidateDelivery) -> dict[str, JSONValue]:
    value: dict[str, JSONValue] = {
        "candidate": wire_object(row.evidence.wire),
        "status": row.status,
    }
    if row.producer is not None:
        value["producer"] = row.producer
    if row.result is not None:
        value["result"] = _ref_wire(row.result)
    if row.pending_receipt is not None:
        value["pending_receipt"] = wire_object(row.pending_receipt)
    if row.error_type is not None:
        value["error_type"] = row.error_type
    if row.detail is not None:
        value["detail"] = row.detail
    return value


def _prepare_manifest(deployment: Deployment, scope: _CodeDelivery) -> _FrozenManifest:
    path = scope.output / "manifest.json"
    if not path.exists():
        batch = code_evidence.export_candidates(
            deployment,
            scope.experiment,
            scope.capability,
            scope.output / "native-export.json",
        )
        if batch.binding.design_id != scope.selected.design_id:
            raise BusinessInputError(
                "identity_mismatch",
                "$.delivery.export.design_id",
                "export differs from measured selection",
            )
        refs = [
            file_ref(scope.experiment / "profile.json"),
            batch.origin,
            *scope.checkpoint.input_refs,
        ]
        entries = []
        client = Jobs(deployment, scope.selected.design_id, scope.output).client
        # Every native candidate is admitted before the manifest authorizes EDA.
        for candidate in batch.candidates:
            refs.append(candidate.native_record)
            if candidate.native_verdict_record is not None:
                refs.append(candidate.native_verdict_record)
            entry = _CandidateDelivery(candidate, "native_rejected")
            if candidate.eligible_for_common_measurement:
                producer = code_evidence.verify_candidate_producer(
                    client, batch.binding, candidate, scope.output / "producer-evidence"
                )
                refs.append(producer.checkpoint)
                retained = (
                    producer.producer_run_id == scope.checkpoint.producer
                    and producer.checkpoint.sha256 == scope.checkpoint.odb.sha256
                )
                entry = replace(
                    entry,
                    producer=producer.producer_run_id,
                    status="already_delivered" if retained else "prepared",
                )
            entries.append(entry)
        for ref in refs:
            if file_ref(ref.path) != ref:
                raise BusinessInputError(
                    "changed_input",
                    "$.delivery.references",
                    "Frozen native candidate evidence changed: " + str(ref.path),
                )
        write(
            path,
            {
                "capability": scope.capability,
                "design_id": scope.selected.design_id,
                "selected_run_id": scope.selected.run_id,
                "selected_producer": scope.checkpoint.producer,
                "references": [_ref_wire(ref) for ref in refs],
                "candidates": [_entry_wire(row) for row in entries],
            },
        )
    from chip_evolve.core.result_io import read_document

    origin, manifest = read_document(path)
    for ref in sequence(required(manifest, "references"), "$.delivery.references"):
        _load_ref(ref, scope.output)
    if (
        manifest.get("capability"),
        manifest.get("design_id"),
        manifest.get("selected_run_id"),
        manifest.get("selected_producer"),
    ) != (
        scope.capability,
        scope.selected.design_id,
        scope.selected.run_id,
        scope.checkpoint.producer,
    ):
        raise BusinessInputError(
            "identity_mismatch",
            "$.delivery.manifest",
            "Native candidate selection identity changed",
        )
    entries = tuple(
        _frozen_entry(v, scope.output)
        for v in sequence(required(manifest, "candidates"), "$.delivery.candidates")
    )
    if len({row.evidence.candidate_id for row in entries}) != len(entries):
        raise BusinessInputError(
            "duplicate_candidate", "$.delivery.manifest", "duplicate frozen candidate"
        )
    return _FrozenManifest(origin, entries)


def _resume_progress(
    scope: _CodeDelivery, manifest: _FrozenManifest
) -> _DeliveryProgress:
    path = scope.output / "inventory.json"
    if not path.exists():
        return _DeliveryProgress(manifest.candidates)
    from chip_evolve.core.result_io import read_document

    _, index = read_document(path)
    if _load_ref(required(index, "manifest"), scope.output) != manifest.origin:
        raise BusinessInputError(
            "changed_input", "$.delivery.manifest", "Native candidate manifest changed"
        )
    if index.get("status") not in ("delivering", "pending"):
        raise BusinessInputError(
            "invalid_state",
            "$.delivery.inventory",
            "unsupported unfinished delivery state",
        )
    rows = tuple(
        _frozen_entry(v, scope.output)
        for v in sequence(required(index, "candidates"), "$.delivery.candidates")
    )
    by_id = {row.evidence.candidate_id: row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != {
        row.evidence.candidate_id for row in manifest.candidates
    }:
        raise BusinessInputError(
            "identity_mismatch",
            "$.delivery.inventory",
            "inventory differs from frozen candidates",
        )
    ordered = []
    for original in manifest.candidates:
        row = by_id[original.evidence.candidate_id]
        if (
            row.evidence.wire != original.evidence.wire
            or row.producer != original.producer
        ):
            raise BusinessInputError(
                "identity_mismatch",
                "$.delivery.inventory",
                "frozen candidate/producer changed",
            )
        if (original.status != "prepared" and row.status != original.status) or (
            original.status == "prepared"
            and row.status in ("native_rejected", "already_delivered")
        ):
            raise BusinessInputError(
                "invalid_state",
                "$.delivery.inventory",
                "candidate changed its delivery identity",
            )
        if row.status == "completed" and row.result is None:
            raise BusinessInputError(
                "missing_evidence",
                "$.delivery.candidate.result",
                "completed result missing",
            )
        if row.status == "completed" and row.result is not None:
            _, measured = read_document(row.result.path)
            parse_metrics(required(measured, "metrics"))
            count(required(measured, "route_drc"), "$.delivery.result.route_drc")
            identity = _identity(measured)
            expected = scope.selected
            native = object_at(
                required(measured, "native_method"), "$.delivery.result.native_method"
            )
            if (
                (identity.design_id, identity.objective_id, identity.condition_id)
                != (expected.design_id, expected.objective_id, expected.condition_id)
                or native.get("kind") != "native-candidate"
                or native.get("candidate") != row.evidence.wire
                or native.get("capability") != scope.capability
            ):
                raise BusinessInputError(
                    "identity_mismatch",
                    "$.delivery.result",
                    "completed result is not the frozen delivery candidate",
                )
        ordered.append(row)
    return _DeliveryProgress(tuple(ordered))


def _persist_inventory(
    scope: _CodeDelivery, manifest: _FrozenManifest, progress: _DeliveryProgress
) -> None:
    value: dict[str, JSONValue] = {
        "status": progress.status,
        "manifest": _ref_wire(manifest.origin),
        "candidates": [_entry_wire(row) for row in progress.candidates],
        "native_promotion_changed": False,
        "adopted": False,
        "original_native_selection": wire_object(scope.checkpoint.native_method),
    }
    if progress.status == "completed":
        value["additional_results"] = (
            _ref_wire(progress.additional) if progress.additional else None
        )
    write(scope.output / "inventory.json", value)


def _deliver_remaining(
    deployment: Deployment,
    scope: _CodeDelivery,
    manifest: _FrozenManifest,
    progress: _DeliveryProgress,
) -> _DeliveryProgress:
    rows = list(progress.candidates)
    for position, row in enumerate(rows):
        if row.status in {
            "native_rejected",
            "already_delivered",
            "delivery_failed",
            "completed",
        }:
            continue
        checkpoint_ref = row.evidence.checkpoint
        if checkpoint_ref is None or row.producer is None:
            raise BusinessInputError(
                "missing_evidence",
                "$.delivery.candidate",
                "admitted checkpoint/producer required",
            )
        child = (
            scope.output
            / "candidates"
            / (scope.experiment.name + "--" + row.evidence.candidate_id)
        )
        child.mkdir(parents=True, exist_ok=True)
        saved = scope.checkpoint
        checkpoint(
            child,
            design_id=scope.selected.design_id,
            odb=checkpoint_ref.path,
            producer=row.producer,
            objective=saved.objective,
            pdk=saved.pdk,
            source=saved.source,
            native_method={
                "kind": "native-candidate",
                "capability": scope.capability,
                "candidate": wire_object(row.evidence.wire),
                "origin_experiment": str(scope.experiment),
                "native_promotion_changed": False,
            },
        )
        try:
            measured = _identity(finish(deployment, child))
            chosen = scope.selected
            if (measured.design_id, measured.objective_id, measured.condition_id) != (
                chosen.design_id,
                chosen.objective_id,
                chosen.condition_id,
            ):
                raise ValueError(
                    "Common candidate measurement changed design/objective/conditions"
                )
        except WorkPending as error:
            rows[position] = replace(
                row,
                status="pending",
                pending_receipt=object_at(freeze(error.receipt), "$.pending"),
            )
            _persist_inventory(
                scope, manifest, _DeliveryProgress(tuple(rows), "pending")
            )
            raise pending(
                scope.output / "lifecycle.json",
                phase="delivery",
                reason="native_candidate_delivery_pending",
                experiment=str(scope.pending_experiment),
                origin_experiment=str(scope.experiment),
                child_pending=error.receipt,
            ) from error
        except RuntimeError as error:
            rows[position] = replace(
                row,
                status="delivery_failed",
                error_type=type(error).__name__,
                detail=str(error),
            )
        else:
            rows[position] = replace(
                row,
                status="completed",
                result=file_ref(child / "result.json"),
                pending_receipt=None,
            )
        _persist_inventory(scope, manifest, _DeliveryProgress(tuple(rows)))
    return _DeliveryProgress(tuple(rows))


def _complete_inventory(
    scope: _CodeDelivery, manifest: _FrozenManifest, progress: _DeliveryProgress
) -> None:
    paths = [
        row.result.path
        for row in progress.candidates
        if row.status == "completed" and row.result is not None
    ]
    additional = None
    if paths:
        deliver_candidates(scope.output, paths)
        additional = file_ref(scope.output / "result.json")
    _persist_inventory(
        scope, manifest, replace(progress, status="completed", additional=additional)
    )


def collect_code_candidates(
    deployment: Deployment,
    experiment: Path,
    selected: dict[str, Any],
    saved: dict[str, Any],
    *,
    output: Path | None = None,
) -> dict[str, Any]:
    """Compatibility wire facade over frozen admission, recovery and delivery stages."""
    scope = _delivery_inputs(experiment, selected, saved, output)
    scope.output.mkdir(parents=True, exist_ok=True)
    with business_lock(scope.output):
        manifest = _prepare_manifest(deployment, scope)
        index = scope.output / "inventory.json"
        if index.exists() and read(index).get("status") == "completed":
            return code_evidence.summarize_inventory(index).to_wire()
        progress = _resume_progress(scope, manifest)
        _persist_inventory(scope, manifest, progress)
        progress = _deliver_remaining(deployment, scope, manifest, progress)
        _complete_inventory(scope, manifest, progress)
        return code_evidence.summarize_inventory(index).to_wire()


def maybe_collect(
    deployment: Deployment,
    experiment: Path,
    result: dict[str, Any],
    saved: dict[str, Any],
) -> None:
    request_path = experiment / "request.json"
    if not request_path.exists() or saved["native_method"].get("kind") not in {
        "native-search",
        "native-timing-continuation",
    }:
        return
    request = read(request_path)
    if request.get("capability") != "goal-continuation" and (
        request.get("capability") not in {"dpl", "goal"}
        or request.get("operation") != "evolve"
    ):
        return
    result["native_candidate_evidence"] = collect_code_candidates(
        deployment, experiment, result, saved
    )
