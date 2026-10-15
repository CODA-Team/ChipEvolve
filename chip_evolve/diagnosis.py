"""Deliver the existing Query investigation and its cited context to professionals."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from openroad_platform_client import KernelClient

from .config import Deployment, read, write


def scoped_analysis_references(
    deployment: Deployment, frames: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Expose existing scoped evidence without widening investigation access."""
    client = KernelClient(deployment.value["kernel_url"], timeout=60)
    references = []
    for frame in frames:
        offset = 0
        while rows := client.runs(
            analysis_of_run_id=frame["run_id"],
            run_type="analysis",
            limit=100,
            offset=offset,
        ):
            for row in rows:
                if row["status"] != "succeeded":
                    continue
                artifacts = [
                    {
                        key: artifact[key]
                        for key in (
                            "artifact_id",
                            "kind",
                            "store_key",
                            "sha256",
                            "size_bytes",
                        )
                    }
                    for artifact in client.artifacts(row["run_id"])
                    if artifact["kind"] == "raw_flow_metadata"
                ]
                if artifacts:
                    references.append(
                        {
                            "analysis_run_id": row["run_id"],
                            "analysis_of_run_id": frame["run_id"],
                            "artifacts": artifacts,
                        }
                    )
            offset += len(rows)
    return references


def diagnose(
    deployment: Deployment,
    result_path: Path,
    question: str,
    seconds: int,
    steps: int,
    *,
    against: Path | None = None,
) -> dict[str, Any]:
    frame = read(result_path)
    from .comparisons import professional_facts

    question += "\nPrepared professional/final facts: " + json.dumps(
        professional_facts(frame), ensure_ascii=False
    )
    question += (
        "\nProfessional receiver capabilities: Flow changes ORFS configuration and parameters; "
        "DPLEvolve changes OpenROAD detailed-placement C++ mechanisms; GoalEvolve changes "
        "OpenROAD optimization C++ mechanisms (resizing, Vt selection, buffering, rerouting "
        "and its native recipes), not design RTL; TimingECOAgent applies its existing local "
        "ECO primitives. Map recommendations to these actual capabilities. A diagnosis "
        "does not expand the native edit scope or replace original scoring."
        " TimingECOAgent's default path report focuses on reg2reg; check whether "
        "an action can affect the actual failing group, including register-to-output paths. "
        "For setup investigation request get_timing_paths with check=setup, sort=slack, "
        "order=worst across all groups. Record order alone is not global worst-slack order."
    )
    snapshots = list(frame["snapshot_ids"].values())
    frames = [frame]
    if against:
        from eda_toolkits.objectives import require_same_conditions

        baseline = read(against)
        frames.append(baseline)
        require_same_conditions(baseline, frame)
        if baseline["design_id"] != frame["design_id"]:
            raise ValueError("Diagnosis comparison needs the same design")
        question += "\nPrepared reference facts: " + json.dumps(
            professional_facts(baseline), ensure_ascii=False
        )
        snapshots = [*baseline["snapshot_ids"].values(), *snapshots]
        question += f"\nFixed baseline run: {baseline['run_id']}; current candidate run: {frame['run_id']}. Compare actual matching conditions and inputs before explaining deltas."
    references = scoped_analysis_references(deployment, frames)
    if references:
        compact = [
            {
                **row,
                "artifacts": [
                    artifact
                    for artifact in row["artifacts"]
                    if artifact["store_key"].endswith("/candidate-brief.json")
                ],
            }
            for row in references
            if any(
                artifact["store_key"].endswith("/candidate-brief.json")
                for artifact in row["artifacts"]
            )
        ]
        if compact:
            question += (
                "\nRead these SDK-verified compact candidate views FIRST. They retain "
                "the frozen constraints, native decisions, final PPA and original "
                "refs. Expand individual candidate details only to resolve a specific "
                "question; do not expand every experiment object: "
                + json.dumps(compact, ensure_ascii=False)
            )
        question += (
            "\nExisting analysis runs already belong to these fixed scopes. Read their "
            "registered raw_flow_metadata artifacts for stage/Teacher evidence; source "
            "parent runs may be outside the scope and are not needed: "
            + json.dumps(references, ensure_ascii=False)
        )
    folder = result_path.parent / "query"
    if folder.exists():
        folder = result_path.parent / ("query-" + uuid4().hex[:8])
    folder.mkdir(exist_ok=False)
    base = [deployment.value["query_python"], "-m", "query_agent"]
    settings = [
        "--state-root",
        str(folder),
        "--data-url",
        deployment.value["data_url"],
        "--kernel-url",
        deployment.value["kernel_url"],
    ]
    environment = dict(
        os.environ,
        NO_PROXY="127.0.0.1,localhost",
        no_proxy="127.0.0.1,localhost",
        PYTHONNOUSERSITE="1",
    )
    command = [
        *base,
        "investigate",
        question,
        *settings,
        "--model",
        "codex",
        "--codex-mode",
        "hosted",
        "--max-seconds",
        str(seconds),
        "--max-analyses",
        "0",
        "--max-tool-calls",
        "64",
        "--max-read-bytes",
        "524288",
        "--steps",
        str(steps),
    ]
    for snapshot in snapshots:
        command += ["--snapshot", snapshot]
    process = subprocess.run(
        command,
        env=environment,
        capture_output=True,
        text=True,
        timeout=seconds + 60,
        check=False,
    )
    (folder / "driver.stdout").write_text(process.stdout)
    (folder / "driver.stderr").write_text(process.stderr)
    if process.returncode not in {0, 2} or not process.stdout.strip():
        raise RuntimeError("Query investigation failed; original trace retained")
    state = json.loads(process.stdout)
    if not any(
        scope["design_id"] == frame["design_id"] and scope["run_id"] == frame["run_id"]
        for scope in state["scopes"]
    ):
        raise ValueError("Diagnosis belongs to another design")
    if state["answer"] is None or not state["evidence"]:
        raise RuntimeError(
            "Query has no supported final diagnosis; inspect " + str(folder)
        )
    context = folder / "professional-context.json"
    export = [
        *base,
        "export-professional-context",
        state["investigation_id"],
        *settings,
        "--snapshot",
        frame["snapshot_ids"]["opendb"],
        "--objective",
        "Provide cited design facts and native professional optimization mechanisms",
        "--package-output",
        str(context),
    ]
    completed = subprocess.run(
        export, env=environment, capture_output=True, text=True, timeout=60, check=False
    )
    (folder / "export.stdout").write_text(completed.stdout)
    (folder / "export.stderr").write_text(completed.stderr)
    if completed.returncode:
        raise RuntimeError("Professional context export failed; trace retained")
    value = read(context)
    receipt = {
        "context": str(context),
        "context_id": value["context_id"],
        "investigation_id": state["investigation_id"],
        "summary": value["summary"],
        "facts": len(value["confirmed_facts"]),
        "hypotheses": len(value["hypotheses"]),
        "limitations": value["limitations"],
    }
    write(folder / "receipt.json", receipt)
    write(result_path.parent / "diagnosis.json", receipt)
    return receipt
