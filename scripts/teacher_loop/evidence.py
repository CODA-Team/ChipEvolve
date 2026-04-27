"""Metrics, baseline evidence, peer-learning, and artifact packets."""
from __future__ import annotations

import json
import shlex
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


def summarize_metrics(metrics_path: Path) -> MetricSummary | None:
    data = load_json(metrics_path)
    if not data:
        return None
    hpwl = data.get("hpwl_proxy", {})
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
    strategy = "_".join(pieces[1:]) if len(pieces) > 1 else "open_explore"
    return iter_part, f"student_{pieces[0]}", strategy


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
    iter_part, student_id, strategy = parse_candidate_tag(
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
        strategy=strategy,
        operation_id=operation_id,
        operation_dir=operation_dir,
        last_message=operation_dir / "codex_last_message.txt",
        source_backup=student_root / "source_backups" / iter_part / "dpl_evolve",
        implementation_diff=student_root
        / iter_part
        / "artifacts"
        / "implementation.diff",
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
            iter_part, _student_id, _strategy = parse_candidate_tag(
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

    baseline = metrics.get("openroad_dpl_flow")
    baseline_hpwl = baseline.hpwl_after if baseline else None
    lines = [
        "| iter | student | strategy | hpwl_after | delta_vs_openroad | beats_openroad | runtime_s | avg_disp | max_disp | violations | metrics |",
        "|---|---|---|---:|---:|---|---:|---:|---:|---|---|",
    ]
    best: MetricSummary | None = None
    best_beating: MetricSummary | None = None
    for summary in candidates:
        iter_part, student_id, strategy = parse_candidate_tag(
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
        lines.append(
            "| {iter_part} | {student_id} | {strategy} | {hpwl} | {delta} | "
            "{beats} | {runtime_s} | {avg_disp} | {max_disp} | {violations} | `{metrics_path}` |".format(
                iter_part=iter_part or "?",
                student_id=student_id or "?",
                strategy=strategy or summary.tag,
                hpwl="" if summary.hpwl_after is None else f"{summary.hpwl_after:.3f}",
                delta="" if delta is None else f"{delta:.3f}",
                beats="yes" if candidate_beats_baseline(summary, baseline) else "no",
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
        best_iter, best_student, best_strategy = parse_candidate_tag(
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
                f"`{best_strategy or best.tag}` with HPWL `{best.hpwl_after:.3f}`"
                + ("" if best_delta is None else f" (`{best_delta:.3f}` vs OpenROAD)."),
            ]
        )
    if best_beating and best_beating.hpwl_after is not None:
        beat_iter, beat_student, beat_strategy = parse_candidate_tag(
            round_id, case_id, best_beating.tag
        )
        lines.append(
            "Best baseline-beating candidate: "
            f"`{beat_iter or '?'}` / `{beat_student or '?'}` / "
            f"`{beat_strategy or best_beating.tag}`."
        )
    else:
        lines.append("No prior student candidate beats `openroad_dpl_flow` yet.")
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
    iter_part, student_id, _strategy = parse_candidate_tag(
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
) -> list[str]:
    artifacts = candidate_artifacts(
        runtime=runtime,
        round_dir=round_dir,
        round_id=round_id,
        case_id=case_id,
        candidate=candidate,
    )
    iter_part, student_id, strategy = parse_candidate_tag(
        round_id, case_id, candidate.tag
    )
    source_backup = artifacts.source_backup if artifacts else None
    implementation_diff = artifacts.implementation_diff if artifacts else None
    delta = (
        None
        if baseline is None
        or baseline.hpwl_after is None
        or candidate.hpwl_after is None
        else candidate.hpwl_after - baseline.hpwl_after
    )
    return [
        f"- candidate: `{iter_part or '?'}` / `{student_id or '?'}` / `{strategy or candidate.tag}`",
        f"  - beats_openroad_dpl_flow: `{'yes' if candidate_beats_baseline(candidate, baseline) else 'no'}`",
        f"  - hpwl_after: `{candidate.hpwl_after}`",
        f"  - delta_vs_openroad: `{delta}`",
        f"  - runtime_seconds: `{candidate.runtime_seconds}`",
        f"  - avg_disp: `{candidate.avg_disp}`",
        f"  - max_disp: `{candidate.max_disp}`",
        f"  - violations: `{candidate.violations or 'clean'}`",
        f"  - metrics_json: `{candidate.metrics_path}`",
        f"  - source_backup: `{source_backup or ''}`",
        f"  - source_backup_exists: `{source_backup.exists() if source_backup is not None else False}`",
        f"  - implementation_diff: `{implementation_diff or ''}`",
        f"  - implementation_diff_exists: `{implementation_diff.exists() if implementation_diff is not None else False}`",
        f"  - last_message: `{artifacts.last_message if artifacts else ''}`",
    ]


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
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    baseline = metrics.get("openroad_dpl_flow")
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
        "Do not promote a candidate unless it is clean and beats `openroad_dpl_flow`.",
        "",
        "## Baseline Anchor",
    ]
    if baseline is None:
        chunks.append("- `openroad_dpl_flow`: missing")
    else:
        chunks.extend(
            [
                f"- hpwl_after: `{baseline.hpwl_after}`",
                f"- runtime_seconds: `{baseline.runtime_seconds}`",
                f"- avg_disp: `{baseline.avg_disp}`",
                f"- max_disp: `{baseline.max_disp}`",
                f"- violations: `{baseline.violations or 'clean'}`",
                f"- metrics_json: `{baseline.metrics_path}`",
            ]
        )

    chunks.extend(["", "## Best Baseline-Beating Candidates"])
    if not beating_candidates:
        chunks.append(
            "No prior clean student candidate beats `openroad_dpl_flow` yet. "
            "Students may still inspect the best clean candidate as a clue, "
            "but it is not an elite seed."
        )
    else:
        for candidate in beating_candidates[:5]:
            chunks.extend(
                peer_candidate_row(
                    runtime=runtime,
                    round_dir=round_dir,
                    round_id=round_id,
                    case_id=case_id,
                    candidate=candidate,
                    baseline=baseline,
                )
            )

    chunks.extend(["", "## Best Clean Candidates"])
    if not clean_candidates:
        chunks.append("No prior clean student candidate metrics are available.")
    else:
        for candidate in clean_candidates[:8]:
            chunks.extend(
                peer_candidate_row(
                    runtime=runtime,
                    round_dir=round_dir,
                    round_id=round_id,
                    case_id=case_id,
                    candidate=candidate,
                    baseline=baseline,
                )
            )

    chunks.extend(
        [
            "",
            "## Use Policy",
            "- Teacher should compare code and metrics before assigning a borrow/merge direction.",
            "- Student may inspect peer code when it directly supports the chosen implementation change.",
            "- Prefer learning a mechanism over blind wholesale replacement.",
            "- A clean baseline-beating candidate may seed an elite continuation branch.",
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
    return [
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
        "| line | tag | hpwl_after | hpwl_delta | runtime_s | avg_disp | max_disp | violations |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for name in CANONICAL_LINES:
        summary = metrics.get(name)
        if summary is None:
            lines.append(f"| {name} | missing |  |  |  |  |  |  |")
            continue
        lines.append(
            "| {name} | {tag} | {hpwl_after} | {hpwl_delta} | {runtime} | "
            "{avg_disp} | {max_disp} | {violations} |".format(
                name=name,
                tag=summary.tag,
                hpwl_after="" if summary.hpwl_after is None else f"{summary.hpwl_after:.3f}",
                hpwl_delta="" if summary.hpwl_delta is None else f"{summary.hpwl_delta:.3f}",
                runtime=""
                if summary.runtime_seconds is None
                else f"{summary.runtime_seconds:.3f}",
                avg_disp="" if summary.avg_disp is None else f"{summary.avg_disp:.4f}",
                max_disp="" if summary.max_disp is None else f"{summary.max_disp:.4f}",
                violations=summary.violations or "clean",
            )
        )
    return "\n".join(lines)


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
        if metric_summary is not None:
            status["metrics_summary"] = {
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
                "strategy": child.strategy,
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
