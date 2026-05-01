"""Metrics, baseline evidence, peer-learning, and artifact packets."""
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from runtime_paths import clean_subprocess_env
from scripts.case_registry import get_case
from scripts.teacher_loop.common import (
    CANONICAL_LINES,
    CandidateArtifacts,
    ChildRound,
    MetricSummary,
    iter_name,
)


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def canonical_hpwl(data: dict[str, Any]) -> dict[str, Any]:
    """Return only the OpenROAD/DPL pin-based HPWL metric.

    `hpwl_proxy` is a legacy cell-bbox proxy.  It is useful for debugging data
    extraction, but it must not drive Teacher decisions, baseline reuse, or
    candidate promotion.
    """
    hpwl = data.get("hpwl")
    if isinstance(hpwl, dict) and hpwl.get("source") != "cell_bbox_proxy":
        return hpwl
    hpwl = data.get("hpwl_openroad_log")
    if isinstance(hpwl, dict):
        return hpwl
    return {}


def hpwl_delta_percent(hpwl: dict[str, Any]) -> float | None:
    if hpwl.get("delta_percent") is not None:
        return float(hpwl["delta_percent"])
    before = hpwl.get("before_micron")
    delta = hpwl.get("delta_micron")
    if before in (None, 0) or delta is None:
        return None
    before_value = float(before)
    if before_value == 0.0:
        return None
    return float(delta) / before_value * 100.0


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _last_float(pattern: str, text: str) -> float | None:
    matches = re.findall(pattern, text, flags=re.MULTILINE)
    return _float_or_none(matches[-1]) if matches else None


def _first_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return _float_or_none(match.group(1)) if match else None


def hpwl_stage_metrics(metrics_path: Path, data: dict[str, Any], hpwl: dict[str, Any]) -> dict[str, float | None]:
    """Return stage-wise HPWL, backfilled from the DPL log for older metrics."""
    stages = data.get("hpwl_stages")
    if not isinstance(stages, dict):
        stages = {}

    hpwl_global = _float_or_none(stages.get("global_micron"))
    hpwl_legalized = _float_or_none(stages.get("legalized_micron"))
    hpwl_after_improve = _float_or_none(stages.get("after_improve_micron"))
    hpwl_final = _float_or_none(stages.get("final_micron"))

    log_value = stages.get("log") or hpwl.get("log")
    log_path = Path(str(log_value)) if log_value else None
    if log_path is not None and not log_path.is_absolute():
        log_path = metrics_path.parent / log_path
    if log_path is not None and log_path.is_file():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        hpwl_global = hpwl_global or _first_float(r"^original HPWL\s+([0-9.+-eE]+)\s+u", text)
        hpwl_global = hpwl_global or _first_float(r"^Original HPWL\s+([0-9.+-eE]+)\s+u", text)
        hpwl_legalized = hpwl_legalized or _last_float(r"^legalized HPWL\s+([0-9.+-eE]+)\s+u", text)
        hpwl_after_improve = hpwl_after_improve or _last_float(r"^Final HPWL\s+([0-9.+-eE]+)\s+u", text)
        hpwl_final = hpwl_final or _last_float(
            r"^\[INFO DPL-0022\]\s+HPWL after\s+([0-9.+-eE]+)\s+u", text
        )

    hpwl_global = hpwl_global if hpwl_global is not None else _float_or_none(hpwl.get("before_micron"))
    hpwl_final = hpwl_final if hpwl_final is not None else _float_or_none(hpwl.get("after_micron"))

    delta_legalization = (
        None if hpwl_global is None or hpwl_legalized is None else hpwl_legalized - hpwl_global
    )
    delta_improve = (
        None
        if hpwl_legalized is None or hpwl_after_improve is None
        else hpwl_after_improve - hpwl_legalized
    )
    delta_final = (
        None if hpwl_global is None or hpwl_final is None else hpwl_final - hpwl_global
    )

    def pct(delta: float | None) -> float | None:
        if delta is None or hpwl_global in (None, 0):
            return None
        return delta / hpwl_global * 100.0

    return {
        "global": hpwl_global,
        "legalized": hpwl_legalized,
        "after_improve": hpwl_after_improve,
        "final": hpwl_final,
        "delta_legalization": delta_legalization,
        "delta_improve": delta_improve,
        "delta_final": delta_final,
        "delta_legalization_percent": pct(delta_legalization),
        "delta_improve_percent": pct(delta_improve),
        "delta_final_percent": pct(delta_final),
    }


def summarize_metrics(metrics_path: Path) -> MetricSummary | None:
    data = load_json(metrics_path)
    if not data:
        return None
    hpwl = canonical_hpwl(data)
    stages = hpwl_stage_metrics(metrics_path, data, hpwl)
    disp = data.get("displacement", {})
    legal = data.get("legality", {})
    legalization = data.get("legalization", {})
    manifest = data.get("manifest", {})
    return MetricSummary(
        tag=metrics_path.parent.name,
        metrics_path=metrics_path,
        mode=str(legalization.get("legalizer_mode", "")),
        line=str(manifest.get("line", "")),
        run_tag=str(manifest.get("run_tag", metrics_path.parent.name)),
        hpwl_after=hpwl.get("after_micron"),
        hpwl_delta=hpwl.get("delta_micron"),
        runtime_seconds=data.get("runtime_seconds"),
        avg_disp=disp.get("average_displacement_micron"),
        max_disp=disp.get("max_displacement_micron"),
        violations=str(legal.get("placement_violations", "")),
        hpwl_delta_percent=hpwl_delta_percent(hpwl),
        hpwl_global=stages["global"],
        hpwl_legalized=stages["legalized"],
        hpwl_after_improve=stages["after_improve"],
        hpwl_stage_delta_legalization=stages["delta_legalization"],
        hpwl_stage_delta_improve=stages["delta_improve"],
        hpwl_stage_delta_final=stages["delta_final"],
        hpwl_stage_delta_legalization_percent=stages["delta_legalization_percent"],
        hpwl_stage_delta_improve_percent=stages["delta_improve_percent"],
        hpwl_stage_delta_final_percent=stages["delta_final_percent"],
    )


