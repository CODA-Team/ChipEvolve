"""Paper tables for two independent, matched fixed-strategy executions."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import mean
from typing import Any

from chip_evolve.comparisons import compare
from chip_evolve.config import read, write

IDENTITY = (
    "binary_sha256",
    "original_script_sha256",
    "input_hashes",
    "condition_id",
    "objective_id",
)


def summarize(reference: Path, results: list[Path]) -> dict[str, Any]:
    if len(results) != 2 or len({p.resolve() for p in results}) != 2:
        raise ValueError("Exactly two distinct full optimization executions required")
    frames = [read(p) for p in results]
    methods = [read(p.parent / "repetition-method.json") for p in results]
    if any(m.get("kind") != "independent-fixed-strategy-optimization" for m in methods):
        raise ValueError("A routing replay is not an optimization repetition")
    if any(methods[0][key] != methods[1][key] for key in IDENTITY):
        raise ValueError("Two executions must use identical inputs, code and strategy")
    run_ids = [x["native_method"]["optimization_run_id"] for x in frames]
    if len(set(run_ids)) != 2 or len({x["run_id"] for x in frames}) != 2:
        raise ValueError(
            "Two independent EF optimization and measurement runs required"
        )
    baseline = read(reference)
    comparisons = [compare(baseline, f) for f in frames]
    causes = []
    for i, (f, delta) in enumerate(zip(frames, comparisons), 1):
        problems = list(delta["constraint_violations"])
        for metric in ("finish__power__total", "finish__design__instance__area"):
            if f["metrics"][metric] > baseline["metrics"][metric]:
                problems.append("worse_than_baseline:" + metric)
        if problems:
            causes.append({"trial": i, "problems": problems})
    common = set.intersection(*(set(f["metrics"]) for f in frames))
    values = {
        k: {
            "trial_1": frames[0]["metrics"][k],
            "trial_2": frames[1]["metrics"][k],
            "mean": mean(f["metrics"][k] for f in frames),
        }
        for k in sorted(common)
        if all(isinstance(f["metrics"][k], (int, float)) for f in frames)
    }
    return {
        "scope": methods[0]["scope"],
        "reference": str(reference.resolve()),
        "results": [str(p.resolve()) for p in results],
        "optimization_run_ids": run_ids,
        "qualified_ppa_pair": not causes,
        "functional_adoption": "Separate exact-artifact proof required; PPA qualification is not functional proof.",
        "status": "qualified_ppa_pair"
        if not causes
        else "requires_cause_review_and_correction",
        "problems": causes,
        "metrics": values,
        "identity": {key: methods[0][key] for key in IDENTITY},
    }


def export(summary: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write(output / "two-trial-summary.json", summary)
    with (output / "two-trial-metrics.csv").open("w") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["metric", "trial_1", "trial_2", "mean", "qualified_ppa_pair"],
        )
        writer.writeheader()
        for metric, values in summary["metrics"].items():
            writer.writerow(
                {
                    "metric": metric,
                    **values,
                    "qualified_ppa_pair": summary["qualified_ppa_pair"],
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--result", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(summarize(args.reference, args.result), args.output)


if __name__ == "__main__":
    main()
