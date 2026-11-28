"""Deliver completed native Code checkpoints; preserve native promotion decisions."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import zipfile
from collections import Counter
from pathlib import Path
from typing import Literal
from types import MappingProxyType

from openroad_platform_client import KernelClient

from .contracts import (
    BusinessInputError,
    CandidateDeliverySummary,
    CandidateStatus,
    CodeCapability,
    FileRef,
    JSONObject,
    JSONValue,
    NativeCampaignBinding,
    NativeCandidateEvidence,
    NativeCandidateExport,
    RegisteredFileRef,
    VerifiedNativeProducer,
)
from .result_io import (
    boolean,
    count,
    file_ref,
    freeze,
    identifier,
    object_at,
    parse_metrics,
    path_value,
    read_document,
    registered_ref,
    required,
    sequence,
    sha256,
    text,
)

from .config import Deployment, read, write
from .jobs import digest


def reference(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": digest(path)}


def _export(
    deployment: Deployment, experiment: Path, capability: str, output: Path
) -> None:
    profile_path = experiment / "profile.json"
    profile = read(profile_path)
    binding = deployment.value["professional"][capability]
    source = Path(binding["source"])
    module = (
        "scripts.platform.candidate_evidence"
        if capability == "dpl"
        else "goalevolve.platform.candidate_evidence"
    )
    env = dict(
        os.environ,
        PYTHONNOUSERSITE="1",
        NO_PROXY="localhost,127.0.0.1,::1",
        no_proxy="localhost,127.0.0.1,::1",
    )
    if capability == "dpl":
        env.update(profile["container_environment"])
    env["PYTHONPYCACHEPREFIX"] = str(output.parent / "pycache")
    command = [
        profile.get("agent_python", profile["client_python"]),
        "-m",
        module,
        "--profile",
        str(profile_path),
        "--output",
        str(output),
    ]
    if capability == "dpl":
        command += ["--round-id", experiment.name]
    with (output.parent / "export.log").open("a") as log:
        subprocess.run(command, cwd=source, env=env, stdout=log, stderr=log, check=True)
    value = read(output)
    value["exporter"] = {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source, text=True
        ).strip(),
        "script": reference(source / (module.replace(".", "/") + ".py")),
    }
    write(output, value)


def code_capability(value: object) -> CodeCapability:
    if value == "goal-continuation":
        return "goal"
    if value not in ("dpl", "goal"):
        raise BusinessInputError(
            "invalid_capability", "$.capability", "Code evidence requires DPL or Goal"
        )
    return "dpl" if value == "dpl" else "goal"


def _checked_file(value: JSONValue, base: Path, location: str) -> FileRef:
    row = object_at(value, location)
    path = path_value(required(row, "path", location), base, location + ".path")
    expected = sha256(required(row, "sha256", location), location + ".sha256")
    try:
        origin = file_ref(path)
    except OSError as error:
        raise BusinessInputError("missing_file", location, str(path)) from error
    if origin.sha256 != expected:
        raise BusinessInputError(
            "changed_input",
            location + ".sha256",
            "Frozen native candidate evidence changed: " + str(path),
        )
    return origin


def _candidate(value: JSONValue, base: Path) -> NativeCandidateEvidence:
    row = object_at(value, "$.candidate")
    name = identifier(required(row, "candidate_id"), "$.candidate.candidate_id")
    if Path(name).name != name or name in {".", ".."}:
        raise BusinessInputError(
            "invalid_identifier",
            "$.candidate.candidate_id",
            "one candidate name required",
        )
    eligible = boolean(
        required(row, "eligible_for_common_measurement"),
        "$.candidate.eligible_for_common_measurement",
    )
    checkpoint = None
    if row.get("checkpoint") is not None and row.get("checkpoint_sha256") is not None:
        checkpoint = _checked_file(
            {"path": row["checkpoint"], "sha256": row["checkpoint_sha256"]},
            base,
            "$.candidate.checkpoint",
        )
    if eligible and checkpoint is None:
        raise BusinessInputError(
            "missing_field",
            "$.candidate.checkpoint",
            "eligible candidate requires actual checkpoint bytes",
        )
    return NativeCandidateEvidence(
        name,
        _checked_file(
            required(row, "native_record"), base, "$.candidate.native_record"
        ),
        _checked_file(
            row["native_verdict_record"], base, "$.candidate.native_verdict_record"
        )
        if row.get("native_verdict_record") is not None
        else None,
        checkpoint,
        eligible,
        tuple(
            text(v, "$.candidate.native_artifact_problems[]")
            for v in sequence(
                required(row, "native_artifact_problems"),
                "$.candidate.native_artifact_problems",
            )
        ),
        row,
    )


def export_candidates(
    deployment: Deployment, experiment: Path, capability: CodeCapability, output: Path
) -> NativeCandidateExport:
    """Export and bind native evidence, without running search or EDA."""
    capability = code_capability(capability)
    _export(deployment, experiment, capability, output)
    origin, exported = read_document(output)
    _, profile = read_document(experiment / "profile.json")
    native_design = identifier(required(profile, "design"), "$.profile.design")
    design_id = identifier(
        profile.get("design_id", native_design), "$.profile.design_id"
    )
    design = deployment.design(design_id)
    expected = design["nickname"] if capability == "dpl" else design["top"]
    if (
        exported.get("capability") != capability
        or exported.get("design") != expected
        or native_design != expected
    ):
        raise BusinessInputError(
            "identity_mismatch",
            "$.export.design",
            "Native candidate export belongs to another design/campaign",
        )
    platform = case = round_id = None
    if capability == "dpl":
        platform = identifier(required(profile, "platform"), "$.profile.platform")
        case = identifier(required(profile, "case"), "$.profile.case")
        round_id = text(required(exported, "round_id"), "$.export.round_id")
        if (
            round_id != experiment.name
            or exported.get("case") != case
            or exported.get("platform") != platform
            or platform != design["platform"]
        ):
            raise BusinessInputError(
                "identity_mismatch",
                "$.export.round_id",
                "Native candidate export belongs to another design/campaign",
            )
    elif exported.get("design_id") != design_id:
        raise BusinessInputError(
            "identity_mismatch",
            "$.export.design_id",
            "Native candidate export belongs to another design/campaign",
        )
    binding = NativeCampaignBinding(
        capability,
        design_id,
        native_design,
        identifier(required(profile, "experiment_id"), "$.profile.experiment_id"),
        path_value(
            required(profile, "operations_root"),
            experiment,
            "$.profile.operations_root",
        ),
        platform,
        case,
        round_id,
    )
    candidates = tuple(
        _candidate(v, experiment)
        for v in sequence(required(exported, "candidates"), "$.export.candidates")
    )
    if len({v.candidate_id for v in candidates}) != len(candidates):
        raise BusinessInputError(
            "duplicate_candidate",
            "$.export.candidates",
            "candidate identities must be unique",
        )
    for candidate in candidates:
        if (
            candidate.eligible_for_common_measurement
            and candidate.checkpoint is not None
        ):
            try:
                candidate.checkpoint.path.relative_to(experiment.resolve())
            except ValueError as error:
                raise BusinessInputError(
                    "identity_mismatch",
                    "$.candidate.checkpoint",
                    "checkpoint is outside the native experiment",
                ) from error
    return NativeCandidateExport(origin, binding, candidates, exported)


def verify_candidate_producer(
    client: KernelClient,
    binding: NativeCampaignBinding,
    candidate: NativeCandidateEvidence,
    archive_root: Path,
) -> VerifiedNativeProducer:
    """Bind exact native bytes to successful public EF producer/artifact evidence."""
    capability = code_capability(binding.capability)
    checkpoint = candidate.checkpoint
    if not candidate.eligible_for_common_measurement or checkpoint is None:
        raise BusinessInputError(
            "missing_field",
            "$.candidate.checkpoint",
            "eligible measured candidate required",
        )
    if file_ref(checkpoint.path) != checkpoint:
        raise BusinessInputError(
            "changed_input",
            "$.candidate.checkpoint",
            "Native candidate checkpoint changed",
        )
    matches: list[
        tuple[
            str,
            str,
            tuple[RegisteredFileRef, ...],
            Literal["direct_artifact", "snapshot_member"],
        ]
    ] = []
    for path in binding.operations_root.glob("*/leaf.json"):
        _, leaf = read_document(path)
        request = object_at(required(leaf, "request"), "$.leaf.request")
        outputs = object_at(leaf.get("output_files", {}), "$.leaf.output_files")
        if (
            request.get("operation")
            != ("baseline" if capability == "dpl" else "physical")
            or outputs.get(str(checkpoint.path)) != checkpoint.sha256
            or leaf.get("exit_code", leaf.get("returncode")) != 0
            or leaf.get("timed_out")
        ):
            continue
        _, execution = read_document(path.parent / "execution.json")
        saved = object_at(required(execution, "run"), "$.execution.run")
        rid = identifier(required(saved, "run_id"), "$.execution.run.run_id")
        run = object_at(freeze(client.run(rid)), "$.registry.run")
        if (
            run.get("status") != "succeeded"
            or run.get("project_id")
            != {"dpl": "dplevolve-common-u3", "goal": "goalevolve-common-u4"}[
                capability
            ]
            or run.get("design_id") != binding.design_id
            or run.get("experiment_id") != binding.experiment_id
        ):
            raise BusinessInputError(
                "identity_mismatch",
                "$.registry.run",
                "Native candidate producer has wrong ownership or terminal status",
            )
        artifacts = [
            object_at(freeze(a), "$.registry.artifact") for a in client.artifacts(rid)
        ]
        direct = [
            a
            for a in artifacts
            if a.get("kind") == "raw_design_database"
            and text(
                required(a, "store_key"), "$.registry.artifact.store_key"
            ).endswith("/" + checkpoint.path.name)
            and a.get("sha256") == checkpoint.sha256
        ]
        method: Literal["direct_artifact", "snapshot_member"] = "direct_artifact"
        if direct:
            refs = tuple(
                registered_ref(a, "$.registry.artifact", archive_root, rid)
                for a in direct
            )
        else:
            snapshots = [a for a in artifacts if a.get("kind") == "data_snapshot"]
            if len(snapshots) != 1:
                raise BusinessInputError(
                    "missing_evidence",
                    "$.registry.artifacts",
                    "Native checkpoint has no registered EF bytes",
                )
            snapshot = snapshots[0]
            ref = registered_ref(snapshot, "$.registry.artifact", archive_root, rid)
            archive = path.parent / "evidence.zip"
            if not archive.exists():
                archive_root.mkdir(parents=True, exist_ok=True)
                archive = archive_root / (rid + ".zip")
                client.materialize_artifact(rid, ref.artifact_id, str(archive))
            if digest(archive) != ref.sha256:
                raise BusinessInputError(
                    "changed_input",
                    "$.registry.snapshot",
                    "Native EF snapshot content changed",
                )
            with zipfile.ZipFile(archive) as bundle:
                actual = object_at(
                    freeze(json.loads(bundle.read("manifest.json"))),
                    "$.snapshot.manifest",
                )
                if actual.get("receipt") != leaf:
                    raise BusinessInputError(
                        "identity_mismatch",
                        "$.snapshot.receipt",
                        "Native leaf differs from its registered EF receipt",
                    )
                if not any(
                    hashlib.sha256(bundle.read(name)).hexdigest() == checkpoint.sha256
                    for name in bundle.namelist()
                    if Path(name).name == checkpoint.path.name
                ):
                    raise BusinessInputError(
                        "missing_evidence",
                        "$.snapshot.checkpoint",
                        "Registered EF snapshot lacks the exact checkpoint",
                    )
            refs, method = (ref,), "snapshot_member"
        matches.append(
            (
                text(run["ended_at"], "$.registry.run.ended_at")
                if run.get("ended_at")
                else "",
                rid,
                refs,
                method,
            )
        )
    if not matches:
        raise BusinessInputError(
            "missing_evidence",
            "$.candidate.producer",
            "Completed native checkpoint has no successful EF producer",
        )
    _, rid, refs, method = max(matches, key=lambda r: (r[0], r[1]))
    return VerifiedNativeProducer(rid, checkpoint, refs, method)


def _status(value: JSONValue) -> CandidateStatus:
    if value not in (
        "native_rejected",
        "already_delivered",
        "prepared",
        "pending",
        "delivery_failed",
        "completed",
    ):
        raise BusinessInputError(
            "invalid_state", "$.inventory.candidate.status", "unknown candidate status"
        )
    return value


def summarize_inventory(index_path: Path) -> CandidateDeliverySummary:
    """Validate frozen inventory references; no EDA or environment requalification."""
    origin, value = read_document(index_path)
    if value.get("status") != "completed":
        raise BusinessInputError(
            "invalid_state", "$.inventory.status", "completed inventory required"
        )
    manifest_ref = _checked_file(
        required(value, "manifest"), index_path.parent, "$.inventory.manifest"
    )
    _, manifest = read_document(manifest_ref.path)
    design = identifier(required(manifest, "design_id"), "$.manifest.design_id")
    capability = code_capability(required(manifest, "capability"))
    for ref in sequence(required(manifest, "references"), "$.manifest.references"):
        _checked_file(ref, manifest_ref.path.parent, "$.manifest.references[]")
    original = {}
    for row in sequence(required(manifest, "candidates"), "$.manifest.candidates"):
        entry = object_at(row, "$.manifest.candidates[]")
        candidate = _candidate(required(entry, "candidate"), manifest_ref.path.parent)
        if candidate.candidate_id in original:
            raise BusinessInputError(
                "duplicate_candidate", "$.manifest.candidates", "duplicate identity"
            )
        original[candidate.candidate_id] = (entry, candidate)
    counts: Counter[CandidateStatus] = Counter()
    completed: dict[Path, JSONObject] = {}
    completed_refs: dict[Path, FileRef] = {}
    completed_runs: set[str] = set()
    seen: set[str] = set()
    for item in sequence(required(value, "candidates"), "$.inventory.candidates"):
        row = object_at(item, "$.inventory.candidates[]")
        candidate = _candidate(required(row, "candidate"), index_path.parent)
        pair = original.get(candidate.candidate_id)
        if pair is None or candidate.candidate_id in seen:
            raise BusinessInputError(
                "identity_mismatch",
                "$.inventory.candidate",
                "inventory differs from manifest candidates",
            )
        saved, before = pair
        if candidate.wire != before.wire or row.get("producer") != saved.get(
            "producer"
        ):
            raise BusinessInputError(
                "identity_mismatch",
                "$.inventory.candidate",
                "inventory changed frozen candidate/producer",
            )
        state = _status(required(row, "status"))
        initial = _status(required(saved, "status"))
        if (initial != "prepared" and state != initial) or (
            initial == "prepared" and state in ("native_rejected", "already_delivered")
        ):
            raise BusinessInputError(
                "invalid_state",
                "$.inventory.candidate.status",
                "candidate changed its eligibility/delivery identity",
            )
        seen.add(candidate.candidate_id)
        counts[state] += 1
        if state == "completed":
            ref = _checked_file(
                required(row, "result"),
                index_path.parent,
                "$.inventory.candidate.result",
            )
            _, result = read_document(ref.path)
            if result.get("design_id") != design:
                raise BusinessInputError(
                    "identity_mismatch",
                    "$.inventory.candidate.result.design_id",
                    "completed result belongs to another design",
                )
            result_run = identifier(required(result, "run_id"), "$.result.run_id")
            if result_run in completed_runs:
                raise BusinessInputError(
                    "duplicate_candidate",
                    "$.result.run_id",
                    "completed results share a measurement run",
                )
            completed_runs.add(result_run)
            sha256(required(result, "objective_id"), "$.result.objective_id")
            sha256(required(result, "condition_id"), "$.result.condition_id")
            parse_metrics(required(result, "metrics"))
            count(required(result, "route_drc"), "$.result.route_drc")
            native = object_at(
                required(result, "native_method"), "$.result.native_method"
            )
            if (
                native.get("kind") != "native-candidate"
                or native.get("capability") != capability
                or native.get("candidate") != candidate.wire
            ):
                raise BusinessInputError(
                    "identity_mismatch",
                    "$.result.native_method",
                    "result is not this frozen native candidate",
                )
            completed[ref.path], completed_refs[ref.path] = result, ref
    if seen != set(original):
        raise BusinessInputError(
            "identity_mismatch",
            "$.inventory.candidates",
            "inventory omits manifest candidates",
        )
    additional = None
    extra = required(value, "additional_results")
    if extra is not None:
        additional = _checked_file(
            extra, index_path.parent, "$.inventory.additional_results"
        )
        _, collection = read_document(additional.path)
        if (
            collection.get("schema_version") != "chip-evolve.candidate-delivery.v1"
            or collection.get("design_id") != design
        ):
            raise BusinessInputError(
                "identity_mismatch",
                "$.additional_results",
                "collection differs from delivery manifest",
            )
        if (
            not completed
            or collection.get("selected_source") is not None
            or collection.get("validation") is not None
            or collection.get("adopted") is not False
        ):
            raise BusinessInputError(
                "invalid_state",
                "$.additional_results",
                "additional collection cannot select or adopt",
            )
        actual: set[Path] = set()
        for item in sequence(
            required(collection, "candidate_results"),
            "$.additional_results.candidate_results",
        ):
            summary = object_at(item, "$.additional_results.candidate")
            path = path_value(
                required(summary, "result"),
                additional.path.parent,
                "$.additional_results.candidate.result",
            )
            target = completed.get(path)
            if (
                target is None
                or path in actual
                or summary.get("sha256") != completed_refs[path].sha256
            ):
                raise BusinessInputError(
                    "identity_mismatch",
                    "$.additional_results.candidate",
                    "collection differs from completed inventory",
                )
            if any(
                collection.get(key) != target.get(key)
                for key in ("objective_id", "condition_id")
            ):
                raise BusinessInputError(
                    "identity_mismatch",
                    "$.additional_results",
                    "collection header differs from completed result",
                )
            for key in (
                "run_id",
                "design_id",
                "objective_id",
                "condition_id",
                "metrics",
            ):
                if required(summary, key) != required(target, key):
                    raise BusinessInputError(
                        "identity_mismatch",
                        "$.additional_results.candidate." + key,
                        "summary differs from completed result",
                    )
            actual.add(path)
        if actual != set(completed):
            raise BusinessInputError(
                "identity_mismatch",
                "$.additional_results",
                "collection omits completed results",
            )
    elif completed:
        raise BusinessInputError(
            "missing_evidence",
            "$.inventory.additional_results",
            "completed candidates need their delivered collection",
        )
    if file_ref(index_path) != origin or file_ref(manifest_ref.path) != manifest_ref:
        raise BusinessInputError(
            "changed_input",
            "$.inventory",
            "inventory/manifest changed while summarizing",
        )
    return CandidateDeliverySummary(
        origin,
        additional,
        MappingProxyType(dict(counts)),
        all(s in ("completed", "already_delivered", "native_rejected") for s in counts),
        "Additional native completed checkpoints, original verdicts retained; Codex judges final feasibility. No source promotion or adoption.",
    )