def is_canonical_baseline_summary(summary: MetricSummary, line: str) -> bool:
    """Return true only for orchestrator baseline-suite rows.

    Student evaluations also use `legalizer_mode=evolve_default`, so mode alone
    must never define the canonical baseline.  The baseline suite writes
    `baseline_probe_<line>` run tags; keep the match narrow so Teacher does not
    mistake a student candidate for the clean comparison anchor.
    """
    tag = summary.run_tag or summary.tag
    return (
        summary.line == line
        and f"baseline_probe_{line}" in tag
        and "_student_" not in tag
        and "_iter_" not in tag
        and summary.hpwl_after is not None
    )


def discover_case_metrics(
    *,
    orfs_root: Path,
    case_id: str,
    flow_variant: str,
) -> dict[str, MetricSummary | None]:
    info = get_case(case_id)
    report_root = (
        orfs_root
        / "flow"
        / "reports"
        / info.platform
        / info.design
        / flow_variant
        / "dpl_evolve_baseline"
    )
    candidates = sorted(
        report_root.glob("*/metrics.json"), key=lambda path: path.stat().st_mtime
    )
    summaries = [item for path in candidates if (item := summarize_metrics(path))]

    by_line: dict[str, MetricSummary | None] = {
        "openroad_dpl_flow": None,
        "evolve_default": None,
    }
    for summary in summaries:
        for line in CANONICAL_LINES:
            if is_canonical_baseline_summary(summary, line):
                by_line[line] = summary

    return by_line


def is_clean_placement(summary: MetricSummary) -> bool:
    return summary.violations.strip().lower() in {"", "0", "clean", "none"}


def parse_candidate_tag(round_id: str, case_id: str, tag: str) -> tuple[str, str, str]:
    body = tag
    suffix = f"_{case_id}"
    if body.endswith(suffix):
        body = body[: -len(suffix)]
    prefix = f"{round_id}_"
    if body.startswith(prefix):
        body = body[len(prefix) :]
    if "_student_" not in body:
        return "", "", body
    iter_part, rest = body.split("_student_", 1)
    pieces = rest.split("_")
    if not pieces:
        return iter_part, "", body
    route_label = "_".join(pieces[1:]) if len(pieces) > 1 else "teacher_assigned"
    return iter_part, f"student_{pieces[0]}", route_label


def candidate_iteration_number(iter_part: str) -> int | None:
    if not iter_part.startswith("iter_"):
        return None
    try:
        return int(iter_part.split("_", 1)[1])
    except (IndexError, ValueError):
        return None


def candidate_operation_id(round_id: str, case_id: str, tag: str) -> str:
    body = tag
    suffix = f"_{case_id}"
    if body.endswith(suffix):
        body = body[: -len(suffix)]
    return body if body.startswith(f"{round_id}_") else f"{round_id}_{body}"


def candidate_artifacts(
    *,
    runtime: Any,
    round_dir: Path,
    round_id: str,
    case_id: str,
    candidate: MetricSummary,
) -> CandidateArtifacts | None:
    iter_part, student_id, route_label = parse_candidate_tag(
        round_id, case_id, candidate.tag
    )
    if not iter_part or not student_id:
        return None
    operation_id = candidate_operation_id(round_id, case_id, candidate.tag)
    operation_dir = runtime.operations_dir / operation_id
    student_root = round_dir / "students" / student_id
    return CandidateArtifacts(
        iter_part=iter_part,
        iter_number=candidate_iteration_number(iter_part),
        student_id=student_id,
        route_label=route_label,
        operation_id=operation_id,
        operation_dir=operation_dir,
        last_message=operation_dir / "codex_last_message.txt",
        source_backup=student_root / "source_backups" / iter_part / "dpl_evolve",
        implementation_diff=student_root
        / iter_part
        / "artifacts"
        / "implementation.diff",
        knowledge_card=student_root / iter_part / "artifacts" / "knowledge_card.md",
    )


def discover_round_candidate_metrics(
    *,
    orfs_root: Path,
    case_id: str,
    flow_variant: str,
    round_id: str,
    before_iteration: int | None = None,
) -> list[MetricSummary]:
    info = get_case(case_id)
    report_root = (
        orfs_root
        / "flow"
        / "reports"
        / info.platform
        / info.design
        / flow_variant
        / "dpl_evolve_baseline"
    )
    summaries: list[MetricSummary] = []
    for path in report_root.glob(f"{round_id}_iter_*_student_*/metrics.json"):
        summary = summarize_metrics(path)
        if summary is None:
            continue
        if before_iteration is not None:
            iter_part, _student_id, _route_label = parse_candidate_tag(
                round_id, case_id, summary.tag
            )
            iter_number = candidate_iteration_number(iter_part)
            if iter_number is None or iter_number >= before_iteration:
                continue
        summaries.append(summary)
    return sorted(summaries, key=lambda item: item.tag)


def candidate_beats_baseline(
    summary: MetricSummary,
    baseline: MetricSummary | None,
) -> bool:
    return (
        baseline is not None
        and is_clean_placement(baseline)
        and baseline.hpwl_after is not None
        and is_clean_placement(summary)
        and summary.hpwl_after is not None
        and summary.hpwl_after < baseline.hpwl_after
    )


def runtime_ratio(
    summary: MetricSummary,
    baseline: MetricSummary | None,
) -> float | None:
    if (
        baseline is None
        or baseline.runtime_seconds in (None, 0)
        or summary.runtime_seconds is None
    ):
        return None
    return float(summary.runtime_seconds) / float(baseline.runtime_seconds)


def efficiency_signal(
    summary: MetricSummary,
    baseline: MetricSummary | None,
    *,
    budget_multiplier: float = 4.0,
) -> str:
    ratio = runtime_ratio(summary, baseline)
    if ratio is None:
        return "efficiency unknown"
    if ratio <= 1.5:
        return f"efficient ({ratio:.2f}x baseline)"
    if ratio <= budget_multiplier:
        return f"bounded ({ratio:.2f}x baseline)"
    return f"inefficient ({ratio:.2f}x baseline; not an effective donor)"


