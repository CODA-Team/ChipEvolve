"""Own Flow terminal admission, completed candidate delivery and config recovery."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

from .config import Deployment, business_lock, read, write
from .contracts import BusinessInputError, CandidateCollection, ObjectiveRef
from .design_facts import publish
from .jobs import Jobs, digest
from .physical import measure
from .result_io import (
    file_ref,
    load_result,
    read_document,
    object_at,
    required,
    identifier,
    text,
    count,
)


def _check_objective(design_id: str, objective: ObjectiveRef) -> None:
    if objective.design_id != design_id:
        raise BusinessInputError(
            "identity_mismatch",
            "$.objective.design_id",
            "Flow objective belongs to another design",
        )
    if file_ref(objective.path) != objective.origin:
        raise BusinessInputError(
            "changed_input", "$.objective", "Flow objective changed after loading"
        )


def _summary_path(deployment: Deployment, design_id: str, experiment: Path) -> Path:
    design = deployment.design(design_id)
    return (
        experiment
        / "source/flow/backup_dir"
        / design["platform"]
        / design["nickname"]
        / "llm_usage_summary.json"
    )


def _collection(path: Path) -> CandidateCollection:
    result = load_result(path)
    if not isinstance(result, CandidateCollection):
        raise BusinessInputError(
            "invalid_type", "$", "Flow delivery requires a candidate collection"
        )
    return result


def collect_completed(
    deployment: Deployment, design_id: str, experiment: Path, objective: ObjectiveRef
) -> CandidateCollection:
    """Collect only successful native terminal stages; never restart search."""
    _check_objective(design_id, objective)
    lock = experiment / "flow-delivery-lock"
    lock.mkdir(exist_ok=True)
    with business_lock(lock):
        _, summary = read_document(_summary_path(deployment, design_id, experiment))
        if (
            type(summary.get("exit_code")) is not int
            or summary["exit_code"] != 0
            or summary.get("status") not in {"completed", "early_stop"}
        ):
            raise BusinessInputError(
                "invalid_state",
                "$.flow.summary",
                "Collection requires a completed native Flow campaign",
            )
        _deliver_candidates(deployment, design_id, experiment, objective.path)
        return _collection(experiment / "result.json")


def collect_failed_evidence(
    deployment: Deployment, design_id: str, experiment: Path, objective: ObjectiveRef
) -> CandidateCollection:
    """Own the original business lock before the separate delivery lock."""
    _check_objective(design_id, objective)
    with business_lock(experiment):
        lock = experiment / "flow-delivery-lock"
        lock.mkdir(exist_ok=True)
        with business_lock(lock):
            native = _failed_terminal(deployment, design_id, experiment)
            output = experiment / "completed-evidence"
            _deliver_candidates(
                deployment,
                design_id,
                experiment,
                objective.path,
                output=output,
                native_campaign=native,
            )
            return _collection(output / "result.json")


def _failed_terminal(
    deployment: Deployment, design_id: str, experiment: Path
) -> dict[str, Any]:
    summary_path = _summary_path(deployment, design_id, experiment)
    _, summary = read_document(summary_path)
    _, campaign = read_document(experiment / "platform-state/campaign.json")
    campaign_id = identifier(required(campaign, "campaign_id"), "$.flow.campaign_id")
    summary_id = identifier(
        required(summary, "campaign_id"), "$.flow.summary.campaign_id"
    )
    status_name = text(required(summary, "status"), "$.flow.summary.status")
    exit_code = required(summary, "exit_code")
    if exit_code is not None and type(exit_code) is not int:
        raise BusinessInputError(
            "invalid_type", "$.flow.summary.exit_code", "integer exit code required"
        )
    if campaign_id != summary_id:
        raise ValueError("Flow campaign identity differs from its terminal summary")
    owner = object_at(required(campaign, "owner"), "$.flow.owner")
    pid = count(required(owner, "pid"), "$.flow.owner.pid")
    if pid == 0:
        raise BusinessInputError(
            "invalid_identifier", "$.flow.owner.pid", "positive owner PID required"
        )
    ticks = text(required(owner, "start_ticks"), "$.flow.owner.start_ticks")
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except FileNotFoundError:
        fields = []
    if fields and fields[0] != "Z" and fields[19] == ticks:
        raise ValueError("Native Flow owner is still running; no evidence recovery")
    native = {
        key: summary.get(key)
        for key in ("campaign_id", "status", "exit_code", "completed_iterations")
    }
    if status_name != "failed" or exit_code in (None, 0):
        status_path, cleanup_path = (
            experiment / "status.json",
            experiment / "native-frontend-cleanup.json",
        )
        if (
            status_name != "running"
            or exit_code is not None
            or not status_path.is_file()
            or not cleanup_path.is_file()
        ):
            raise ValueError("Completed evidence needs a terminal failed Flow campaign")
        status, cleanup = read(status_path), read(cleanup_path)
        if (
            status.get("status") != "failed"
            or status.get("error_type") != "TimeoutExpired"
            or cleanup.get("status") != "completed"
            or cleanup.get("reason") != "TimeoutExpired"
            or cleanup.get("owner_pid") != pid
        ):
            raise ValueError("Flow timeout lacks matching completed cleanup evidence")
        native.update(
            status="timed_out",
            terminal_evidence={
                "reported_native_status": summary["status"],
                "source": "business-supervisor",
                "files": {
                    str(path.resolve()): digest(path)
                    for path in (summary_path, status_path, cleanup_path)
                },
            },
        )
    return native


def _deliver_candidates(
    deployment: Deployment,
    design_id: str,
    experiment: Path,
    objective: Path,
    *,
    output: Path | None = None,
    native_campaign: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deliver actual finished physical branches; the caller checks campaign state."""
    design = deployment.design(design_id)
    source = experiment / "source"
    output = output or experiment
    output.mkdir(exist_ok=True)
    jobs = Jobs(deployment, design_id, experiment)
    candidates = []
    for path in sorted(
        (experiment / "platform-state").glob("iteration-*/slot-*-route_finish.json")
    ):
        native = read(path)
        if native["status"] != "succeeded":
            continue
        record = {"run": native["terminal_run"], "artifacts": native["artifacts"]}
        folder = output / (path.parent.name + "-" + str(native["candidate_slot"]))
        folder.mkdir(exist_ok=True)
        files = {}
        for suffix, kind in {
            "odb": "raw_design_database",
            "spef": "raw_parasitics",
        }.items():
            file = folder / ("6_final." + suffix)
            jobs.materialize(record, kind, file, suffix="/6_final." + suffix)
            files[suffix] = file
        archive = folder / "flow.zip"
        jobs.materialize(record, "flow_archive", archive)
        measurement = experiment / (folder.name + "-common") / "measurement.json"
        measured = (
            read(measurement)
            if measurement.exists()
            else measure(
                jobs,
                folder.name + "-common",
                files["odb"],
                files["spef"],
                Path(design["sdc"]),
                native["run_id"],
                objective,
            )
        )
        if measured["physical_run_id"] != native["run_id"]:
            raise ValueError("Saved measurement belongs to another physical run")
        config = folder / "config.mk"
        recover_config(source / "flow", experiment / "platform-state", native, config)
        with zipfile.ZipFile(archive) as bundle:
            route = json.loads(bundle.read("flow/logs/5_2_route.json"))
        measured.update(
            route_drc=route["detailedroute__route__drc_errors"],
            flow_archive=str(archive),
            candidate_id=native["candidate_id"],
            native_config=str(config),
            native_flow_dir=str(source / "flow"),
            native_score="Retained in original Flow reports/CP0 feedback",
        )
        if (experiment / "recipe.json").is_file():
            measured["flow_recipe"] = str(experiment / "recipe.json")
        if native_campaign is not None:
            measured["native_campaign"] = native_campaign
            measured["native_method"] = {
                "kind": "completed-physical-evidence-of-failed-flow-search",
                "native_campaign": native_campaign,
                "native_search_completed": False,
            }
        candidate_frame = publish(
            jobs,
            measured,
            result_path=folder / "result.json",
            modes=("orfs", "opensta"),
        )
        write(folder / "result.json", candidate_frame)
        candidates.append(candidate_frame)
    if not candidates:
        raise RuntimeError("No completed native Flow candidate")
    write(output / "candidates.json", candidates)
    from .candidates import deliver_candidates

    return deliver_candidates(
        output,
        [Path(row["native_config"]).parent / "result.json" for row in candidates],
        native_campaign=native_campaign,
    )


def recover_config(
    flow: Path, state: Path, native: dict[str, Any], destination: Path
) -> None:
    """Later native rounds may replace config_N.mk; recover its frozen checkpoint."""
    name = "config_" + str(native["candidate_slot"]) + ".mk"
    wanted = native["input_hashes"]["config"]
    for path in flow.rglob(name):
        if digest(path) == wanted:
            shutil.copyfile(path, destination)
            return
    for path in (state / "checkpoints").glob("iteration-*/native-state.zip"):
        with zipfile.ZipFile(path) as bundle:
            for member in bundle.namelist():
                if Path(member).name == name:
                    content = bundle.read(member)
                    if hashlib.sha256(content).hexdigest() == wanted:
                        destination.write_bytes(content)
                        return
    raise ValueError("Cannot recover the actual native candidate configuration")
