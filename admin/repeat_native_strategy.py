"""Repeat a recorded optimization action from its original inputs through EF/DF.

This repeats fixed professional code/recipe execution, not Teacher/Student search.
The original routed candidate is never used as the optimization input.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from chip_evolve.comparisons import compare
from chip_evolve.config import Deployment, read, write
from chip_evolve.delivery import checkpoint, finish
from chip_evolve.jobs import Jobs, digest
from chip_evolve.physical import container


def recorded_action(result: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    frame = read(result)
    saved = read(result.parent / "delivery-checkpoint.json")
    method = frame.get("native_method", {})
    origin = Path(method.get("origin_experiment", result.parent))
    records = [
        p
        for p in (origin / "operations").glob("*/execution.json")
        if read(p)["run"]["run_id"] == saved["producer"]
    ]
    if len(records) != 1 or read(records[0])["run"]["status"] != "succeeded":
        raise ValueError("Need one successful original professional EF action")
    request = records[0].parent / "request.json"
    action = read(request)
    if action["operation"] != "physical":
        raise ValueError("A build or routing-only measurement is not optimization")
    script = Path(action["command"][-1])
    if script.name != "evaluate.tcl" or "repair_" not in script.read_text():
        raise ValueError("Choose the recorded native optimization Tcl explicitly")
    for name, sha in action["inputs"].items():
        if digest(Path(name)) != sha:
            raise ValueError("Original optimization input changed: " + name)
    return request, action, saved


def relocated_script(script: str, original: Path, destination: Path) -> str:
    """Relocate outputs only; original benchmark/PDK inputs remain frozen."""
    if str(original) not in script:
        raise ValueError("Original native output directory is absent")
    return script.replace(str(original), str(destination))


def repeat(deployment: Deployment, result: Path, key: str) -> dict[str, Any]:
    frame = read(result)
    request, action, saved = recorded_action(result)
    if frame["conditions"]["toolchain"] != deployment.value["toolchain"]:
        raise ValueError("Repetition must use the original common toolchain")
    origin = Path(
        frame.get("native_method", {}).get("origin_experiment", result.parent)
    )
    handoff = read(origin / "input-receipt.json")
    design = frame["design_id"]
    experiment = deployment.experiment(design, key)
    native = experiment / "native"
    native.mkdir()
    original = Path(action["cwd"])
    script = native / "evaluate.tcl"
    script.write_text(
        relocated_script(Path(action["command"][-1]).read_text(), original, native)
    )
    binary = Path(action["command"][0])
    identity = {
        "kind": "independent-fixed-strategy-optimization",
        "source_result": str(result.resolve()),
        "source_result_sha256": digest(result),
        "original_request": str(request.resolve()),
        "original_request_sha256": digest(request),
        "binary_sha256": digest(binary),
        "original_script_sha256": digest(Path(action["command"][-1])),
        "input_hashes": action["inputs"],
        "physical_input_run_id": handoff["source_run_id"],
        "recorded_method_producer_run_id": saved["producer"],
        "condition_id": frame["condition_id"],
        "objective_id": frame["objective_id"],
        "scope": "Full saved optimization action from original inputs plus common DRT/RCX/facts. Does not repeat source generation or earlier relay stages.",
    }
    write(experiment / "repetition-method.json", identity)
    write(
        experiment / "request.json",
        {
            "design": design,
            "capability": "goal",
            "operation": "fixed-strategy-repeat",
            "source": handoff["source"],
            "code_source": str(result.resolve()),
            "key": key,
        },
    )
    write(
        experiment / "input-receipt.json",
        {
            **handoff,
            "operation": "fixed-strategy-repeat",
            "code_source": str(result.resolve()),
        },
    )
    jobs = Jobs(deployment, design, experiment)
    record = jobs.command(
        "native-optimization",
        container(deployment, [*action["command"][:-1], str(script)]),
        cwd=native,
        capture=[
            script,
            binary,
            *[Path(p) for p in action["inputs"]],
            native / "post_route.odb",
            native / "post_route.v",
        ],
        parent=handoff["source_run_id"],
        objective=Path(frame["objective"]),
        seconds=7200,
        cpu=8,
        memory_gib=8 if design == "gcd" else 16,
    )
    jobs.log(record, native / "optimization.log")
    method = {
        "kind": identity["kind"],
        "repetition_method": str(experiment / "repetition-method.json"),
        "optimization_run_id": record["run"]["run_id"],
    }
    checkpoint(
        experiment,
        design_id=design,
        odb=native / "post_route.odb",
        producer=record["run"]["run_id"],
        objective=Path(frame["objective"]),
        native_method=method,
        pdk=Path(saved["pdk"]),
    )
    repeated = finish(deployment, experiment)
    write(experiment / "result.json", repeated)
    delta = compare(frame, repeated)
    write(experiment / "comparison-to-original.json", delta)
    write(
        experiment / "status.json",
        {
            "status": "succeeded",
            "constraint_violations": delta["constraint_violations"],
            "adopted": False,
        },
    )
    return repeated


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--result", type=Path, required=True)
    p.add_argument("--key", required=True)
    a = p.parse_args()
    repeat(Deployment(a.config), a.result, a.key)


if __name__ == "__main__":
    main()