def stage_donor_signal(
    candidate: MetricSummary,
    baseline: MetricSummary | None,
    *,
    budget_multiplier: float = 4.0,
) -> str:
    """Classify candidate evidence without reducing it to final HPWL only.

    A strong HPWL result that needs much more than the student evaluation
    budget is quality evidence, not an effective donor.  This prevents endpoint
    stacking or many-round random replay from being promoted as an elite route.
    """
    if baseline is None or not is_clean_placement(candidate):
        return "unclassified"

    ratio = runtime_ratio(candidate, baseline)
    inefficient = ratio is not None and ratio > budget_multiplier

    if candidate_beats_baseline(candidate, baseline):
        if inefficient:
            return (
                "quality-only final signal; inefficient runtime "
                f"{ratio:.2f}x baseline, not an effective donor"
            )
        return "final donor"

    signals: list[str] = []
    if (
        baseline.hpwl_stage_delta_legalization is not None
        and candidate.hpwl_stage_delta_legalization is not None
    ):
        gain = baseline.hpwl_stage_delta_legalization - candidate.hpwl_stage_delta_legalization
        if gain > 0:
            signals.append(f"legalization stage donor: {gain:.1f} HPWL less damage")
    if (
        baseline.hpwl_stage_delta_improve is not None
        and candidate.hpwl_stage_delta_improve is not None
    ):
        gain = baseline.hpwl_stage_delta_improve - candidate.hpwl_stage_delta_improve
        if gain > 0:
            signals.append(f"improve stage donor: {gain:.1f} HPWL more recovery")
    if (
        baseline.hpwl_stage_delta_final is not None
        and candidate.hpwl_stage_delta_final is not None
    ):
        gain = baseline.hpwl_stage_delta_final - candidate.hpwl_stage_delta_final
        if gain > 0:
            signals.append(f"final-stage donor: {gain:.1f} HPWL lower final delta")

    if signals:
        signal = "; ".join(signals)
        if inefficient:
            return (
                "quality-only stage signal; inefficient runtime "
                f"{ratio:.2f}x baseline, not an effective donor: {signal}"
            )
        return signal
    return "negative evidence"


def strongest_baseline_anchor(
    metrics: dict[str, MetricSummary | None],
) -> tuple[str | None, MetricSummary | None]:
    """Return the clean baseline with the lowest canonical HPWL."""
    best_label: str | None = None
    best_summary: MetricSummary | None = None
    for label in CANONICAL_LINES:
        summary = metrics.get(label)
        if (
            summary is None
            or not is_clean_placement(summary)
            or summary.hpwl_after is None
        ):
            continue
        if (
            best_summary is None
            or best_summary.hpwl_after is None
            or summary.hpwl_after < best_summary.hpwl_after
        ):
            best_label = label
            best_summary = summary
    return best_label, best_summary


def five_percent_target_hpwl(baseline: MetricSummary | None) -> float | None:
    if baseline is None or baseline.hpwl_after is None:
        return None
    return baseline.hpwl_after * 0.95


def round_scoreboard(
    *,
    runtime: Any,
    case_id: str,
    flow_variant: str,
    round_id: str,
    metrics: dict[str, MetricSummary | None],
    before_iteration: int | None = None,
) -> str:
    candidates = discover_round_candidate_metrics(
        orfs_root=runtime.orfs_root,
        case_id=case_id,
        flow_variant=flow_variant,
        round_id=round_id,
        before_iteration=before_iteration,
    )
    if not candidates:
        return "No student candidate metrics have been found for this round yet."

    baseline_label, baseline = strongest_baseline_anchor(metrics)
    baseline_hpwl = baseline.hpwl_after if baseline else None
    target_hpwl = five_percent_target_hpwl(baseline)
    lines = [
        "| iter | student | route_label | HPWLg | dHPWLlg% | dHPWLip% | dHPWLfinal% | HPWL final | delta_vs_strongest | beats_strongest | gap_to_5pct_target | runtime_s | avg_disp | max_disp | violations | metrics |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|---|",
    ]
    best: MetricSummary | None = None
    best_beating: MetricSummary | None = None
    for summary in candidates:
        iter_part, student_id, route_label = parse_candidate_tag(
            round_id, case_id, summary.tag
        )
        if (
            best is None
            or (
                is_clean_placement(summary)
                and summary.hpwl_after is not None
                and (
                    not is_clean_placement(best)
                    or best.hpwl_after is None
                    or summary.hpwl_after < best.hpwl_after
                )
            )
        ):
            best = summary
        if candidate_beats_baseline(summary, baseline) and (
            best_beating is None
            or best_beating.hpwl_after is None
            or (
                summary.hpwl_after is not None
                and summary.hpwl_after < best_beating.hpwl_after
            )
        ):
            best_beating = summary
        delta = (
            None
            if baseline_hpwl is None or summary.hpwl_after is None
            else summary.hpwl_after - baseline_hpwl
        )
        target_gap = (
            None
            if target_hpwl is None or summary.hpwl_after is None
            else summary.hpwl_after - target_hpwl
        )
        lines.append(
            "| {iter_part} | {student_id} | {route_label} | {hpwlg} | {d_lg_pct} | {d_ip_pct} | {d_final_pct} | {hpwl} | {delta} | "
            "{beats} | {target_gap} | {runtime_s} | {avg_disp} | {max_disp} | {violations} | `{metrics_path}` |".format(
                iter_part=iter_part or "?",
                student_id=student_id or "?",
                route_label=route_label or summary.tag,
                hpwlg="" if summary.hpwl_global is None else f"{summary.hpwl_global:.3f}",
                d_lg_pct=""
                if summary.hpwl_stage_delta_legalization_percent is None
                else f"{summary.hpwl_stage_delta_legalization_percent:.2f}%",
                d_ip_pct=""
                if summary.hpwl_stage_delta_improve_percent is None
                else f"{summary.hpwl_stage_delta_improve_percent:.2f}%",
                d_final_pct=""
                if summary.hpwl_stage_delta_final_percent is None
                else f"{summary.hpwl_stage_delta_final_percent:.2f}%",
                hpwl="" if summary.hpwl_after is None else f"{summary.hpwl_after:.3f}",
                delta="" if delta is None else f"{delta:.3f}",
                beats="yes" if candidate_beats_baseline(summary, baseline) else "no",
                target_gap="" if target_gap is None else f"{target_gap:.3f}",
                runtime_s=""
                if summary.runtime_seconds is None
                else f"{summary.runtime_seconds:.3f}",
                avg_disp="" if summary.avg_disp is None else f"{summary.avg_disp:.4f}",
                max_disp="" if summary.max_disp is None else f"{summary.max_disp:.4f}",
                violations=summary.violations or "clean",
                metrics_path=summary.metrics_path,
            )
        )

    if best and best.hpwl_after is not None:
        best_iter, best_student, best_route_label = parse_candidate_tag(
            round_id, case_id, best.tag
        )
        best_delta = (
            None
            if baseline_hpwl is None
            else best.hpwl_after - baseline_hpwl
        )
        lines.extend(
            [
                "",
                "Best clean candidate so far: "
                f"`{best_iter or '?'}` / `{best_student or '?'}` / "
                f"`{best_route_label or best.tag}` with HPWL `{best.hpwl_after:.3f}`"
                + (
                    ""
                    if best_delta is None
                    else f" (`{best_delta:.3f}` vs {baseline_label or 'strongest baseline'})."
                ),
            ]
        )
    if best_beating and best_beating.hpwl_after is not None:
        beat_iter, beat_student, beat_route_label = parse_candidate_tag(
            round_id, case_id, best_beating.tag
        )
        lines.append(
            "Best strongest-baseline-beating candidate: "
            f"`{beat_iter or '?'}` / `{beat_student or '?'}` / "
            f"`{beat_route_label or best_beating.tag}`."
        )
    else:
        lines.append(
            "No prior student candidate beats the strongest clean baseline "
            f"(`{baseline_label or 'unknown'}`) yet."
        )
    if target_hpwl is not None:
        lines.append(
            f"Five-percent target from `{baseline_label}`: `{target_hpwl:.3f}`."
        )
    return "\n".join(lines)


