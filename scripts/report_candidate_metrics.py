#!/usr/bin/env python3
"""Summarize one candidate run from canonical evaluator artifacts.

This script exists so Students do not need to manually inspect nested
`metrics.json`, `legalize_summary.json`, and DPL logs just to report the
canonical final HPWL/runtime/stage deltas and a few route-specific counters.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize one candidate run from canonical evaluator artifacts."
    )
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument(
        "--limit-log-counters",
        type=int,
        default=24,
        help="Maximum number of log-derived counters/summary lines to keep.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def canonical_hpwl(data: dict[str, Any]) -> dict[str, Any]:
    hpwl = data.get("hpwl")
    if isinstance(hpwl, dict) and hpwl.get("source") != "cell_bbox_proxy":
        return hpwl
    hpwl = data.get("hpwl_openroad_log")
    if isinstance(hpwl, dict):
        return hpwl
    return {}


def fmt_float(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "missing"
    return f"{value:.{digits}f}"


def fmt_pct(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "missing"
    return f"{value:+.{digits}f}%"


def last_float(pattern: str, text: str) -> float | None:
    matches = re.findall(pattern, text, flags=re.MULTILINE)
    if not matches:
        return None
    return as_float(matches[-1])


def first_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return as_float(match.group(1)) if match else None


def resolve_path(base_dir: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    anchor = infer_flow_root(base_dir)
    if anchor is not None and path.parts and path.parts[0] in {
        "reports",
        "results",
        "logs",
    }:
        return anchor / path
    return base_dir / path


def infer_flow_root(base_dir: Path) -> Path | None:
    parts = base_dir.parts
    if "reports" in parts:
        idx = parts.index("reports")
        if idx > 0:
            return Path(*parts[:idx])
    if "logs" in parts:
        idx = parts.index("logs")
        if idx > 0:
            return Path(*parts[:idx])
    if "results" in parts:
        idx = parts.index("results")
        if idx > 0:
            return Path(*parts[:idx])
    return None


def hpwl_stage_summary(
    metrics_path: Path, data: dict[str, Any], hpwl: dict[str, Any]
) -> dict[str, float | None]:
    stages = data.get("hpwl_stages")
    if not isinstance(stages, dict):
        stages = {}

    hpwlg = as_float(stages.get("global_micron")) or as_float(hpwl.get("before_micron"))
    hpwl_legalized = as_float(stages.get("legalized_micron"))
    hpwl_after_improve = as_float(stages.get("after_improve_micron"))
    hpwl_final = as_float(stages.get("final_micron")) or as_float(hpwl.get("after_micron"))

    log_path = resolve_path(metrics_path.parent, stages.get("log") or hpwl.get("log"))
    if log_path is not None and log_path.is_file():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        hpwlg = hpwlg or first_float(r"^original HPWL\s+([0-9.+-eE]+)\s+u", text)
        hpwlg = hpwlg or first_float(r"^Original HPWL\s+([0-9.+-eE]+)\s+u", text)
        hpwl_legalized = hpwl_legalized or last_float(
            r"^legalized HPWL\s+([0-9.+-eE]+)\s+u", text
        )
        hpwl_after_improve = hpwl_after_improve or last_float(
            r"^Final HPWL\s+([0-9.+-eE]+)\s+u", text
        )
        hpwl_final = hpwl_final or last_float(
            r"^\[INFO DPL-0022\]\s+HPWL after\s+([0-9.+-eE]+)\s+u", text
        )

    def pct(delta: float | None, base: float | None) -> float | None:
        if delta is None or base in (None, 0.0):
            return None
        return delta / base * 100.0

    delta_lg = (
        None if hpwlg is None or hpwl_legalized is None else hpwl_legalized - hpwlg
    )
    delta_ip = (
        None
        if hpwl_legalized is None or hpwl_after_improve is None
        else hpwl_after_improve - hpwl_legalized
    )
    delta_final = (
        None if hpwlg is None or hpwl_final is None else hpwl_final - hpwlg
    )
    return {
        "global_micron": hpwlg,
        "legalized_micron": hpwl_legalized,
        "after_improve_micron": hpwl_after_improve,
        "final_micron": hpwl_final,
        "delta_legalization_micron": delta_lg,
        "delta_improve_micron": delta_ip,
        "delta_final_micron": delta_final,
        "delta_legalization_percent": pct(delta_lg, hpwlg),
        "delta_improve_percent": pct(delta_ip, hpwlg),
        "delta_final_percent": pct(delta_final, hpwlg),
    }


def summarize_log_counters(log_path: Path | None, limit: int) -> list[str]:
    if log_path is None or not log_path.is_file():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if "[INFO DPL-" not in line:
            continue
        lower = line.lower()
        if not any(
            token in lower
            for token in (
                "frontier",
                "guided",
                "probe",
                "exact-search",
                "rollback",
                "transaction",
                "pass summary",
                "handoff",
                "continuity",
                "quality accepts",
                "low-residual",
            )
        ):
            continue
        lines.append(line)
    if len(lines) > limit:
        return lines[-limit:]
    return lines


def build_summary(metrics_path: Path, limit_log_counters: int) -> dict[str, Any]:
    data = load_json(metrics_path)
    if not data:
        raise SystemExit(f"[ERROR] failed to parse metrics json: {metrics_path}")

    hpwl = canonical_hpwl(data)
    disp = data.get("displacement", {})
    legality = data.get("legality", {})
    manifest = data.get("manifest", {})
    legalize = data.get("legalization", {})
    legalize_summary_path = metrics_path.parent / "legalize_summary.json"
    post_metrics_summary_path = metrics_path.parent / "post_metrics_summary.json"
    legalize_summary = load_json(legalize_summary_path) if legalize_summary_path.is_file() else None
    post_metrics_summary = (
        load_json(post_metrics_summary_path) if post_metrics_summary_path.is_file() else None
    )

    stages = hpwl_stage_summary(metrics_path, data, hpwl)
    log_path = resolve_path(metrics_path.parent, hpwl.get("log"))
    counter_lines = summarize_log_counters(log_path, limit_log_counters)

    violations = str(legality.get("placement_violations", ""))
    legality_status = "clean" if violations.strip() == "" else violations

    summary = {
        "metrics_path": str(metrics_path),
        "run_tag": manifest.get("run_tag", metrics_path.parent.name),
        "line": manifest.get("line"),
        "engine": manifest.get("engine"),
        "case_report_dir": str(metrics_path.parent),
        "canonical": {
            "final_hpwl_micron": as_float(hpwl.get("after_micron")),
            "hpwl_before_micron": as_float(hpwl.get("before_micron")),
            "hpwl_delta_micron": as_float(hpwl.get("delta_micron")),
            "hpwl_delta_percent": as_float(hpwl.get("delta_percent")),
            "runtime_seconds": as_float(data.get("runtime_seconds")),
            "avg_displacement_micron": as_float(disp.get("average_displacement_micron")),
            "max_displacement_micron": as_float(disp.get("max_displacement_micron")),
            "legality": legality_status,
        },
        "stages": stages,
        "paths": {
            "metrics_json": str(metrics_path),
            "log": str(log_path) if log_path else None,
            "legalize_summary": str(legalize_summary_path) if legalize_summary_path.is_file() else None,
            "post_metrics_summary": str(post_metrics_summary_path)
            if post_metrics_summary_path.is_file()
            else None,
            "metrics_report": (
                str(resolve_path(metrics_path.parent, post_metrics_summary.get("metrics_report")))
                if isinstance(post_metrics_summary, dict)
                else None
            ),
            "check_report": (
                str(resolve_path(metrics_path.parent, legality.get("check_report")))
                if isinstance(legality, dict)
                else None
            ),
        },
        "commands": {
            "place_command": legalize.get("place_command"),
            "improve_command": legalize.get("improve_command"),
            "optimize_command": legalize.get("optimize_command"),
            "stage_sequence": legalize.get("stage_sequence"),
        },
        "log_counter_lines": counter_lines,
        "status": data.get("status"),
        "legalize_exit_status": data.get("legalize_exit_status"),
        "legalize_timeout_seconds": data.get("legalize_timeout_seconds"),
        "legalizer_mode": legalize.get("legalizer_mode"),
        "legalize_summary_status": (
            legalize_summary.get("status") if isinstance(legalize_summary, dict) else None
        ),
    }
    return summary


def render_markdown(summary: dict[str, Any]) -> str:
    canonical = summary["canonical"]
    stages = summary["stages"]
    paths = summary["paths"]
    lines = [
        "# Candidate Metrics Summary",
        "",
        f"- run_tag: `{summary.get('run_tag')}`",
        f"- line: `{summary.get('line')}`",
        f"- engine: `{summary.get('engine')}`",
        f"- legality: `{canonical.get('legality')}`",
        f"- final_hpwl_micron: `{fmt_float(canonical.get('final_hpwl_micron'), 3)}`",
        f"- hpwl_delta_micron: `{fmt_float(canonical.get('hpwl_delta_micron'), 3)}`",
        f"- hpwl_delta_percent: `{fmt_pct(canonical.get('hpwl_delta_percent'), 3)}`",
        f"- runtime_seconds: `{fmt_float(canonical.get('runtime_seconds'), 3)}`",
        f"- avg_displacement_micron: `{fmt_float(canonical.get('avg_displacement_micron'), 4)}`",
        f"- max_displacement_micron: `{fmt_float(canonical.get('max_displacement_micron'), 4)}`",
        "",
        "## Stage Metrics",
        "",
        f"- HPWLg: `{fmt_float(stages.get('global_micron'), 3)}`",
        f"- HPWLlg: `{fmt_float(stages.get('legalized_micron'), 3)}`",
        f"- HPWLimprove: `{fmt_float(stages.get('after_improve_micron'), 3)}`",
        f"- HPWLfinal: `{fmt_float(stages.get('final_micron'), 3)}`",
        f"- delta_HPWL_legalization_micron: `{fmt_float(stages.get('delta_legalization_micron'), 3)}`",
        f"- delta_HPWL_improve_micron: `{fmt_float(stages.get('delta_improve_micron'), 3)}`",
        f"- delta_HPWL_final_micron: `{fmt_float(stages.get('delta_final_micron'), 3)}`",
        f"- delta_HPWL_legalization_percent: `{fmt_pct(stages.get('delta_legalization_percent'), 3)}`",
        f"- delta_HPWL_improve_percent: `{fmt_pct(stages.get('delta_improve_percent'), 3)}`",
        f"- delta_HPWL_final_percent: `{fmt_pct(stages.get('delta_final_percent'), 3)}`",
        "",
        "## Canonical Paths",
        "",
        f"- metrics_json: `{paths.get('metrics_json')}`",
        f"- dpl_log: `{paths.get('log')}`",
        f"- legalize_summary: `{paths.get('legalize_summary')}`",
        f"- post_metrics_summary: `{paths.get('post_metrics_summary')}`",
        f"- metrics_report: `{paths.get('metrics_report')}`",
        f"- check_report: `{paths.get('check_report')}`",
    ]
    counter_lines = summary.get("log_counter_lines") or []
    if counter_lines:
        lines.extend(["", "## Log Counter Lines", ""])
        for line in counter_lines:
            lines.append(f"- `{line}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    metrics_path = args.metrics.resolve()
    if not metrics_path.is_file():
        print(f"[ERROR] metrics json not found: {metrics_path}", file=sys.stderr)
        return 2

    summary = build_summary(metrics_path, args.limit_log_counters)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(summary), encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
