"""Matched deterministic method replay and factual deltas, without a scorer."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from chip_evolve.core.resources import preset
from chip_evolve.core.comparison_facts import (
    compare,
    compare_results,
    professional_facts as professional_facts,
)
from chip_evolve.core.config import Deployment, read, write
from chip_evolve.core.result_io import load_physical_result
from chip_evolve.core.contracts import BusinessInputError
from chip_evolve.core.jobs import Jobs, digest
from chip_evolve.core.metrics import METRICS as METRICS
from chip_evolve.execution.physical import container, qualify
from chip_evolve.core.proof_policy import proven_points
from chip_evolve.core.selection import violations as violations


def replay_goal(deployment: Deployment, result_path: Path, key: str) -> dict[str, Any]:
    """Run the exact original native Tcl directly beneath an EF command task."""
    wrapped = read(result_path)
    if wrapped["native_method"]["kind"] != "native-baseline":
        raise ValueError(
            "Matched replay needs a fixed native baseline, not a new search"
        )
    original = result_path.parent / "baseline"
    operations = result_path.parent / "operations"
    requests = [
        read(p)
        for p in operations.glob("*/request.json")
        if read(p)["operation"] == "physical" and read(p)["cwd"] == str(original)
    ]
    if len(requests) != 1:
        raise ValueError("Choose one native physical baseline operation")
    request = requests[0]
    command = request["command"]
    binary = Path(command[0])
    profile = read(result_path.parent / "profile.json")
    experiment = deployment.experiment(wrapped["design_id"], key)
    native = experiment / "native"
    native.mkdir()
    script = native / "evaluate.tcl"
    script.write_text(Path(command[-1]).read_text().replace(str(original), str(native)))
    jobs = Jobs(deployment, wrapped["design_id"], experiment)
    record = jobs.command(
        "native-method",
        container(deployment, [*command[:-1], str(script)]),
        cwd=native,
        seconds=preset("native-evaluation")["seconds"],
        capture=[
            script,
            native / "post_route.odb",
            native / (deployment.design(wrapped["design_id"])["top"] + ".def"),
            native / (deployment.design(wrapped["design_id"])["top"] + ".v"),
        ],
        parent=wrapped["run_id"],
        objective=Path(wrapped["objective"]),
        kind="native-evaluation",
    )
    jobs.log(record, native / "evaluation.log")
    result = qualify(
        jobs,
        native / "post_route.odb",
        record["run"]["run_id"],
        Path(wrapped["objective"]),
        Path(profile["pdk_root"])
        if profile.get("pdk_root")
        else Path(profile["state_root"])
        / "inputs"
        / deployment.design(wrapped["design_id"])["platform"],
    )
    receipt = {
        "kind": "same native method; direct EF command vs professional EF bridge",
        "binary_sha256": digest(binary),
        "original_script_sha256": digest(Path(command[-1])),
        "scope": "same input DEF/V/SDC/libs, native optimization Tcl, common DRT/RCX and final measurement",
        "input_files": request["inputs"],
        "comparison": compare(wrapped, result),
    }
    write(experiment / "matched-replay.json", receipt)
    write(experiment / "status.json", {"status": "succeeded"})
    return receipt


def verify_logic(
    deployment: Deployment, reference_path: Path, candidate_path: Path, key: str
) -> dict[str, Any]:
    """Check the measured netlists using fixed Liberty logic models beneath EF."""
    reference, candidate = read(reference_path), read(candidate_path)
    compare(reference, candidate)
    design = deployment.design(candidate["design_id"])
    experiment = deployment.experiment(candidate["design_id"], key)
    script = experiment / "equivalence.ys"
    libraries = [Path(row["path"]) for row in design["libraries"]]
    if any(
        digest(path) != row["sha256"]
        for path, row in zip(libraries, design["libraries"], strict=True)
    ):
        raise ValueError("Declared Liberty logic model changed")
    lines = []
    for frame, name in ((reference, "gold"), (candidate, "gate")):
        lines += [
            "read_liberty -ignore_miss_func -ignore_miss_dir " + str(path)
            for path in libraries
        ]
        lines += [
            "read_verilog " + frame["files"]["v"],
            "hierarchy -top " + design["top"],
            "proc",
            "flatten",
            "rename " + design["top"] + " " + name,
            "design -stash " + name,
        ]
    lines += [
        "design -reset",
        "design -copy-from gold -as gold gold",
        "design -copy-from gate -as gate gate",
        "equiv_make gold gate equiv",
        "hierarchy -top equiv",
        "equiv_simple",
        "equiv_induct -seq 5",
        "equiv_status -assert",
    ]
    script.write_text("\n".join(lines) + "\n")
    jobs = Jobs(deployment, candidate["design_id"], experiment)
    record = jobs.command(
        "logic",
        container(deployment, [deployment.value["tools"]["yosys"], "-s", str(script)]),
        seconds=preset("logic-comparison")["seconds"],
        memory_gib=preset("logic-comparison")["memory_gib"],
        cpu=preset("logic-comparison")["cpu_cores"],
        capture=[script, Path(reference["files"]["v"]), Path(candidate["files"]["v"])],
        parent=candidate["run_id"],
        objective=Path(candidate["objective"]),
        kind="logic-comparison",
    )
    log = jobs.log(record, experiment / "proof.log")
    points = proven_points(log)
    receipt = {
        "kind": "Yosys equiv_status -assert with fixed Liberty logic models",
        "run_id": record["run"]["run_id"],
        "reference_result": str(reference_path),
        "candidate_result": str(candidate_path),
        "proven_points": points,
        "unproven_points": 0,
        "input_hashes": {
            str(path): digest(path)
            for path in [
                *libraries,
                Path(reference["files"]["v"]),
                Path(candidate["files"]["v"]),
            ]
        },
        "scope": "registered netlist sequential equivalence under Liberty logic models; physical signoff is separate",
    }
    write(experiment / "logical-equivalence.json", receipt)
    write(experiment / "status.json", {"status": "succeeded"})
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    replay = sub.add_parser("replay-goal")
    replay.add_argument("--result", type=Path, required=True)
    replay.add_argument("--key", required=True)
    logic = sub.add_parser("verify-logic")
    logic.add_argument("--reference", type=Path, required=True)
    logic.add_argument("--candidate", type=Path, required=True)
    logic.add_argument("--key", required=True)
    delta = sub.add_parser("compare")
    delta.add_argument("--reference", type=Path, required=True)
    delta.add_argument("--candidate", type=Path, required=True)
    delta.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    deployment = Deployment(args.config)
    try:
        reference = (
            load_physical_result(args.reference) if hasattr(args, "reference") else None
        )
        candidate = (
            load_physical_result(args.candidate) if hasattr(args, "candidate") else None
        )
        if args.command == "replay-goal":
            load_physical_result(args.result)
            replay_goal(deployment, args.result.resolve(), args.key)
        elif args.command == "verify-logic":
            if reference is None or candidate is None:
                raise BusinessInputError(
                    "missing_field", "$", "explicit result pair required"
                )
            reference.files.require("v")
            candidate.files.require("v")
            compare_results(reference, candidate)
            verify_logic(
                deployment, args.reference.resolve(), args.candidate.resolve(), args.key
            )
        else:
            if reference is None or candidate is None:
                raise BusinessInputError(
                    "missing_field", "$", "explicit result pair required"
                )
            write(args.output, compare_results(reference, candidate))
    except BusinessInputError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
