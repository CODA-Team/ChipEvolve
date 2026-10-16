"""Report all fixed-method preflight outcomes; never choose or adopt a winner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from admin.freeze_formal_campaign import checked
from chip_evolve.comparisons import compare, professional_facts
from chip_evolve.config import Deployment, read, write
from chip_evolve.environment import reference
from chip_evolve.validation import query_facts


def report(manifest: Path) -> dict[str, Any]:
    campaign = checked(manifest)
    deployment = Deployment(Path(campaign["config"]["path"]))
    designs = []
    for design in campaign["designs"]:
        name = design["design_id"]
        baseline, source = (
            read(design["reference"]["path"]),
            read(design["selected_source"]["path"]),
        )
        rows, complete = [], {}
        for step in campaign["steps"]:
            path = manifest.parent / "steps" / name / step["key"] / "receipt.json"
            row: dict[str, Any] = (
                read(path) if path.exists() else {"status": "not_started"}
            )
            attempts = sorted(path.parent.glob("attempt-*.json"))
            outcomes = [read(p) for p in attempts]
            value = {
                "step": step["key"],
                "status": row["status"],
                "receipt": str(path),
                "wall_seconds": row.get("wall_seconds"),
                "attempts": [str(p) for p in attempts],
                "attempt_outcomes": [
                    {key: a[key] for key in ("attempt", "status", "wall_seconds")}
                    for a in outcomes
                ],
                "completed_attempt_wall_seconds_sum": sum(
                    a["wall_seconds"] for a in outcomes
                ),
            }
            if row["status"] == "succeeded":
                result = Path(row["result"]["path"])
                if reference(result) != row["result"]:
                    raise ValueError("Preflight result changed after execution")
                frame = read(result)
                query_facts(deployment, frame)
                complete[step["key"]] = frame
                value.update(
                    result=row["result"],
                    facts=professional_facts(frame),
                    versus_reference=compare(baseline, frame),
                    versus_selected_source=compare(source, frame),
                )
            rows.append(value)
        interaction = None
        if all(k in complete for k in ("dpl-fixed", "goal-single", "goal-relay")):
            interaction = {
                "relay_versus_goal_alone": compare(
                    complete["goal-single"], complete["goal-relay"]
                ),
                "relay_versus_dpl_alone": compare(
                    complete["dpl-fixed"], complete["goal-relay"]
                ),
                "interpretation": "Matched fixed methods only. Local and combined changes do not establish a new-search team advantage.",
            }
        designs.append(
            {
                "design_id": name,
                "selected_source": design["selected_source"],
                "selection_reason": design["selection_reason"],
                "steps": rows,
                "interaction": interaction,
            }
        )
    states = [r["status"] for d in designs for r in d["steps"]]
    return {
        "campaign_id": campaign["campaign_id"],
        "purpose": campaign["purpose"],
        "designs": designs,
        "execution_gate": "passed"
        if all(s == "succeeded" for s in states)
        else "failed"
        if "failed" in states
        else "incomplete",
        "formal_study_ready": False,
        "new_source_search_executed": False,
        "limitations": [
            "Fixed-method integration preflight, not an equal-budget optimization study.",
            "No automatic adoption. Validation and Codex decisions are separate.",
            "Two qualified designs; picorv32 remains excluded.",
            "All failed/pending/not-started steps and attempts remain in the report.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = report(args.manifest.resolve())
    write(args.output, value)
    print(
        json.dumps(
            {
                "report": str(args.output),
                "execution_gate": value["execution_gate"],
                "formal_study_ready": False,
            }
        )
    )


if __name__ == "__main__":
    main()
