"""Matched deterministic method replay and factual deltas, without a scorer."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from eda_toolkits.objectives import require_same_conditions

from .config import Deployment, read, write
from .jobs import Jobs, digest
from .physical import container, qualify
from .selection import violations

METRICS = (
    "finish__timing__setup__tns",
    "finish__timing__setup__ws",
    "finish__timing__hold__tns",
    "finish__power__total",
    "finish__design__instance__area",
    "finish__design__core__area",
    "finish__design__die__area",
)


def proven_points(log: str) -> int:
    counts = re.findall(r"Of those cells (\d+) are proven and (\d+) are unproven", log)
    if (
        not counts
        or int(counts[-1][0]) == 0
        or int(counts[-1][1]) != 0
        or "Equivalence successfully proven!" not in log
    ):
        raise ValueError("No complete nonempty equivalence proof in the Yosys receipt")
    return int(counts[-1][0])


def compare(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    require_same_conditions(reference, candidate)
    if (
        reference["design_id"] != candidate["design_id"]
        or reference["objective_id"] != candidate["objective_id"]
    ):
        raise ValueError("Compare the same design and business objective")
    deltas = {}
    for key in METRICS:
        old, new = reference["metrics"][key], candidate["metrics"][key]
        deltas[key] = {
            "reference": old,
            "candidate": new,
            "delta": new - old,
            "percent": 100 * (new - old) / abs(old) if old else None,
        }
    return {
        "reference_run_id": reference["run_id"],
        "candidate_run_id": candidate["run_id"],
        "condition_id": reference["condition_id"],
        "objective_id": reference["objective_id"],
        "deltas": deltas,
        "constraint_violations": violations(candidate),
        "professional_facts": {
            "reference": professional_facts(reference),
            "candidate": professional_facts(candidate),
        },
    }


def professional_facts(frame: dict[str, Any]) -> dict[str, Any]:
    """Keep the original professional decision separate from final feasibility."""
    native = frame.get("native_method")
    failed = violations(frame)
    return {
        "run_id": frame["run_id"],
        "design_id": frame["design_id"],
        "objective_id": frame["objective_id"],
        "condition_id": frame["condition_id"],
        "native_method": native,
        "native_evidence_available": native is not None,
        "final_metrics": {key: frame["metrics"][key] for key in METRICS},
        "final_constraint_violations": failed,
        "final_feasible": not failed,
        "snapshot_ids": frame.get("snapshot_ids", {}),
    }


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
        seconds=3600,
        capture=[
            script,
            native / "post_route.odb",
            native / (deployment.design(wrapped["design_id"])["top"] + ".def"),
            native / (deployment.design(wrapped["design_id"])["top"] + ".v"),
        ],
        parent=wrapped["run_id"],
        objective=Path(wrapped["objective"]),
    )
    jobs.log(record, native / "evaluation.log")
    result = qualify(
        jobs,
        native / "post_route.odb",
        record["run"]["run_id"],
        Path(wrapped["objective"]),
        Path(profile["state_root"]) / "inputs/asap7",
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
        seconds=1800,
        memory_gib=8,
        cpu=2,
        capture=[script, Path(reference["files"]["v"]), Path(candidate["files"]["v"])],
        parent=candidate["run_id"],
        objective=Path(candidate["objective"]),
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
    if args.command == "replay-goal":
        replay_goal(deployment, args.result.resolve(), args.key)
    elif args.command == "verify-logic":
        verify_logic(
            deployment, args.reference.resolve(), args.candidate.resolve(), args.key
        )
    else:
        write(args.output, compare(read(args.reference), read(args.candidate)))


if __name__ == "__main__":
    main()