def best_round_candidate(
    *,
    runtime: Any,
    case_id: str,
    flow_variant: str,
    round_id: str,
    baseline: MetricSummary | None = None,
    require_baseline_beat: bool = False,
    before_iteration: int | None = None,
) -> MetricSummary | None:
    best: MetricSummary | None = None
    for summary in discover_round_candidate_metrics(
        orfs_root=runtime.orfs_root,
        case_id=case_id,
        flow_variant=flow_variant,
        round_id=round_id,
        before_iteration=before_iteration,
    ):
        if not is_clean_placement(summary) or summary.hpwl_after is None:
            continue
        if require_baseline_beat and not candidate_beats_baseline(summary, baseline):
            continue
        if best is None or best.hpwl_after is None or summary.hpwl_after < best.hpwl_after:
            best = summary
    return best


def source_backup_for_candidate(
    *,
    round_dir: Path,
    round_id: str,
    case_id: str,
    candidate: MetricSummary | None,
) -> Path | None:
    if candidate is None:
        return None
    iter_part, student_id, _route_label = parse_candidate_tag(
        round_id, case_id, candidate.tag
    )
    if not iter_part or not student_id:
        return None
    source = round_dir / "students" / student_id / "source_backups" / iter_part / "dpl_evolve"
    return source if source.exists() else None


def peer_candidate_row(
    *,
    runtime: Any,
    round_dir: Path,
    round_id: str,
    case_id: str,
    candidate: MetricSummary,
    baseline: MetricSummary | None,
    budget_multiplier: float = 4.0,
) -> list[str]:
    artifacts = candidate_artifacts(
        runtime=runtime,
        round_dir=round_dir,
        round_id=round_id,
        case_id=case_id,
        candidate=candidate,
    )
    iter_part, student_id, route_label = parse_candidate_tag(
        round_id, case_id, candidate.tag
    )
    source_backup = artifacts.source_backup if artifacts else None
    implementation_diff = artifacts.implementation_diff if artifacts else None
    knowledge_card = artifacts.knowledge_card if artifacts else None
    delta = (
        None
        if baseline is None
        or baseline.hpwl_after is None
        or candidate.hpwl_after is None
        else candidate.hpwl_after - baseline.hpwl_after
    )
    beats = "yes" if candidate_beats_baseline(candidate, baseline) else "no"
    summary = (
        f"- `{iter_part or '?'}` / `{student_id or '?'}` / "
        f"`{route_label or candidate.tag}`: HPWLg `{candidate.hpwl_global}`, "
        f"dHPWL lg/ip/final `{_fmt_stage_pct(candidate)}`, "
        f"HPWL final `{candidate.hpwl_after}`, "
        f"delta_vs_baseline `{delta}`, runtime `{candidate.runtime_seconds}`, "
        f"efficiency `{efficiency_signal(candidate, baseline, budget_multiplier=budget_multiplier)}`, "
        f"avg/max disp `{candidate.avg_disp}/{candidate.max_disp}`, "
        f"legality `{candidate.violations or 'clean'}`, beats `{beats}`, "
        f"stage_signal `{stage_donor_signal(candidate, baseline, budget_multiplier=budget_multiplier)}`"
    )
    pointers = (
        f"  - inspect only if useful: metrics `{candidate.metrics_path}`; "
        f"source `{source_backup or ''}`; diff `{implementation_diff or ''}`; "
        f"knowledge `{knowledge_card or ''}`"
    )
    return [summary, pointers]


