"""Deliver completed native Code checkpoints; preserve native promotion decisions."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from .config import Deployment, business_lock, read, write
from .jobs import Jobs, digest
from .lifecycle import WorkPending, pending


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


def _producer(
    client: Any,
    profile: dict[str, Any],
    capability: str,
    row: dict[str, Any],
    archive_root: Path,
) -> str:
    """Bind actual native output bytes to a successful public EF producer."""
    odb = Path(row["checkpoint"])
    matches = []
    for path in Path(profile["operations_root"]).glob("*/leaf.json"):
        leaf = read(path)
        if (
            leaf["request"]["operation"]
            != ("baseline" if capability == "dpl" else "physical")
            or leaf.get("output_files", {}).get(str(odb)) != row["checkpoint_sha256"]
            or leaf.get("exit_code", leaf.get("returncode")) != 0
            or leaf.get("timed_out")
        ):
            continue
        saved = read(path.parent / "execution.json")["run"]
        run = client.run(saved["run_id"])
        if (
            run["status"] != "succeeded"
            or run["project_id"]
            != {"dpl": "dplevolve-common-u3", "goal": "goalevolve-common-u4"}[
                capability
            ]
            or run["design_id"] != profile.get("design_id", profile["design"])
            or run["experiment_id"] != profile["experiment_id"]
        ):
            raise ValueError(
                "Native candidate producer has wrong ownership or terminal status"
            )
        artifacts = client.artifacts(run["run_id"])
        direct = [
            a
            for a in artifacts
            if a["kind"] == "raw_design_database"
            and a["store_key"].endswith("/" + odb.name)
            and a["sha256"] == row["checkpoint_sha256"]
        ]
        if not direct:
            snapshots = [a for a in artifacts if a["kind"] == "data_snapshot"]
            if len(snapshots) != 1:
                raise ValueError("Native checkpoint has no registered EF bytes")
            snapshot = snapshots[0]
            archive = path.parent / "evidence.zip"
            if not archive.exists():
                archive_root.mkdir(parents=True, exist_ok=True)
                archive = archive_root / (run["run_id"] + ".zip")
                client.materialize_artifact(
                    run["run_id"], snapshot["artifact_id"], str(archive)
                )
            if digest(archive) != snapshot["sha256"]:
                raise ValueError("Native EF snapshot content changed")
            with zipfile.ZipFile(archive) as bundle:
                actual = json.loads(bundle.read("manifest.json"))["receipt"]
                if actual != leaf:
                    raise ValueError(
                        "Native leaf differs from its registered EF receipt"
                    )
                members = [
                    name for name in bundle.namelist() if Path(name).name == odb.name
                ]
                if not any(
                    hashlib.sha256(bundle.read(name)).hexdigest()
                    == row["checkpoint_sha256"]
                    for name in members
                ):
                    raise ValueError(
                        "Registered EF snapshot lacks the exact checkpoint"
                    )
        matches.append((run.get("ended_at", ""), run["run_id"]))
    if not matches:
        raise ValueError("Completed native checkpoint has no successful EF producer")
    return max(matches)[1]


def _metadata(index: Path) -> dict[str, Any]:
    value = read(index)
    return {
        "inventory": reference(index),
        "additional_results": value["additional_results"],
        "candidate_counts": dict(
            Counter(item["status"] for item in value["candidates"])
        ),
        "all_eligible_candidates_delivered": all(
            item["status"] in {"completed", "already_delivered", "native_rejected"}
            for item in value["candidates"]
        ),
        "interpretation": "Additional native completed checkpoints, original verdicts retained; Codex judges final feasibility. No source promotion or adoption.",
    }


def collect(
    deployment: Deployment,
    experiment: Path,
    selected: dict[str, Any],
    saved: dict[str, Any],
    *,
    output: Path | None = None,
) -> dict[str, Any]:
    from .candidates import deliver_candidates
    from .delivery import checkpoint, finish

    capability = read(experiment / "request.json")["capability"]
    if capability == "goal-continuation":
        capability = "goal"
    pending_experiment = output if output is not None else experiment
    output = output or experiment / "native-candidates"
    output.mkdir(parents=True, exist_ok=True)
    with business_lock(output):
        manifest_path, index_path = output / "manifest.json", output / "inventory.json"
        if manifest_path.exists():
            manifest = read(manifest_path)
            for ref in manifest["references"]:
                if digest(Path(ref["path"])) != ref["sha256"]:
                    raise ValueError(
                        "Frozen native candidate evidence changed: " + ref["path"]
                    )
            if (
                manifest["selected_producer"] != saved["producer"]
                or manifest["design_id"] != saved["design_id"]
                or manifest["selected_run_id"] != selected["run_id"]
            ):
                raise ValueError("Native candidate selection identity changed")
        else:
            exported_path = output / "native-export.json"
            _export(deployment, experiment, capability, exported_path)
            exported = read(exported_path)
            profile = read(experiment / "profile.json")
            design = deployment.design(saved["design_id"])
            expected = design["nickname"] if capability == "dpl" else design["top"]
            if (
                exported["capability"] != capability
                or exported["design"] != expected
                or profile["design"] != expected
                or (capability == "dpl" and exported["round_id"] != experiment.name)
                or (
                    capability == "dpl"
                    and (
                        exported["case"] != profile["case"]
                        or exported["platform"] != design["platform"]
                        or profile["platform"] != design["platform"]
                    )
                )
                or (
                    capability == "goal" and exported["design_id"] != saved["design_id"]
                )
            ):
                raise ValueError(
                    "Native candidate export belongs to another design/campaign"
                )
            refs = [
                reference(experiment / "profile.json"),
                reference(exported_path),
                *[
                    {"path": path, "sha256": sha}
                    for path, sha in saved["input_hashes"].items()
                ],
            ]
            candidates = []
            client = Jobs(deployment, saved["design_id"], output).client
            # Validate every candidate before any extra EDA, including producer
            # ownership and registered bytes, rather than trusting local filenames.
            for row in exported["candidates"]:
                item = {"candidate": row, "status": "native_rejected"}
                refs.append(row["native_record"])
                if row.get("native_verdict_record"):
                    refs.append(row["native_verdict_record"])
                if row["eligible_for_common_measurement"]:
                    odb = Path(row["checkpoint"]).resolve()
                    odb.relative_to(experiment.resolve())
                    if digest(odb) != row["checkpoint_sha256"]:
                        raise ValueError("Native candidate checkpoint changed")
                    if Path(row["candidate_id"]).name != row["candidate_id"]:
                        raise ValueError(
                            "Native candidate identity is not a single name"
                        )
                    refs.append(reference(odb))
                    producer = _producer(
                        client, profile, capability, row, output / "producer-evidence"
                    )
                    item.update(
                        producer=producer,
                        status=(
                            "already_delivered"
                            if producer == saved["producer"]
                            and digest(odb) == digest(Path(saved["odb"]))
                            else "prepared"
                        ),
                    )
                candidates.append(item)
            manifest = {
                "capability": capability,
                "design_id": saved["design_id"],
                "selected_run_id": selected["run_id"],
                "selected_producer": saved["producer"],
                "references": refs,
                "candidates": candidates,
            }
            for ref in refs:
                if digest(Path(ref["path"])) != ref["sha256"]:
                    raise ValueError(
                        "Frozen native candidate evidence changed: " + ref["path"]
                    )
            write(manifest_path, manifest)
        if index_path.exists() and read(index_path)["status"] == "completed":
            return _metadata(index_path)
        candidates, paths = manifest["candidates"], []
        if index_path.exists():
            previous = read(index_path)
            if previous["manifest"] != reference(manifest_path):
                raise ValueError("Native candidate manifest changed")
            progress = {
                item["candidate"]["candidate_id"]: item
                for item in previous["candidates"]
            }
            for item in candidates:
                if item["status"] == "prepared":
                    old = progress[item["candidate"]["candidate_id"]]
                    for key in (
                        "status",
                        "result",
                        "pending_receipt",
                        "error_type",
                        "detail",
                    ):
                        if key in old:
                            item[key] = old[key]
        index = {
            "status": "delivering",
            "manifest": reference(manifest_path),
            "candidates": candidates,
            "native_promotion_changed": False,
            "adopted": False,
            "original_native_selection": saved["native_method"],
        }
        write(index_path, index)
        for item in candidates:
            if item["status"] in {"native_rejected", "already_delivered"}:
                continue
            if item["status"] == "delivery_failed":
                continue
            if item["status"] == "completed":
                result_path = Path(item["result"]["path"])
                if digest(result_path) != item["result"]["sha256"]:
                    raise ValueError("Completed native candidate result changed")
                paths.append(result_path)
                continue
            row = item["candidate"]
            child = (
                output / "candidates" / (experiment.name + "--" + row["candidate_id"])
            )
            child.mkdir(parents=True, exist_ok=True)
            checkpoint(
                child,
                design_id=saved["design_id"],
                odb=Path(row["checkpoint"]),
                producer=item["producer"],
                objective=Path(saved["objective"]),
                pdk=Path(saved["pdk"]) if saved["pdk"] else None,
                source=Path(saved["source"]) if saved["source"] else None,
                native_method={
                    "kind": "native-candidate",
                    "capability": capability,
                    "candidate": row,
                    "origin_experiment": str(experiment),
                    "native_promotion_changed": False,
                },
            )
            try:
                measured = finish(deployment, child)
                if any(
                    measured[key] != selected[key]
                    for key in ("design_id", "objective_id", "condition_id")
                ):
                    raise ValueError(
                        "Common candidate measurement changed design/objective/conditions"
                    )
            except WorkPending as error:
                item.update(status="pending", pending_receipt=error.receipt)
                index["status"] = "pending"
                write(index_path, index)
                raise pending(
                    output / "lifecycle.json",
                    phase="delivery",
                    reason="native_candidate_delivery_pending",
                    experiment=str(pending_experiment),
                    origin_experiment=str(experiment),
                    child_pending=error.receipt,
                ) from error
            except RuntimeError as error:
                item.update(
                    status="delivery_failed",
                    error_type=type(error).__name__,
                    detail=str(error),
                )
            else:
                item.update(status="completed", result=reference(child / "result.json"))
                item.pop("pending_receipt", None)
                paths.append(child / "result.json")
            write(index_path, index)
        additional = None
        if paths:
            deliver_candidates(output, paths)
            additional = reference(output / "result.json")
        index.update(status="completed", additional_results=additional)
        # The inventory never hashes the parent result, avoiding a circular
        # reference when its immutable index is attached to that result.
        write(index_path, index)
        return _metadata(index_path)


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
    result["native_candidate_evidence"] = collect(deployment, experiment, result, saved)
