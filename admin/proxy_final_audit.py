"""Bounded physical controls through existing business/EF/data entry points."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Any

from chip_evolve.comparisons import compare
from chip_evolve.config import Deployment, business_lock, read, write
from chip_evolve.delivery import checkpoint, finish
from chip_evolve.jobs import digest
from chip_evolve.physical import baseline
from chip_evolve.professional import dpl_producer
from chip_evolve.validation import query_facts


def matched_inputs(before: dict, after: dict, declared: set[str]) -> list[str]:
    """A claimed control must not silently change an undeclared input."""
    changed = sorted(
        k for k in before.keys() | after.keys() if before.get(k) != after.get(k)
    )
    unexpected = set(changed) - declared
    if unexpected:
        raise ValueError("Undeclared control changes: " + ", ".join(sorted(unexpected)))
    if not changed:
        raise ValueError("Control has no actual input change")
    return changed


def rank_reversals(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """List observed HPWL/power disagreements, without making a causal claim."""
    pairs = []
    for first in rows:
        for second in rows:
            if (
                first["hpwl_um"] < second["hpwl_um"]
                and first["power_w"] > second["power_w"]
            ):
                pairs.append(
                    {"lower_hpwl": first["name"], "lower_final_power": second["name"]}
                )
    return pairs


def flow_deployment(
    deployment: Deployment, design_id: str, key: str, overrides: dict[str, str]
) -> Deployment:
    value = deepcopy(deployment.value)
    design = value["designs"][design_id]
    original = design.get("baseline_overrides", "")
    design["baseline_overrides"] = original + "".join(
        f"export {name} = {setting}\n" for name, setting in sorted(overrides.items())
    )
    path = deployment.path.parent / "controls" / (key + ".json")
    if path.exists() and read(path) != value:
        raise ValueError(
            "Control configuration was already frozen with different inputs"
        )
    write(path, value)
    return Deployment(path)


def flow_control(
    deployment: Deployment,
    reference: Path,
    key: str,
    overrides: dict[str, str],
    seconds: int,
) -> dict[str, Any]:
    frame = read(reference)
    controlled = flow_deployment(deployment, frame["design_id"], key, overrides)
    experiment = controlled.state / "experiments" / frame["design_id"] / key
    experiment.mkdir(parents=True, exist_ok=True)
    request = {
        "design": frame["design_id"],
        "capability": "orfs",
        "seconds": seconds,
        "source": str(reference),
        "reference_sha256": digest(reference),
        "declared_overrides": overrides,
        "deployment": str(controlled.path),
        "scope": "Fixed recipe control; no model search",
    }
    saved = experiment / "request.json"
    if saved.exists() and read(saved) != request:
        raise ValueError("A control cannot change its frozen request")
    write(saved, request)
    with business_lock(experiment):
        result = baseline(
            controlled,
            frame["design_id"],
            experiment,
            seconds,
            objective=Path(frame["objective"]),
        )
        write(experiment / "comparison.json", compare(frame, result))
        write(experiment / "sdk-query.json", query_facts(controlled, result))
        write(experiment / "status.json", {"status": "succeeded"})
    return result


def dpl_control(
    deployment: Deployment, reference: Path, native: Path, key: str, student: int
) -> dict[str, Any]:
    frame = read(reference)
    request = read(native / "request.json")
    design_id = frame["design_id"]
    design = deployment.design(design_id)
    tag = f"{native.name}_iter_01_student_{student:02d}_{design['nickname']}_{design['platform']}"
    placements = list(
        (native / "orfs/flow/results" / design["platform"] / design["nickname"]).glob(
            f"*/dpl_evolve_baseline/{tag}/legalized.odb"
        )
    )
    if len(placements) != 1 or request["design"] != design_id:
        raise ValueError("Choose the actual matching native Student placement")
    placement = placements[0]
    producer = dpl_producer(native / "operations", placement, tag)
    experiment = deployment.state / "experiments" / design_id / key
    experiment.mkdir(parents=True, exist_ok=True)
    receipt = {
        "design": design_id,
        "capability": "audit-dpl-delivery",
        "source": str(reference),
        "reference_sha256": digest(reference),
        "native": str(native),
        "student": student,
        "run_tag": tag,
        "producer": producer,
        "placement_sha256": digest(placement),
    }
    saved = experiment / "request.json"
    if saved.exists() and read(saved) != receipt:
        raise ValueError("DPL control changed its frozen native input")
    write(saved, receipt)
    with business_lock(experiment):
        delivered = experiment / "selected-placement.odb"
        delivered.write_bytes(placement.read_bytes())
        checkpoint(
            experiment,
            design_id=design_id,
            odb=delivered,
            producer=producer,
            objective=Path(frame["objective"]),
            source=reference,
            native_method={
                "kind": "native-Student-matched-delivery",
                **receipt,
                "native_search_restarted": False,
            },
        )
        result = finish(deployment, experiment)
        write(experiment / "comparison.json", compare(frame, result))
        write(experiment / "sdk-query.json", query_facts(deployment, result))
        write(experiment / "status.json", {"status": "succeeded"})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    flow = sub.add_parser("flow")
    flow.add_argument("--key", required=True)
    flow.add_argument("--override", action="append", required=True)
    flow.add_argument("--seconds", type=int, default=7200)
    dpl = sub.add_parser("dpl")
    dpl.add_argument("--key", required=True)
    dpl.add_argument("--native", type=Path, required=True)
    dpl.add_argument("--student", type=int, choices=[1, 2, 3], required=True)
    args = parser.parse_args()
    deployment = Deployment(args.config)
    try:
        if args.command == "flow":
            overrides = dict(item.split("=", 1) for item in args.override)
            result = flow_control(
                deployment, args.reference.resolve(), args.key, overrides, args.seconds
            )
        else:
            result = dpl_control(
                deployment,
                args.reference.resolve(),
                args.native.resolve(),
                args.key,
                args.student,
            )
    except Exception as error:
        experiment = (
            deployment.state
            / "experiments"
            / read(args.reference)["design_id"]
            / args.key
        )
        if experiment.exists():
            write(
                experiment / "status.json",
                {
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "detail": str(error),
                },
            )
        raise
    print(result["run_id"], result["metrics"])


if __name__ == "__main__":
    main()