def write_peer_learning_packet(
    *,
    path: Path,
    runtime: Any,
    round_dir: Path,
    case_id: str,
    flow_variant: str,
    round_id: str,
    iteration: int,
    metrics: dict[str, MetricSummary | None],
    student_runtime_multiplier: float = 4.0,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    baseline_label, baseline = strongest_baseline_anchor(metrics)
    target_hpwl = five_percent_target_hpwl(baseline)
    candidates = discover_round_candidate_metrics(
        orfs_root=runtime.orfs_root,
        case_id=case_id,
        flow_variant=flow_variant,
        round_id=round_id,
        before_iteration=iteration,
    )
    clean_candidates = [
        item
        for item in candidates
        if is_clean_placement(item) and item.hpwl_after is not None
    ]
    clean_candidates.sort(key=lambda item: item.hpwl_after or float("inf"))
    beating_candidates = [
        item for item in clean_candidates if candidate_beats_baseline(item, baseline)
    ]

    chunks = [
        "# Generated Peer Learning Packet",
        "",
        "This file is generated by the orchestrator.  It is the code-learning "
        "index for the next Teacher/Student step.",
        "",
        "Use it to borrow mechanisms and source from validated peer candidates. "
        "A clean candidate that beats the strongest baseline is useful donor "
        "evidence only when its runtime and complexity are controlled. Treat "
        "5% below the strongest baseline as a credible research target, not a "
        "hard gate; below-5% stage donors can still be useful when efficient.",
        "",
        "## Baseline Anchor",
    ]
    if baseline is None:
        chunks.append("- strongest clean baseline: missing")
    else:
        chunks.extend(
            [
                f"- strongest_baseline: `{baseline_label}`",
                f"- HPWLg: `{baseline.hpwl_global}`",
                f"- delta_HPWL_legalization: `{baseline.hpwl_stage_delta_legalization}`",
                f"- delta_HPWL_improve: `{baseline.hpwl_stage_delta_improve}`",
                f"- delta_HPWL_final: `{baseline.hpwl_stage_delta_final}`",
                f"- stage_delta_pct_lg_ip_final: `{_fmt_stage_pct(baseline)}`",
                f"- hpwl_after: `{baseline.hpwl_after}`",
                f"- five_percent_target_hpwl: `{target_hpwl}`",
                f"- runtime_seconds: `{baseline.runtime_seconds}`",
                f"- avg_disp: `{baseline.avg_disp}`",
                f"- max_disp: `{baseline.max_disp}`",
                f"- violations: `{baseline.violations or 'clean'}`",
                f"- metrics_json: `{baseline.metrics_path}`",
            ]
        )

    chunks.extend(["", "## Best Strongest-Baseline-Beating Candidates"])
    if not beating_candidates:
        chunks.append(
            "No prior clean student candidate beats the strongest baseline yet. "
            "Students may still inspect the best clean candidate as a clue, "
            "but it is not an elite seed."
        )
    else:
        for candidate in beating_candidates[:3]:
            chunks.extend(
                peer_candidate_row(
                    runtime=runtime,
                    round_dir=round_dir,
                    round_id=round_id,
                    case_id=case_id,
                    candidate=candidate,
                    baseline=baseline,
                    budget_multiplier=student_runtime_multiplier,
                )
            )

    chunks.extend(["", "## Best Clean Candidates"])
    if not clean_candidates:
        chunks.append("No prior clean student candidate metrics are available.")
    else:
        for candidate in clean_candidates[:3]:
            chunks.extend(
                peer_candidate_row(
                    runtime=runtime,
                    round_dir=round_dir,
                    round_id=round_id,
                    case_id=case_id,
                    candidate=candidate,
                    baseline=baseline,
                    budget_multiplier=student_runtime_multiplier,
                )
            )

    chunks.extend(
        [
            "",
            "## Use Policy",
            "- Teacher should compare code and metrics before assigning a borrow/merge direction.",
            f"- Teacher must separate effective donors from quality-only signals.  A candidate that wins mainly by repeated random/end-point replay or exceeds the {student_runtime_multiplier:g}x runtime budget is not an effective donor until the mechanism is reimplemented with bounded complexity.",
            "- Teacher must separate final donors from stage donors.  If a candidate improves one stage but loses later, preserve a repair route for the later-stage handoff.",
            "- Student may inspect peer code when it directly supports the chosen implementation change.",
            "- If a student opens peer code or diff, first summarize the peer idea in 2-3 lines, then decide what to borrow.",
            "- Prefer learning a mechanism over blind wholesale replacement.",
            "- A clean strongest-baseline-beating candidate may seed an elite continuation branch only when its efficiency signal is bounded or better.",
            "- Sub-1% wins over `evolve_default` are donor evidence, not success.",
        ]
    )
    path.write_text("\n".join(chunks) + "\n", encoding="utf-8")
    return path


def seed_private_source_from_elite(
    *,
    seed_source: Path,
    target_source: Path,
) -> None:
    if not seed_source.exists():
        raise FileNotFoundError(f"missing elite seed source: {seed_source}")
    if target_source.exists():
        shutil.rmtree(target_source)
    target_source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        seed_source,
        target_source,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            "*.o",
            "*.a",
            "*.so",
            "CMakeFiles",
            "cmake_install.cmake",
        ),
    )


def baseline_suite_preflight_command(
    *,
    runtime: Any,
    case_id: str,
    flow_variant: str,
    threads: int,
    round_id: str,
) -> list[str]:
    command = [
        str(runtime.agent_root / "baseline" / "run_baseline_suite.sh"),
        "--case",
        case_id,
        "--flow-variant",
        flow_variant,
        "--threads",
        str(threads),
        "--tag-prefix",
        f"{round_id}_baseline_probe",
    ]
    core_binary = openroad_core_binary(runtime)
    if core_binary is not None:
        command.extend(["--openroad-binary", str(core_binary)])
    return command


def openroad_core_binary(runtime: Any) -> Path | None:
    """Return the freshly built common OpenROAD core binary if identifiable."""
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(runtime.orfs_root / "tools" / "OpenROAD"),
                "rev-parse",
                "--short",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return None
    anchor_id = proc.stdout.strip()
    if not anchor_id:
        return None
    return (
        runtime.state_root
        / "openroad_core"
        / anchor_id
        / "install"
        / "OpenROAD"
        / "bin"
        / "openroad"
    )


