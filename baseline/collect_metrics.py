#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
from typing import Any

from flow_paths import resolve_flow_path


def load_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    json_path = resolve_flow_path(path)
    if not json_path.exists():
        return {}
    with json_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_snapshot(path: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with resolve_flow_path(path).open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            rows[row["inst"]] = row
    return rows


def displacement_metrics(
    before: dict[str, dict[str, str]], after: dict[str, dict[str, str]]
) -> dict[str, Any]:
    movable = 0
    moved = 0
    total_disp = 0.0
    total_abs_dx = 0.0
    total_abs_dy = 0.0
    max_disp = 0.0
    unmatched_before: list[str] = []
    unmatched_after = sorted(set(after) - set(before))

    for name, before_row in before.items():
        if name not in after:
            unmatched_before.append(name)
            continue
        if before_row["is_fixed"] == "1":
            continue

        after_row = after[name]
        before_x = float(before_row["x"])
        before_y = float(before_row["y"])
        after_x = float(after_row["x"])
        after_y = float(after_row["y"])
        dx = after_x - before_x
        dy = after_y - before_y
        disp = math.hypot(dx, dy)

        movable += 1
        total_disp += disp
        total_abs_dx += abs(dx)
        total_abs_dy += abs(dy)
        max_disp = max(max_disp, disp)
        if dx != 0.0 or dy != 0.0:
            moved += 1

    average_disp = total_disp / movable if movable else 0.0
    average_abs_dx = total_abs_dx / movable if movable else 0.0
    average_abs_dy = total_abs_dy / movable if movable else 0.0

    return {
        "movable_instance_count": movable,
        "moved_instance_count": moved,
        "average_displacement_dbu": average_disp,
        "max_displacement_dbu": max_disp,
        "average_abs_dx_dbu": average_abs_dx,
        "average_abs_dy_dbu": average_abs_dy,
        "unmatched_before_instances": unmatched_before,
        "unmatched_after_instances": unmatched_after,
    }


def add_micron_metrics(metrics: dict[str, Any], dbu_per_micron: float | None) -> None:
    if not dbu_per_micron:
        return
    for key in (
        "average_displacement_dbu",
        "max_displacement_dbu",
        "average_abs_dx_dbu",
        "average_abs_dy_dbu",
    ):
        if key in metrics:
            metrics[key.replace("_dbu", "_micron")] = metrics[key] / dbu_per_micron


def select_metrics(source: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for dst_key, src_key in mapping.items():
        if src_key in source:
            selected[dst_key] = source[src_key]
    return selected


def normalize_metric_keys(source: dict[str, Any]) -> dict[str, Any]:
    return {
        key.replace(":", "__").replace("/", "__"): value for key, value in source.items()
    }


def select_present(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: source[key] for key in keys if key in source}


def relative_artifact(path: str | None, report_dir: Path) -> str | None:
    if not path:
        return None
    artifact = resolve_flow_path(path)
    if not artifact.exists():
        return None
    return os.path.relpath(artifact, report_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine dpl_evolve baseline metrics.")
    parser.add_argument("--before", required=True, help="Before-placement TSV snapshot.")
    parser.add_argument("--after", required=True, help="After-placement TSV snapshot.")
    parser.add_argument("--run-summary", help="Strict-track summary JSON.")
    parser.add_argument("--post-metrics-summary", help="Post-legalization ODB metrics summary JSON.")
    parser.add_argument("--before-summary", help="Before snapshot summary JSON.")
    parser.add_argument("--after-summary", help="After snapshot summary JSON.")
    parser.add_argument("--manifest", help="Run manifest JSON.")
    parser.add_argument("--bridge-manifest", help="External legalizer bridge manifest JSON.")
    parser.add_argument("--detailed-placement-report", help="Detailed placement JSON report.")
    parser.add_argument("--orfs-metrics", help="ORFS stage metrics JSON.")
    parser.add_argument(
        "--orfs-metadata",
        help="Placement-only normalized metadata.json derived from 3_5_place_dp.json.",
    )
    parser.add_argument("--runtime-seconds", type=float, help="Wall-clock runtime for the run.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    args = parser.parse_args()

    before = load_snapshot(args.before)
    after = load_snapshot(args.after)
    run_summary = load_json(args.run_summary)
    post_metrics_summary = load_json(args.post_metrics_summary)
    before_summary = load_json(args.before_summary)
    after_summary = load_json(args.after_summary)
    manifest = load_json(args.manifest)
    bridge_manifest = load_json(args.bridge_manifest)
    dp_report = load_json(args.detailed_placement_report)
    orfs_metrics = load_json(args.orfs_metrics)
    orfs_metadata = load_json(args.orfs_metadata)
    merged_stage_metrics = normalize_metric_keys(orfs_metrics)
    merged_stage_metrics.update(orfs_metadata)
    output = resolve_flow_path(args.output)
    report_dir = output.parent

    dbu_per_micron = None
    for source in (run_summary, post_metrics_summary, before_summary, after_summary):
        if "dbu_per_micron" in source:
            dbu_per_micron = float(source["dbu_per_micron"])
            break

    displacement = displacement_metrics(before, after)
    add_micron_metrics(displacement, dbu_per_micron)

    hpwl_before = None
    hpwl_after = None
    hpwl_delta = None
    if "hpwl_before_dbu" in run_summary and "hpwl_after_dbu" in run_summary:
        hpwl_before = run_summary["hpwl_before_dbu"]
        hpwl_after = run_summary["hpwl_after_dbu"]
        hpwl_delta = run_summary.get("hpwl_delta_dbu", hpwl_after - hpwl_before)
    elif "hpwl_proxy_dbu" in before_summary and "hpwl_after_dbu" in run_summary:
        hpwl_before = before_summary["hpwl_proxy_dbu"]
        hpwl_after = run_summary["hpwl_after_dbu"]
        hpwl_delta = hpwl_after - hpwl_before
    elif "hpwl_proxy_dbu" in before_summary and "hpwl_proxy_dbu" in after_summary:
        hpwl_before = before_summary["hpwl_proxy_dbu"]
        hpwl_after = after_summary["hpwl_proxy_dbu"]
        hpwl_delta = hpwl_after - hpwl_before

    payload: dict[str, Any] = {
        "manifest": manifest,
        "runtime_seconds": args.runtime_seconds,
        "dbu_per_micron": dbu_per_micron,
        "displacement": displacement,
    }

    legalization = select_present(
        run_summary,
        (
            "status",
            "track",
            "legalizer_mode",
            "place_command",
            "padding_command",
            "use_negotiation",
            "use_abacus",
            "balance_rows",
            "enable_dpo",
        ),
    )
    if legalization:
        payload["legalization"] = legalization

    metrics_stage = {
        "elapsed_seconds": merged_stage_metrics.get("detailedplace__elapsed_seconds"),
        "cpu_total_seconds": merged_stage_metrics.get("detailedplace__cpu__total"),
        "peak_memory_kb": merged_stage_metrics.get("detailedplace__mem__peak"),
        "warning_count": merged_stage_metrics.get("detailedplace__flow__warnings__count"),
        "error_count": merged_stage_metrics.get("detailedplace__flow__errors__count"),
        "warning_type_count": merged_stage_metrics.get("detailedplace__flow__warnings__type_count"),
    }
    metrics_stage = {key: value for key, value in metrics_stage.items() if value is not None}
    if metrics_stage:
        payload["metrics_stage"] = metrics_stage

    if hpwl_before is not None:
        payload["hpwl_proxy"] = {
            "before_dbu": hpwl_before,
            "after_dbu": hpwl_after,
            "delta_dbu": hpwl_delta,
        }
        if dbu_per_micron:
            payload["hpwl_proxy"]["before_micron"] = hpwl_before / dbu_per_micron
            payload["hpwl_proxy"]["after_micron"] = hpwl_after / dbu_per_micron
            payload["hpwl_proxy"]["delta_micron"] = hpwl_delta / dbu_per_micron

    payload["timing_metrics"] = select_metrics(
        merged_stage_metrics,
        {
            "setup_tns": "detailedplace__timing__setup__tns",
            "hold_tns": "detailedplace__timing__hold__tns",
            "setup_ws": "detailedplace__timing__setup__ws",
            "hold_ws": "detailedplace__timing__hold__ws",
            "fmax": "detailedplace__timing__fmax",
            "setup_violation_count": "detailedplace__timing__drv__setup_violation_count",
            "hold_violation_count": "detailedplace__timing__drv__hold_violation_count",
        },
    )
    payload["power_metrics"] = select_metrics(
        merged_stage_metrics,
        {
            "total": "detailedplace__power__total",
            "internal": "detailedplace__power__internal__total",
            "switching": "detailedplace__power__switching__total",
            "leakage": "detailedplace__power__leakage__total",
        },
    )
    payload["design_metrics"] = select_metrics(
        merged_stage_metrics,
        {
            "instance_count": "detailedplace__design__instance__count",
            "instance_area": "detailedplace__design__instance__area",
            "core_area": "detailedplace__design__core__area",
            "die_area": "detailedplace__design__die__area",
            "utilization": "detailedplace__design__instance__utilization",
            "estimated_wirelength": "detailedplace__route__wirelength__estimated",
        },
    )
    payload["legality"] = {
        "placement_violations": post_metrics_summary.get(
            "placement_violations",
            run_summary.get("placement_violations"),
        ),
        "check_report": post_metrics_summary.get("check_report"),
    }

    if bridge_manifest:
        dreamplace_bridge = select_present(
            bridge_manifest,
            (
                "status",
                "dreamplace_root",
                "python_executable",
                "greedy_legality_check_passed",
                "legality_check_passed",
            ),
        )
        if not dreamplace_bridge:
            dreamplace_bridge = bridge_manifest
        payload["dreamplace_bridge"] = dreamplace_bridge

    supporting_files = {
        "before_snapshot_tsv": relative_artifact(args.before, report_dir),
        "after_snapshot_tsv": relative_artifact(args.after, report_dir),
        "legalize_summary_json": relative_artifact(args.run_summary, report_dir),
        "post_metrics_summary_json": relative_artifact(args.post_metrics_summary, report_dir),
        "before_summary_json": relative_artifact(args.before_summary, report_dir),
        "after_summary_json": relative_artifact(args.after_summary, report_dir),
        "detailed_placement_report_json": relative_artifact(args.detailed_placement_report, report_dir),
        "dreamplace_manifest_json": relative_artifact(args.bridge_manifest, report_dir),
        "raw_metrics_json": relative_artifact(args.orfs_metrics, report_dir),
        "normalized_metadata_json": relative_artifact(args.orfs_metadata, report_dir),
    }
    supporting_files = {
        key: value for key, value in supporting_files.items() if value is not None
    }
    check_report = payload["legality"].get("check_report")
    check_report_rel = relative_artifact(check_report, report_dir)
    if check_report_rel is not None:
        supporting_files["check_placement_report_json"] = check_report_rel
    if supporting_files:
        payload["supporting_files"] = supporting_files

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
