"""Collect finite, cited native-stage evidence for existing routed results."""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path
from typing import Any

from chip_evolve.comparisons import professional_facts
from chip_evolve.config import Deployment, read, write
from chip_evolve.jobs import Jobs, digest

STAGES = (
    "pre_repair",
    "post_repair_design",
    "post_repair_power",
    "post_placement",
    "post_route",
)


def stage_metrics(log: str) -> list[dict[str, Any]]:
    found: dict[str, dict[str, float]] = {}
    for stage, name, raw in re.findall(
        r"GOALEVOLVE_CHECKPOINT_METRIC (\w+) (tns_abs_ns|wns_abs_ns) ([^\s]+)",
        log,
    ):
        found.setdefault(stage, {})[name] = float(raw)
    if any(
        stage not in found or set(found[stage]) != {"tns_abs_ns", "wns_abs_ns"}
        for stage in STAGES
    ):
        raise ValueError("Native stage evidence is incomplete")
    # Original markers say 'abs' but emit signed OpenSTA values. Preserve the
    # measured signs; only the native parser/score uses absolute TNS.
    return [
        {
            "stage": stage,
            "setup_tns_ns": found[stage]["tns_abs_ns"],
            "setup_ws_ns": found[stage]["wns_abs_ns"],
        }
        for stage in STAGES
    ]


def collect(deployment: Deployment, result_path: Path, output: Path) -> dict[str, Any]:
    frame = read(result_path)
    producer = frame["qualification"]["producer_run_id"]
    jobs = Jobs(deployment, frame["design_id"], output)
    run = jobs.client.run(producer)
    if run["design_id"] != frame["design_id"] or run["status"] != "succeeded":
        raise ValueError("Native evidence belongs to another design or failed producer")
    output.mkdir(parents=True, exist_ok=False)
    record = {"run": run, "artifacts": jobs.client.artifacts(producer)}
    artifact = jobs.materialize(record, "data_snapshot", output / "native-evidence.zip")
    with zipfile.ZipFile(output / "native-evidence.zip") as bundle:
        names = [
            name for name in bundle.namelist() if Path(name).name == "evaluation.log"
        ]
        if len(names) != 1:
            raise ValueError("Choose the original professional evaluation log")
        member = names[0]
        (output / "native.log").write_bytes(bundle.read(member))
    stages = stage_metrics((output / "native.log").read_text())
    parent = frame["native_method"].get("selected_checkpoint") or frame[
        "native_method"
    ].get("parent")
    if (
        parent
        and abs(abs(stages[-1]["setup_tns_ns"]) - parent["metrics"]["tns_abs_ns"])
        > 1e-6
    ):
        raise ValueError(
            "Native stage units/identity disagree with original selected-parent metrics"
        )
    stages.append(
        {
            "stage": "final_drt_rcx",
            "setup_tns_ns": frame["metrics"]["finish__timing__setup__tns"],
            "setup_ws_ns": frame["metrics"]["finish__timing__setup__ws"],
        }
    )
    receipt = {
        "result": str(result_path.resolve()),
        "facts": professional_facts(frame),
        "native_checkpoint_sha256": frame["qualification"]["input_odb_sha256"],
        "native_producer_run_id": producer,
        "stages": stages,
        "earliest_observed_negative_stage": next(
            (s["stage"] for s in stages if s["setup_tns_ns"] < 0), None
        ),
        "evidence": {
            "run_id": producer,
            "artifact_id": artifact["artifact_id"],
            "sha256": artifact["sha256"],
            "archive_member": member,
            "member_sha256": digest(output / "native.log"),
        },
        "limitations": [
            "Native estimates and final extracted parasitics are different analysis conditions; stage observations alone do not prove a unique parameter cause.",
            "No new routing or optimization is performed by this collector.",
        ],
    }
    write(output / "stage-evidence.json", receipt)
    published = jobs.command(
        "cited-stage-facts",
        ["/usr/bin/sha256sum", str(output / "native.log")],
        capture=[output / "native.log", output / "stage-evidence.json"],
        analysis_parent=frame["run_id"],
        seconds=120,
        cpu=1,
        memory_gib=1,
        extra_paths=["query-data/0/native.log", "query-data/1/stage-evidence.json"],
    )
    receipt["scoped_evidence_run_id"] = published["run"]["run_id"]
    receipt["scoped_artifacts"] = [
        a
        for a in published["artifacts"]
        if a["store_key"].endswith(("native.log", "stage-evidence.json"))
    ]
    write(output / "stage-evidence.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    value = collect(Deployment(args.config), args.result, args.output)
    print(
        {
            "evidence": str(args.output / "stage-evidence.json"),
            "first_negative_stage": value["earliest_observed_negative_stage"],
        }
    )


if __name__ == "__main__":
    main()