def baseline_suite_complete(metrics: dict[str, MetricSummary | None]) -> bool:
    return all(metrics.get(line) is not None for line in CANONICAL_LINES)


def ensure_baseline_suite(
    *,
    runtime: Any,
    case_id: str,
    flow_variant: str,
    threads: int,
    round_id: str,
    refresh: bool,
    dry_run: bool,
) -> tuple[dict[str, MetricSummary | None], list[list[str]]]:
    command = baseline_suite_preflight_command(
        runtime=runtime,
        case_id=case_id,
        flow_variant=flow_variant,
        threads=threads,
        round_id=round_id,
    )
    metrics = discover_case_metrics(
        orfs_root=runtime.orfs_root,
        case_id=case_id,
        flow_variant=flow_variant,
    )
    if baseline_suite_complete(metrics) and not refresh:
        return metrics, []

    if dry_run:
        return metrics, [command]

    print("[optimize_case] baseline suite preflight:", " ".join(shlex.quote(part) for part in command))
    subprocess.run(command, check=True, env=clean_subprocess_env())
    metrics = discover_case_metrics(
        orfs_root=runtime.orfs_root,
        case_id=case_id,
        flow_variant=flow_variant,
    )
    if not baseline_suite_complete(metrics):
        missing = ", ".join(line for line in CANONICAL_LINES if metrics.get(line) is None)
        raise SystemExit(
            "Baseline suite preflight completed but missing metrics for "
            f"{missing} under flow_variant={flow_variant}."
        )
    return metrics, [command]


