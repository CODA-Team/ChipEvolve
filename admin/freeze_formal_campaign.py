"""Freeze explicit preflight inputs and budgets before any new EDA work."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from eda_toolkits.objectives import require_same_conditions

from chip_evolve.candidates import result_frame
from chip_evolve.config import Deployment, read, write
from chip_evolve.environment import check_environment, reference
from chip_evolve.selection import checked_validation
from chip_evolve.validation import query_facts

SCHEMA = "chip-evolve.preflight.v1"


def content_id(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            {k: v for k, v in value.items() if k != "campaign_id"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def freeze(config: Path, spec: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError("A frozen campaign cannot be overwritten")
    deployment, request = Deployment(config), read(spec)
    if request["purpose"] != "fixed_method_integration_preflight":
        raise ValueError(
            "This slice freezes fixed-method preflight, not a formal search study"
        )
    rows = request["designs"]
    if len(rows) < 2 or len({r["design_id"] for r in rows}) != len(rows):
        raise ValueError("Need at least two distinct explicitly qualified designs")
    frozen = []
    for row in rows:
        design = row["design_id"]
        reference_path, selected_path = (
            Path(row["reference"]),
            Path(row["selected_source"]),
        )
        baseline, selected = result_frame(reference_path), result_frame(selected_path)
        if baseline["design_id"] != design or selected["design_id"] != design:
            raise ValueError("Preflight source belongs to another design")
        require_same_conditions(baseline, selected)
        if baseline["objective_id"] != selected["objective_id"]:
            raise ValueError("Preflight sources have different business objectives")
        if not row["selection_reason"].strip():
            raise ValueError("Codex must explicitly explain the selected source")
        environment = Path(deployment.value["qualified_environments"][design])
        check_environment(
            deployment, environment, design, "flow", reference_path, "source"
        )
        query_facts(deployment, baseline)
        query_facts(deployment, selected)
        candidates = []
        alternatives = []
        for extra in row.get("additional_sources", []):
            path, proof = Path(extra["result"]), Path(extra["validation"])
            frame = result_frame(path)
            require_same_conditions(baseline, frame)
            if (
                frame["design_id"] != design
                or frame["objective_id"] != baseline["objective_id"]
            ):
                raise ValueError("Alternative source has a different design/objective")
            checked_validation(path, proof)
            query_facts(deployment, frame)
            alternatives.append(
                {"result": reference(path), "validation": reference(proof)}
            )
        if not row["flow_candidates"]:
            raise ValueError("Preflight must preserve the completed Flow candidate set")
        for path in map(Path, row["flow_candidates"]):
            candidate = result_frame(path)
            require_same_conditions(baseline, candidate)
            if candidate["design_id"] != design:
                raise ValueError("Candidate belongs to another design")
            if candidate["objective_id"] != baseline["objective_id"]:
                raise ValueError("Candidate has a different business objective")
            candidates.append(reference(path))
            query_facts(deployment, candidate)
        if reference(selected_path)["sha256"] not in {
            reference(reference_path)["sha256"],
            *[r["sha256"] for r in candidates],
            *[r["result"]["sha256"] for r in alternatives],
        }:
            raise ValueError(
                "Selected source is not one of the declared completed inputs"
            )
        frozen.append(
            {
                **row,
                "reference": reference(reference_path),
                "selected_source": reference(selected_path),
                "environment": reference(environment),
                "flow_candidates": candidates,
                "additional_sources": alternatives,
                "objective": reference(Path(baseline["objective"])),
                "objective_id": baseline["objective_id"],
                "condition_id": baseline["condition_id"],
            }
        )
    steps = request["steps"]
    if not steps or len({s["key"] for s in steps}) != len(steps):
        raise ValueError("Need distinct explicit preflight steps")
    prior = {"reference", "selected_source"}
    for step in steps:
        if step["input"] not in prior:
            raise ValueError("Step source must be an explicit earlier result")
        prior.add(step["key"])
        if step["seconds"] <= 0 or step["operation"] not in {"replay", "framework"}:
            raise ValueError(
                "Fixed-method preflight needs positive budgets and explicit methods"
            )
        if step["capability"] not in {"dpl", "goal"}:
            raise ValueError(
                "Preflight dispatch is limited to the declared fixed Code methods"
            )
        if step["operation"] == "framework" and step["capability"] != "dpl":
            raise ValueError("Framework is an original DPL operation only")
    value = {
        "schema_version": SCHEMA,
        "purpose": request["purpose"],
        "experiment_prefix": request["experiment_prefix"],
        "config": reference(config),
        "request": reference(spec),
        "designs": frozen,
        "steps": steps,
        "interpretation": "Reuses completed Flow candidates; reruns fixed professional methods. No new source evolution, equal-budget team superiority or statistical claim.",
        "decision_owner": "Codex",
        "full_formal_campaign_authorized_by_this_manifest": False,
    }
    value["campaign_id"] = content_id(value)
    write(output, value)
    return value


def checked(path: Path) -> dict[str, Any]:
    from chip_evolve.jobs import digest

    value = read(path)
    if value["schema_version"] != SCHEMA or value["campaign_id"] != content_id(value):
        raise ValueError("Frozen campaign content changed")
    refs = [value["config"], value["request"]]
    for row in value["designs"]:
        refs += [
            row[k] for k in ("reference", "selected_source", "environment", "objective")
        ]
        refs += row["flow_candidates"]
        for extra in row.get("additional_sources", []):
            refs += [extra["result"], extra["validation"]]
    for row in refs:
        if digest(Path(row["path"])) != row["sha256"]:
            raise ValueError("Frozen campaign input changed: " + row["path"])
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = freeze(args.config.resolve(), args.spec.resolve(), args.output.resolve())
    print(
        json.dumps({"campaign_id": value["campaign_id"], "manifest": str(args.output)})
    )


if __name__ == "__main__":
    main()
