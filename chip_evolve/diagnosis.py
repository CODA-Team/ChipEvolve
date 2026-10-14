"""Deliver the existing Query investigation and its cited context to professionals."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import Deployment, read, write


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
    question += (
        "\nProfessional receiver capabilities: Flow changes ORFS configuration and parameters; "
        "DPLEvolve changes OpenROAD detailed-placement C++ mechanisms; GoalEvolve changes "
        "OpenROAD optimization C++ mechanisms (resizing, Vt selection, buffering, rerouting "
        "and its native recipes), not design RTL; TimingECOAgent applies its existing local "
        "ECO primitives. Map recommendations to these actual capabilities. A diagnosis "
        "does not expand the native edit scope or replace original scoring."
    )
    snapshots = list(frame["snapshot_ids"].values())
    if against:
        from eda_toolkits.objectives import require_same_conditions

        baseline = read(against)
        require_same_conditions(baseline, frame)
        if baseline["design_id"] != frame["design_id"]:
            raise ValueError("Diagnosis comparison needs the same design")
        snapshots = [*baseline["snapshot_ids"].values(), *snapshots]
        question += f"\nFixed baseline run: {baseline['run_id']}; current candidate run: {frame['run_id']}. Compare actual matching conditions and inputs before explaining deltas."
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