def metric_table(metrics: dict[str, MetricSummary | None]) -> str:
    lines = [
        "| line | tag | HPWLg | delta HPWLlg | delta HPWLip | delta HPWL final | HPWL final | runtime_s | avg_disp | max_disp | violations |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name in CANONICAL_LINES:
        summary = metrics.get(name)
        if summary is None:
            lines.append(f"| {name} | missing |  |  |  |  |  |  |  |  |  |")
            continue
        lines.append(
            "| {name} | {tag} | {hpwlg} | {d_lg} | {d_ip} | {d_final} | {hpwl_after} | {runtime} | "
            "{avg_disp} | {max_disp} | {violations} |".format(
                name=name,
                tag=summary.tag,
                hpwlg="" if summary.hpwl_global is None else f"{summary.hpwl_global:.3f}",
                d_lg=""
                if summary.hpwl_stage_delta_legalization is None
                else f"{summary.hpwl_stage_delta_legalization:.3f}",
                d_ip=""
                if summary.hpwl_stage_delta_improve is None
                else f"{summary.hpwl_stage_delta_improve:.3f}",
                d_final=""
                if summary.hpwl_stage_delta_final is None
                else f"{summary.hpwl_stage_delta_final:.3f}",
                hpwl_after="" if summary.hpwl_after is None else f"{summary.hpwl_after:.3f}",
                runtime=""
                if summary.runtime_seconds is None
                else f"{summary.runtime_seconds:.3f}",
                avg_disp="" if summary.avg_disp is None else f"{summary.avg_disp:.4f}",
                max_disp="" if summary.max_disp is None else f"{summary.max_disp:.4f}",
                violations=summary.violations or "clean",
            )
        )
    return "\n".join(lines)


def _fmt_float(value: Any, digits: int = 3, suffix: str = "") -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_stage_pct(summary: MetricSummary) -> str:
    parts = []
    for label, value in (
        ("lg", summary.hpwl_stage_delta_legalization_percent),
        ("ip", summary.hpwl_stage_delta_improve_percent),
        ("final", summary.hpwl_stage_delta_final_percent),
    ):
        parts.append(f"{label}:{_fmt_float(value, 2, '%')}")
    return " / ".join(parts)


def design_characteristics_block(
    *,
    case_id: str,
    flow_variant: str,
    metrics: dict[str, MetricSummary | None],
) -> str:
    """Summarize case facts Teacher should pass to students.

    Keep this evidence-derived and compact.  The Teacher can add judgment, but
    this block gives it the concrete design/baseline facts that matter before
    asking students to modify algorithms.
    """
    anchor_label, anchor = strongest_baseline_anchor(metrics)
    target_hpwl = five_percent_target_hpwl(anchor)
    anchor_data = load_json(anchor.metrics_path) if anchor is not None else None
    design = (anchor_data or {}).get("design_metrics", {})
    disp = (anchor_data or {}).get("displacement", {})
    legalize = (anchor_data or {}).get("legalization", {})
    summary_data = load_json(anchor.metrics_path.parent / "legalize_summary.json") if anchor is not None else None
    fixed_count = (summary_data or {}).get("fixed_instance_count")
    placed_count = (summary_data or {}).get("placed_instance_count")

    utilization = design.get("utilization")
    util_text = ""
    if utilization is not None:
        util_text = _fmt_float(float(utilization) * 100.0, 1, "%")

    lines = [
        f"- case: `{case_id}`",
        f"- flow_variant/input: `{flow_variant}` / `3_4_place_resized.odb`",
        "- density: core_area={core}um^2, instance_area={inst}um^2, "
        "utilization={util}".format(
            core=_fmt_float(design.get("core_area"), 1),
            inst=_fmt_float(design.get("instance_area"), 1),
            util=util_text,
        ),
        "- population: instances={inst_count}, movable={movable}, fixed={fixed}, placed={placed}".format(
            inst_count=design.get("instance_count", ""),
            movable=disp.get("movable_instance_count", ""),
            fixed=fixed_count if fixed_count is not None else "",
            placed=placed_count if placed_count is not None else "",
        ),
        "- baseline flow: `{seq}`".format(seq=legalize.get("stage_sequence", "")),
        "- baseline displacement: avg={avg}um, max={maxd}um, moved={moved}".format(
            avg=_fmt_float(disp.get("average_displacement_micron"), 4),
            maxd=_fmt_float(disp.get("max_displacement_micron"), 4),
            moved=disp.get("moved_instance_count", ""),
        ),
        "- strongest baseline: `{label}`, five_percent_target_hpwl={target}".format(
            label=anchor_label or "",
            target=_fmt_float(target_hpwl, 3),
        ),
    ]

    lines.extend(
        [
            "",
            "HPWL values below use OpenROAD/DPL pin-based log HPWL only. "
            "`hpwl_proxy` is debug-only and is never a promotion metric.",
            "",
            "| line | HPWLg | delta HPWLlg | delta HPWLip | delta HPWL final | HPWL final | stage_delta_pct | runtime_s | violations |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for line in CANONICAL_LINES:
        summary = metrics.get(line)
        if summary is None:
            lines.append(f"| {line} | missing |  |  |  |  |  |  |  |")
            continue
        lines.append(
            "| {line} | {hpwlg} | {d_lg} | {d_ip} | {d_final} | {after} | {stage_pct} | {runtime} | {violations} |".format(
                line=line,
                hpwlg=_fmt_float(summary.hpwl_global, 3),
                d_lg=_fmt_float(summary.hpwl_stage_delta_legalization, 3),
                d_ip=_fmt_float(summary.hpwl_stage_delta_improve, 3),
                d_final=_fmt_float(summary.hpwl_stage_delta_final, 3),
                after=_fmt_float(summary.hpwl_after, 3),
                stage_pct=_fmt_stage_pct(summary),
                runtime=_fmt_float(summary.runtime_seconds, 3),
                violations=summary.violations or "clean",
            )
        )
    return "\n".join(lines)


def write_design_characteristics_packet(
    *,
    path: Path,
    case_id: str,
    flow_variant: str,
    metrics: dict[str, MetricSummary | None],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Generated Design Characteristics\n\n"
        + design_characteristics_block(
            case_id=case_id,
            flow_variant=flow_variant,
            metrics=metrics,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def baseline_artifact_block(
    *,
    runtime: Any,
    case_id: str,
    flow_variant: str,
    metrics: dict[str, MetricSummary | None],
) -> str:
    info = get_case(case_id)
    flow_root = runtime.orfs_root / "flow"
    blocks = []
    for line in CANONICAL_LINES:
        summary = metrics.get(line)
        blocks.append(f"### {line}")
        if summary is None:
            blocks.append("- status: missing; run the baseline suite before making a promotion decision.")
            continue
        tag = summary.tag
        rel_root = Path(info.platform) / info.design / flow_variant / "dpl_evolve_baseline" / tag
        report_dir = flow_root / "reports" / rel_root
        log_dir = flow_root / "logs" / rel_root
        result_dir = flow_root / "results" / rel_root
        blocks.extend(
            [
                f"- run_tag: `{tag}`",
                f"- HPWLg: `{summary.hpwl_global}`",
                f"- delta_HPWL_legalization: `{summary.hpwl_stage_delta_legalization}`",
                f"- delta_HPWL_improve: `{summary.hpwl_stage_delta_improve}`",
                f"- delta_HPWL_final: `{summary.hpwl_stage_delta_final}`",
                f"- stage_delta_pct_lg_ip_final: `{_fmt_stage_pct(summary)}`",
                f"- HPWL_final: `{summary.hpwl_after}`",
                f"- metrics_json: `{summary.metrics_path}`",
                f"- report_dir: `{report_dir}`",
                f"- result_dir: `{result_dir}`",
                f"- log_dir: `{log_dir}`",
                f"- legalize_log: `{log_dir / f'dpl_evolve_{tag}_legalize.log'}`",
                f"- metrics_log: `{log_dir / '3_5_place_dp.log'}`",
                f"- legalize_summary: `{report_dir / 'legalize_summary.json'}`",
                f"- check_report: `{report_dir / 'check_placement_report.json'}`",
                f"- legalized_odb: `{result_dir / 'legalized.odb'}`",
            ]
        )
    return "\n".join(blocks)


def write_baseline_artifacts_packet(
    *,
    path: Path,
    runtime: Any,
    case_id: str,
    flow_variant: str,
    metrics: dict[str, MetricSummary | None],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Generated Baseline Artifact Packet\n\n"
        + baseline_artifact_block(
            runtime=runtime,
            case_id=case_id,
            flow_variant=flow_variant,
            metrics=metrics,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def operation_artifact_block(runtime: Any, operation_id: str) -> str:
    op_dir = runtime.operations_dir / operation_id
    return f"""- operation_id: `{operation_id}`
  operation_dir: `{op_dir}`
  last_message: `{op_dir / "codex_last_message.txt"}`
  usage_summary: `{op_dir / "codex_usage_summary.json"}`
  events_large_do_not_read_by_default: `{op_dir / "codex_events.jsonl"}`
  stderr: `{op_dir / "codex_stderr.log"}`
"""


def expected_metrics_path(
    *,
    runtime: Any,
    case_id: str,
    flow_variant: str,
    run_tag: str,
) -> Path:
    info = get_case(case_id)
    return (
        runtime.orfs_root
        / "flow"
        / "reports"
        / info.platform
        / info.design
        / flow_variant
        / "dpl_evolve_baseline"
        / run_tag
        / "metrics.json"
    )


def child_artifact_status(
    *,
    runtime: Any,
    case_id: str,
    flow_variant: str,
    child: ChildRound,
) -> dict[str, Any]:
    usage = load_json(child.usage_summary) or {}
    metrics_path = expected_metrics_path(
        runtime=runtime,
        case_id=case_id,
        flow_variant=flow_variant,
        run_tag=child.run_tag,
    )
    metric_summary = summarize_metrics(metrics_path) if metrics_path.exists() else None
    diff_size = child.implementation_diff.stat().st_size if child.implementation_diff.exists() else 0
    knowledge_size = child.knowledge_card.stat().st_size if child.knowledge_card.exists() else 0
    last_message_size = child.last_message.stat().st_size if child.last_message.exists() else 0
    returncode = usage.get("returncode")
    agent_message_count = int(usage.get("agent_message_count", 0) or 0)

    problems: list[str] = []
    if not child.usage_summary.exists():
        problems.append("missing_usage_summary")
    elif returncode != 0:
        problems.append(f"codex_returncode_{returncode}")
    if agent_message_count <= 0:
        problems.append("no_agent_message")
    if last_message_size <= 0:
        problems.append("empty_last_message")
    if not child.private_binary.exists():
        problems.append("missing_private_binary")
    if not metrics_path.exists():
        problems.append("missing_metrics_json")
    if not child.implementation_diff.exists():
        problems.append("missing_implementation_diff")
    elif diff_size <= 0:
        problems.append("empty_implementation_diff")
    if not child.knowledge_card.exists():
        problems.append("missing_knowledge_card")
    elif knowledge_size <= 0:
        problems.append("empty_knowledge_card")

    status = "valid" if not problems else "invalid"
    return {
        "status": status,
        "problems": problems,
        "usage": usage,
        "returncode": returncode,
        "agent_message_count": agent_message_count,
        "last_message_exists": child.last_message.exists(),
        "last_message_size": last_message_size,
        "private_binary_exists": child.private_binary.exists(),
        "metrics_path": metrics_path,
        "metrics_exists": metrics_path.exists(),
        "metric_summary": metric_summary,
        "diff_exists": child.implementation_diff.exists(),
        "diff_size": diff_size,
        "knowledge_card": child.knowledge_card,
        "knowledge_exists": child.knowledge_card.exists(),
        "knowledge_size": knowledge_size,
    }


def child_artifact_status_block(
    *,
    runtime: Any,
    case_id: str,
    flow_variant: str,
    child: ChildRound,
) -> str:
    status = child_artifact_status(
        runtime=runtime,
        case_id=case_id,
        flow_variant=flow_variant,
        child=child,
    )
    metric_summary = status["metric_summary"]
    metric_lines = ["- metrics_summary: `missing`"]
    if metric_summary is not None:
        metric_lines = [
            "- metrics_summary:",
            f"  - HPWLg: `{metric_summary.hpwl_global}`",
            f"  - delta_HPWL_legalization: `{metric_summary.hpwl_stage_delta_legalization}`",
            f"  - delta_HPWL_improve: `{metric_summary.hpwl_stage_delta_improve}`",
            f"  - delta_HPWL_final: `{metric_summary.hpwl_stage_delta_final}`",
            f"  - stage_delta_pct_lg_ip_final: `{_fmt_stage_pct(metric_summary)}`",
            f"  - hpwl_after: `{metric_summary.hpwl_after}`",
            f"  - hpwl_delta: `{metric_summary.hpwl_delta}`",
            f"  - runtime_seconds: `{metric_summary.runtime_seconds}`",
            f"  - avg_disp: `{metric_summary.avg_disp}`",
            f"  - max_disp: `{metric_summary.max_disp}`",
            f"  - violations: `{metric_summary.violations or 'clean'}`",
        ]

    problems = status["problems"]
    problem_text = ", ".join(problems) if problems else "none"
    return "\n".join(
        [
            f"- artifact_status: `{status['status']}`",
            f"- artifact_problems: `{problem_text}`",
            f"- codex_returncode: `{status['returncode']}`",
            f"- agent_message_count: `{status['agent_message_count']}`",
            f"- last_message_exists: `{status['last_message_exists']}`",
            f"- last_message_size: `{status['last_message_size']}`",
            f"- private_binary_exists: `{status['private_binary_exists']}`",
            f"- metrics_json_expected: `{status['metrics_path']}`",
            f"- metrics_json_exists: `{status['metrics_exists']}`",
            f"- implementation_diff_exists: `{status['diff_exists']}`",
            f"- implementation_diff_size: `{status['diff_size']}`",
            f"- knowledge_card: `{status['knowledge_card']}`",
            f"- knowledge_card_exists: `{status['knowledge_exists']}`",
            f"- knowledge_card_size: `{status['knowledge_size']}`",
            *metric_lines,
        ]
    )


def write_child_artifact_status_json(
    *,
    path: Path,
    runtime: Any,
    case_id: str,
    flow_variant: str,
    child_rounds: list[ChildRound],
) -> Path:
    rows: list[dict[str, Any]] = []
    for child in child_rounds:
        status = child_artifact_status(
            runtime=runtime,
            case_id=case_id,
            flow_variant=flow_variant,
            child=child,
        )
        metric_summary = status.pop("metric_summary")
        status.pop("usage", None)
        status["metrics_path"] = str(status["metrics_path"])
        status["knowledge_card"] = str(status["knowledge_card"])
        if metric_summary is not None:
            status["metrics_summary"] = {
                "HPWLg": metric_summary.hpwl_global,
                "delta_HPWL_legalization": metric_summary.hpwl_stage_delta_legalization,
                "delta_HPWL_improve": metric_summary.hpwl_stage_delta_improve,
                "delta_HPWL_final": metric_summary.hpwl_stage_delta_final,
                "delta_HPWL_legalization_percent": metric_summary.hpwl_stage_delta_legalization_percent,
                "delta_HPWL_improve_percent": metric_summary.hpwl_stage_delta_improve_percent,
                "delta_HPWL_final_percent": metric_summary.hpwl_stage_delta_final_percent,
                "hpwl_after": metric_summary.hpwl_after,
                "hpwl_delta": metric_summary.hpwl_delta,
                "runtime_seconds": metric_summary.runtime_seconds,
                "avg_disp": metric_summary.avg_disp,
                "max_disp": metric_summary.max_disp,
                "violations": metric_summary.violations,
            }
        else:
            status["metrics_summary"] = None
        rows.append(
            {
                "student_id": child.student_id,
                "route_label": child.route_label,
                "operation_id": child.operation_id,
                "run_tag": child.run_tag,
                **status,
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        print(
            "[optimize_case] child_artifacts "
            f"{row['student_id']} status={row['status']} "
            f"problems={','.join(row['problems']) or 'none'}"
        )
    return path
