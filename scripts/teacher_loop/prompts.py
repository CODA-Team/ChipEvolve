"""Prompt, packet, context, and prompt-audit generation."""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from runtime_paths import clean_subprocess_env
from scripts.teacher_loop.common import (
    AGENT_ROOT,
    CANONICAL_LINES,
    ChildRound,
    MetricSummary,
    StudentWorkspace,
    assigned_start_kind_from_insight,
    iter_name,
    render_prompt_template,
    round_id_from_dir,
    stable_candidate_ref,
    student_workspace_paths,
)
from scripts.teacher_loop.evidence import (
    baseline_artifact_block,
    candidate_artifacts,
    candidate_artifact_problems,
    candidate_artifact_status_text,
    child_artifact_status_block,
    design_characteristics_block,
    discover_round_candidate_metrics,
    expected_metrics_path,
    hpwl_runtime_gain,
    hpwl_runtime_gain_factors,
    metric_table,
    operation_artifact_block,
    parse_candidate_tag,
    stage_donor_signal,
    summarize_metrics,
    value_reference_anchor,
)


NOISY_CONTEXT_MARKERS = (
    "[" + "trun" + "cated]",
    "[" + "excerpt " + "trun" + "cated]",
    "<" + "br>",
)

INFRASTRUCTURE_REVIEW_MARKERS = (
    "bwrap: Unknown option --perms",
    "could not read `teacher_review_artifacts.md`",
    "could not read teacher_review_artifacts.md",
    "Blocked before review",
    "Blocked: the local command tool is failing",
    "every shell command is failing",
)


def read_text_excerpt(path: Path, *, max_chars: int = 6000) -> str:
    if not path.exists():
        return render_prompt_template("context/missing_text_source.md", path=path).strip()
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return render_prompt_template("context/empty_text_source.md", path=path).strip()
    if len(text) <= max_chars:
        return text
    return render_prompt_template("context/long_content_pointer.md", path=path).strip()


def previous_teacher_review_text(
    *, runtime: Any, round_id: str, iteration: int, warn_chars: int = 12000
) -> str:
    """Return the complete previous Teacher review.

    Review evidence must not be summarized or capped before another agent sees
    it.  Long reviews get a warning header, but the full text remains available
    in the generated context.
    """
    if iteration <= 1:
        return render_prompt_template("context/no_previous_teacher_review.md").strip()
    review_op = f"{round_id}_{iter_name(iteration - 1)}_teacher_review"
    review_path = runtime.operations_dir / review_op / "codex_last_message.txt"
    if not review_path.exists():
        return render_prompt_template(
            "context/missing_previous_teacher_review.md",
            review_path=review_path,
        ).strip()
    text = review_path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return render_prompt_template(
            "context/empty_previous_teacher_review.md",
            review_path=review_path,
        ).strip()
    if any(marker in text for marker in INFRASTRUCTURE_REVIEW_MARKERS):
        return render_prompt_template("context/previous_review_infra_omitted.md").strip()
    if len(text) <= warn_chars:
        return text
    return (
        render_prompt_template(
            "context/long_previous_teacher_review_warning.md",
            review_path=review_path,
            review_chars=len(text),
            warn_chars=warn_chars,
        ).strip()
        + "\n\n"
        + text
    )


def compact_inline_text(text: str, *, max_chars: int = 220) -> str:
    """Return one prompt-safe line without noisy truncation markers."""
    cleaned = text.replace("|", "/")
    for marker in NOISY_CONTEXT_MARKERS:
        cleaned = cleaned.replace(marker, " ")
    cleaned = " ".join(cleaned.split())
    if len(cleaned) <= max_chars:
        return cleaned
    clipped = cleaned[: max_chars - 3].rstrip()
    for sep in (". ", "; ", ", ", " "):
        idx = clipped.rfind(sep)
        if idx >= max_chars // 2:
            clipped = clipped[: idx + (1 if sep == " " else 1)].rstrip()
            break
    return clipped.rstrip(".,;:") + "..."


def format_multiplier(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def markdown_section_excerpt(text: str, heading: str, *, max_chars: int = 220) -> str:
    """Extract a short section body from a student knowledge card."""
    wanted = heading.strip().lower()
    in_section = False
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            title = line.lstrip("#").strip().lower().rstrip(":")
            if in_section and title != wanted:
                break
            in_section = title == wanted
            continue
        if in_section and line:
            lines.append(line.lstrip("- ").strip())
        if in_section and len(" ".join(lines)) >= max_chars:
            break
    return compact_inline_text(" ".join(lines), max_chars=max_chars) if lines else ""


def labeled_line_excerpt(
    text: str, labels: tuple[str, ...], *, max_chars: int = 220
) -> str:
    """Extract a compact labeled line from a student final message."""
    normalized_labels = tuple(label.lower().rstrip(":") for label in labels)
    for raw in text.splitlines():
        line = raw.strip().lstrip("- ").strip()
        if not line:
            continue
        low = line.lower()
        for label in normalized_labels:
            if low.startswith(label + ":"):
                return compact_inline_text(
                    line.split(":", 1)[1].strip(), max_chars=max_chars
                )
    for raw in text.splitlines():
        line = raw.strip()
        if line:
            return compact_inline_text(line, max_chars=max_chars)
    return "No concise report found."


def focused_message_excerpt(text: str, *, max_chars: int = 900) -> str:
    """Compatibility helper for execution.py with compact, non-redundant output."""
    per_field = max(160, max_chars // 4)
    fields = [
        (
            "mechanism",
            labeled_line_excerpt(
                text,
                ("Mechanism", "core idea", "Implemented", "Touched files"),
                max_chars=per_field,
            ),
        ),
        (
            "result",
            labeled_line_excerpt(
                text,
                ("Result", "Final canonical metrics", "metrics"),
                max_chars=per_field,
            ),
        ),
        (
            "next",
            labeled_line_excerpt(
                text,
                ("Next experiment", "Next uncertainty", "Next step"),
                max_chars=per_field,
            ),
        ),
    ]
    useful = [
        f"{label}: {value}"
        for label, value in fields
        if value and value != "No concise report found."
    ]
    if useful:
        return "\n".join(useful)
    return compact_inline_text(text, max_chars=max_chars)


def peer_mechanism_summary(
    *,
    runtime: Any,
    round_dir: Path,
    round_id: str,
    case_id: str,
    summary: MetricSummary,
) -> tuple[str, str, str]:
    """Summarize one peer in bounded text for student prompts.

    Full source/diff/card paths stay in peer_learning.md.  Student prompts only
    need enough evidence to decide what to inspect.
    """
    artifacts = candidate_artifacts(
        runtime=runtime,
        round_dir=round_dir,
        round_id=round_id,
        case_id=case_id,
        candidate=summary,
    )
    text = ""
    if artifacts and artifacts.knowledge_card.exists():
        text = artifacts.knowledge_card.read_text(encoding="utf-8", errors="replace")
        mechanism = markdown_section_excerpt(text, "Mechanism")
        lesson = markdown_section_excerpt(text, "Causal lesson")
        next_step = markdown_section_excerpt(text, "Next experiment")
        if mechanism or lesson or next_step:
            return (
                mechanism,
                lesson,
                next_step,
            )
    if artifacts and artifacts.last_message.exists():
        text = artifacts.last_message.read_text(encoding="utf-8", errors="replace")
    mechanism = labeled_line_excerpt(
        text,
        ("Mechanism", "core idea", "Implemented", "Touched files"),
    )
    lesson = labeled_line_excerpt(
        text,
        ("Causal lesson", "Next uncertainty", "Next step", "Result"),
    )
    next_step = labeled_line_excerpt(
        text,
        ("Next experiment", "Next uncertainty", "Next step"),
    )
    return mechanism, lesson, next_step


def peer_briefing(
    *,
    runtime: Any,
    round_dir: Path,
    case_id: str,
    flow_variant: str,
    iteration: int,
    current_student: str,
    student_runtime_multiplier: float = 2.0,
) -> str:
    if iteration <= 1:
        return render_prompt_template("context/no_prior_peer_results.md").strip()

    round_id = round_id_from_dir(round_dir)
    previous = iter_name(iteration - 1)
    baseline_metrics: dict[str, MetricSummary | None] = {}
    for line in CANONICAL_LINES:
        run_tag = f"{round_id}_baseline_probe_{line}"
        baseline_metrics[line] = summarize_metrics(
            expected_metrics_path(
                runtime=runtime,
                case_id=case_id,
                flow_variant=flow_variant,
                run_tag=run_tag,
            )
        )
    _baseline_label, baseline = value_reference_anchor(baseline_metrics)
    metrics_by_student: dict[str, MetricSummary] = {}
    invalid_rows: list[tuple[str, MetricSummary, list[str]]] = []
    for summary in discover_round_candidate_metrics(
        orfs_root=runtime.orfs_root,
        case_id=case_id,
        flow_variant=flow_variant,
        round_id=round_id,
    ):
        iter_part, student_id, _route_label = parse_candidate_tag(
            round_id, case_id, summary.tag
        )
        if iter_part == previous and student_id:
            problems = candidate_artifact_problems(
                runtime=runtime,
                round_dir=round_dir,
                round_id=round_id,
                case_id=case_id,
                candidate=summary,
            )
            if problems:
                invalid_rows.append((student_id, summary, problems))
                continue
            metrics_by_student[student_id] = summary

    if not metrics_by_student:
        invalid_note = ""
        if invalid_rows:
            invalid_note = "\n\n" + render_prompt_template(
                "context/invalid_prior_metric_rows.md",
                invalid_rows="; ".join(
                    f"{student_id}={candidate_artifact_status_text(problems)}"
                    for student_id, _summary, problems in invalid_rows[:4]
                ),
            )
        return render_prompt_template(
            "context/no_valid_prior_peer_metrics.md",
            previous_iteration=previous,
            invalid_note=invalid_note,
        )

    def peer_rank(student: str) -> tuple[float, float]:
        summary = metrics_by_student[student]
        hpwl_rank = (
            -float(summary.hpwl_after)
            if summary.hpwl_after is not None
            else float("-inf")
        )
        gain = hpwl_runtime_gain(summary, baseline)
        gain_rank = gain if gain is not None else float("-inf")
        return hpwl_rank, gain_rank

    best_student = max(metrics_by_student, key=peer_rank)
    lines = [
        render_prompt_template(
            "context/prior_peer_briefing_header.md",
            previous_iteration=previous,
            best_student=best_student,
        ).rstrip()
    ]
    for student_id in sorted(metrics_by_student):
        summary = metrics_by_student[student_id]
        label = "you" if student_id == current_student else "peer"
        hpwl = "" if summary.hpwl_after is None else f"{summary.hpwl_after:.3f}"
        runtime_s = (
            "" if summary.runtime_seconds is None else f"{summary.runtime_seconds:.3f}s"
        )
        avg_disp = "" if summary.avg_disp is None else f"{summary.avg_disp:.4f}"
        max_disp = "" if summary.max_disp is None else f"{summary.max_disp:.4f}"
        violations = summary.violations or "clean"
        gain_factors = hpwl_runtime_gain_factors(summary, baseline)
        gain_text = "" if gain_factors is None else f"{gain_factors['score']:.3f}"
        h_text = "" if gain_factors is None else f"{gain_factors['H']:.4f}"
        r_text = "" if gain_factors is None else f"{gain_factors['R']:.4f}"
        stage_pct = " / ".join(
            [
                "lg:"
                + (
                    ""
                    if summary.hpwl_stage_delta_legalization_percent is None
                    else f"{summary.hpwl_stage_delta_legalization_percent:.2f}%"
                ),
                "ip:"
                + (
                    ""
                    if summary.hpwl_stage_delta_improve_percent is None
                    else f"{summary.hpwl_stage_delta_improve_percent:.2f}%"
                ),
                "final:"
                + (
                    ""
                    if summary.hpwl_stage_delta_final_percent is None
                else f"{summary.hpwl_stage_delta_final_percent:.2f}%"
                ),
            ]
        )
        lines.append(
            "- {student} ({label}): analysis G_HR `{score}` HPWL_gain/runtime_penalty_pp `{h}/{r}`, "
            "HPWL `{hpwl}`, runtime `{runtime_s}`, "
            "avg/max disp `{avg_disp}/{max_disp}`, legality `{violations}`; "
            "stage `{stage_pct}`, signal `{signal}`".format(
                student=student_id,
                label=label,
                score=gain_text,
                h=h_text,
                r=r_text,
                hpwl=hpwl,
                runtime_s=runtime_s,
                avg_disp=avg_disp,
                max_disp=max_disp,
                violations=violations,
                stage_pct=stage_pct,
                signal=stage_donor_signal(
                    summary,
                    baseline,
                    budget_multiplier=student_runtime_multiplier,
                ),
            )
        )
    if invalid_rows:
        lines.append("")
        lines.append(
            render_prompt_template(
                "context/invalid_prior_metric_rows.md",
                invalid_rows="; ".join(
                    f"{student_id}={candidate_artifact_status_text(problems)}"
                    for student_id, _summary, problems in invalid_rows[:4]
                ),
            ).rstrip()
        )
    return "\n".join(lines)


def prior_iteration_context(
    *,
    runtime: Any,
    round_dir: Path,
    round_id: str,
    iteration: int,
    strategies: list[str],
) -> str:
    if iteration <= 1:
        return render_prompt_template("context/no_previous_iteration.md").strip()

    previous = iteration - 1
    review_op = f"{round_id}_{iter_name(previous)}_teacher_review"
    blocks = [
        render_prompt_template(
            "context/prior_iteration_context_header.md",
            previous_iteration=iter_name(previous),
            previous_teacher_review_artifact=operation_artifact_block(
                runtime, review_op
            ),
            previous_teacher_review_text=previous_teacher_review_text(
                runtime=runtime,
                round_id=round_id,
                iteration=iteration,
                warn_chars=12000,
            ),
        ).rstrip()
    ]
    for idx, route_label in enumerate(strategies, start=1):
        student_id = f"student_{idx:02d}"
        child_op = f"{round_id}_{iter_name(previous)}_{student_id}"
        blocks.append(
            render_prompt_template(
                "context/prior_child_artifact.md",
                student_id=student_id,
                route_label=route_label,
                operation_artifact=operation_artifact_block(runtime, child_op),
                lineage_path=round_dir / "students" / student_id / "lineage.json",
            ).rstrip()
        )
    return "\n".join(blocks)


def write_iteration_context(
    *,
    iteration_dir: Path,
    context: str,
) -> Path:
    context_dir = iteration_dir / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    path = context_dir / "iteration_context.md"
    path.write_text(context, encoding="utf-8")
    return path


def build_packet(
    *,
    agent_root: Path,
    case_id: str,
    packet_dir: Path,
) -> Path:
    problem_path = subprocess.check_output(
        [
            sys.executable,
            str(agent_root / "scripts" / "case_registry.py"),
            "--case",
            case_id,
            "--field",
            "problem",
        ],
        text=True,
        env=clean_subprocess_env(),
    ).strip()
    problem_dir = str(Path(problem_path).parent)
    subprocess.run(
        [
            sys.executable,
            str(agent_root / "adapters" / "science_codeevolve" / "kb_query.py"),
            "--problem_dir",
            problem_dir,
            "--out_dir",
            str(packet_dir),
        ],
        check=True,
        env=clean_subprocess_env(),
    )
    return packet_dir / "current_run_packet.md"


def common_context(
    *,
    case_id: str,
    flow_variant: str,
    threads: int,
    start_kind: str,
    runtime: Any,
    metrics: dict[str, MetricSummary | None],
    packet_path: Path,
    baseline_artifacts_path: Path,
    start_seed_calibration_path: Path,
    design_characteristics_path: Path,
    peer_learning_path: Path,
    round_id: str,
    iteration: int,
    prior_context: str,
    scoreboard: str,
    elite_seed_source: Path | None,
    student_runtime_multiplier: float,
) -> str:
    elite_text = (
        render_prompt_template("context/no_elite_seed.md").strip()
        if elite_seed_source is None
        else render_prompt_template(
            "context/elite_seed_context.md",
            elite_seed_source=elite_seed_source,
        )
    )
    context_template = (
        "context/common_context_followup.md"
        if iteration > 1
        else "context/common_context.md"
    )
    return render_prompt_template(
        context_template,
        case_id=case_id,
        flow_variant=flow_variant,
        threads=threads,
        start_kind=start_kind,
        round_id=round_id,
        iteration_name=iter_name(iteration),
        orfs_root=runtime.orfs_root,
        agent_root=runtime.agent_root,
        state_root=runtime.state_root,
        packet_path=packet_path,
        design_characteristics=design_characteristics_block(
            case_id=case_id,
            flow_variant=flow_variant,
            metrics=metrics,
        ),
        design_characteristics_path=design_characteristics_path,
        dpl_evolve_src=runtime.orfs_root
        / "tools"
        / "OpenROAD"
        / "src"
        / "dpl_evolve"
        / "src",
        legalm_guidance=runtime.agent_root / "family_variants" / "legalm_guidance",
        openroad_diamond=runtime.agent_root / "family_variants" / "openroad_diamond",
        openroad_negotiation_nblg=runtime.agent_root
        / "family_variants"
        / "openroad_negotiation_nblg",
        dreamplace_abacus=runtime.agent_root / "family_variants" / "dreamplace_abacus",
        evolved_legalizers_readme=runtime.agent_root
        / "patches"
        / "evolved_legalizers"
        / "README.md",
        evolved_legalizers_manifest=runtime.agent_root
        / "patches"
        / "evolved_legalizers"
        / "generation_manifest.tsv",
        evolved_legalizers_validation=runtime.agent_root
        / "patches"
        / "evolved_legalizers"
        / "validation.tsv",
        dense_legalizer_routing_insight=runtime.agent_root
        / "knowledge"
        / "insights"
        / "case_evolution"
        / "dense_evolved_legalizer_routing.md",
        strategy_inspiration_insight=runtime.agent_root
        / "knowledge"
        / "insights"
        / "case_evolution"
        / "strategy_inspiration_by_design_feature.md",
        dpo_source_mechanisms_insight=runtime.agent_root
        / "knowledge"
        / "insights"
        / "dpo"
        / "source_level_mechanisms.md",
        openroad_native_handoff_insight=runtime.agent_root
        / "knowledge"
        / "insights"
        / "dpo"
        / "openroad_native_handoff.md",
        skill_index=runtime.agent_root / "knowledge" / "index" / "skill_cards.jsonl",
        skill_query_script=runtime.agent_root / "scripts" / "query_knowledge.py",
        skill_cards_dir=runtime.agent_root / "knowledge" / "skills",
        algorithm_cards_dir=runtime.agent_root / "knowledge" / "algorithm_cards",
        teacher_coaching_skill=runtime.agent_root
        / "skills"
        / "teacher_peer_coaching.md",
        metric_table=metric_table(metrics),
        scoreboard=scoreboard,
        elite_text=elite_text,
        baseline_artifacts_path=baseline_artifacts_path,
        start_seed_calibration_path=start_seed_calibration_path,
        peer_learning_path=peer_learning_path,
        prior_context=prior_context,
        student_runtime_multiplier=format_multiplier(student_runtime_multiplier),
    )


def teacher_prompt(
    *,
    context_path: Path,
    current_run_packet_path: Path,
    design_characteristics_path: Path,
    baseline_artifacts_path: Path,
    peer_learning_path: Path,
    start_seed_calibration_path: Path,
    strategies: list[str],
    children: int,
    iteration: int,
    student_runtime_multiplier: float,
) -> str:
    student_roster = "\n".join(
        render_prompt_template(
            "teacher/student_roster_line.md",
            student_id=f"student_{idx:02d}",
        ).rstrip()
        for idx in range(1, children + 1)
    )
    route_lines = "\n".join(
        render_prompt_template(
            "teacher/student_slot_line.md",
            student_id=f"student_{idx:02d}",
        ).rstrip()
        for idx, _name in enumerate(strategies, start=1)
    )
    return render_prompt_template(
        "teacher/plan.md",
        context_path=context_path,
        current_run_packet_path=current_run_packet_path,
        design_characteristics_path=design_characteristics_path,
        baseline_artifacts_path=baseline_artifacts_path,
        peer_learning_path=peer_learning_path,
        start_seed_calibration_path=start_seed_calibration_path,
        iteration_name=iter_name(iteration),
        route_lines=route_lines,
        student_roster=student_roster,
        teacher_rules=render_prompt_template(
            "teacher/rules.md",
            student_runtime_multiplier=format_multiplier(student_runtime_multiplier),
        ),
        teacher_plan_output=render_prompt_template(
            "teacher/plan_output.md",
            student_insight_packet_format=render_prompt_template(
                "shared/student_insight_packet_format.md"
            ),
        ),
        children=children,
    )


def compact_teacher_prompt(
    *,
    context_path: Path,
    current_run_packet_path: Path,
    design_characteristics_path: Path,
    baseline_artifacts_path: Path,
    peer_learning_path: Path,
    start_seed_calibration_path: Path,
    strategies: list[str],
    children: int,
    iteration: int,
    student_runtime_multiplier: float,
) -> str:
    student_roster = "\n".join(
        render_prompt_template(
            "teacher/student_roster_line.md",
            student_id=f"student_{idx:02d}",
        ).rstrip()
        for idx in range(1, children + 1)
    )
    route_lines = "\n".join(
        render_prompt_template(
            "teacher/student_slot_line.md",
            student_id=f"student_{idx:02d}",
        ).rstrip()
        for idx, _name in enumerate(strategies, start=1)
    )
    return render_prompt_template(
        "teacher/plan_compact.md",
        context_path=context_path,
        current_run_packet_path=current_run_packet_path,
        design_characteristics_path=design_characteristics_path,
        baseline_artifacts_path=baseline_artifacts_path,
        peer_learning_path=peer_learning_path,
        start_seed_calibration_path=start_seed_calibration_path,
        iteration_name=iter_name(iteration),
        route_lines=route_lines,
        student_roster=student_roster,
        teacher_rules=render_prompt_template(
            "teacher/rules_followup.md",
            student_runtime_multiplier=format_multiplier(student_runtime_multiplier),
        ),
        teacher_plan_output=render_prompt_template(
            "teacher/plan_output.md",
            student_insight_packet_format=render_prompt_template(
                "shared/student_insight_packet_format.md"
            ),
        ),
        children=children,
    )


def teacher_review_prompt(
    *,
    context_path: Path,
    review_packet_path: Path,
    student_runtime_multiplier: float,
) -> str:
    return render_prompt_template(
        "teacher/review.md",
        context_path=context_path,
        review_packet_path=review_packet_path,
        teacher_review_rules=render_prompt_template(
            "teacher/review_rules.md",
            student_runtime_multiplier=format_multiplier(student_runtime_multiplier),
        ),
        teacher_review_output=render_prompt_template(
            "teacher/review_output.md",
            student_insight_packet_format=render_prompt_template(
                "shared/student_insight_packet_format.md"
            ),
        ),
    )


def compact_teacher_review_prompt(
    *,
    context_path: Path,
    review_packet_path: Path,
    student_runtime_multiplier: float,
) -> str:
    return render_prompt_template(
        "teacher/review_compact.md",
        context_path=context_path,
        review_packet_path=review_packet_path,
        teacher_review_rules=render_prompt_template(
            "teacher/review_rules_followup.md",
            student_runtime_multiplier=format_multiplier(student_runtime_multiplier),
        ),
        teacher_review_output=render_prompt_template(
            "teacher/review_output.md",
            student_insight_packet_format=render_prompt_template(
                "shared/student_insight_packet_format.md"
            ),
        ),
    )


def start_kind_source(runtime: Any, start_kind: str) -> Path:
    if start_kind == "framework":
        return runtime.state_root / "seed_sources" / "framework_dpl_evolve"
    if start_kind == "diamond":
        return runtime.state_root / "seed_sources" / "diamond_dpl_evolve"
    if start_kind == "evolved_diamond":
        return runtime.state_root / "seed_sources" / "evolved_diamond_dpl_evolve"
    if start_kind == "evolved_legalm":
        return runtime.state_root / "seed_sources" / "evolved_legalm_dpl_evolve"
    if start_kind == "evolved_negotiation":
        return runtime.state_root / "seed_sources" / "evolved_negotiation_dpl_evolve"
    if start_kind == "prepared":
        return runtime.orfs_root / "tools" / "OpenROAD" / "src" / "dpl_evolve"
    raise ValueError(f"unsupported start_kind: {start_kind}")


def validate_start_kind_seed(runtime: Any, start_kind: str) -> tuple[bool, Path]:
    source = start_kind_source(runtime, start_kind)
    return (source / "CMakeLists.txt").is_file(), source


def child_evaluation_timeout(
    *,
    runtime: Any,
    case_id: str,
    flow_variant: str,
    round_id: str,
    runtime_multiplier: float,
    baseline_metrics: dict[str, MetricSummary | None] | None = None,
) -> tuple[int | None, str]:
    """Return the hard DPL flow timeout from canonical reported runtime."""
    summary = None
    if baseline_metrics is not None:
        summary = baseline_metrics.get("openroad_dpl_flow")
    runtime_s = summary.runtime_seconds if summary is not None else None
    if runtime_s is not None and runtime_s > 0:
        baseline_path = summary.metrics_path
    else:
        baseline_path = None

    baseline_tag = f"{round_id}_baseline_probe_openroad_dpl_flow"
    fallback_path = expected_metrics_path(
        runtime=runtime,
        case_id=case_id,
        flow_variant=flow_variant,
        run_tag=baseline_tag,
    )
    if runtime_s is None or runtime_s <= 0:
        baseline = summarize_metrics(fallback_path)
        runtime_s = baseline.runtime_seconds if baseline is not None else None
        baseline_path = fallback_path
    if runtime_s is None or runtime_s <= 0:
        return (
            None,
            "Unavailable: canonical openroad_dpl_flow reported runtime is missing. "
            f"Run baseline preflight first. Expected metrics: `{fallback_path}`",
        )
    multiplier_label = format_multiplier(runtime_multiplier)
    timeout_s = max(1, int(math.ceil(runtime_s * runtime_multiplier)))
    return (
        timeout_s,
        "DPL flow timeout: "
        f"`{timeout_s}s` = {multiplier_label}x canonical openroad_dpl_flow reported runtime "
        f"`{runtime_s:.3f}s` from the canonical baseline `metrics.json:runtime_seconds`. "
        "The timeout is applied only to the OpenROAD legalize/improve/mirror flow run; "
        "post-run metrics/evaluator collection is not timeout-wrapped, so timeout failures "
        "should still write metrics.json failure evidence when possible.  Runtime below the "
        "limit is acceptable when it buys cached, capped, explainable HPWL-source search; "
        "DPL-flow-timeout runs are non-promotable.",
    )


def child_parent_source(
    *,
    runtime: Any,
    round_dir: Path,
    iteration: int,
    student_id: str,
    stable_workspace: bool,
    elite_seed_source: Path | None,
    start_kind: str,
) -> Path:
    if elite_seed_source is not None:
        return elite_seed_source
    if iteration > 1:
        if stable_workspace:
            return (
                round_dir
                / "students"
                / student_id
                / "workspace"
                / "variant"
                / "dpl_evolve"
            )
        return student_workspace_paths(
            round_dir=round_dir,
            iteration=iteration - 1,
            student_id=student_id,
            stable_workspace=stable_workspace,
        ).dpl_src
    return start_kind_source(runtime, start_kind)


def write_executable_script(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def write_student_workspace_scripts(
    *,
    runtime: Any,
    paths: StudentWorkspace,
    case_id: str,
    flow_variant: str,
    threads: int,
    start_kind: str,
    run_tag: str,
    parent_src: Path,
    use_seed_override: bool,
    timeout_seconds: int | None,
) -> dict[str, Path]:
    """Write fixed helper scripts into the Student workspace.

    The Student should spend context on source behavior, not on reconstructing
    relink/evaluator/git boilerplate.  These scripts are intentionally verbose
    in names and short in logic so failures are easy to report.
    """
    script_dir = paths.student_workspace / "scripts" / paths.source_branch.split("/")[-1]
    metrics_path = expected_metrics_path(
        runtime=runtime,
        case_id=case_id,
        flow_variant=flow_variant,
        run_tag=run_tag,
    )
    seed_lines = (
        '  --seed-src "$PARENT_SRC" \\\n'
        '  --force \\\n'
        if use_seed_override
        else ""
    )
    legalize_timeout_arg = (
        f'  --legalize-timeout-seconds {timeout_seconds} \\\n'
        if timeout_seconds is not None
        else ""
    )

    common_vars = f"""AGENT_ROOT={shlex.quote(str(runtime.agent_root))}
ORFS_ROOT={shlex.quote(str(runtime.orfs_root))}
VARIANT_ROOT={shlex.quote(str(paths.variant_root))}
DPL_SRC={shlex.quote(str(paths.dpl_src))}
PRIVATE_BINARY={shlex.quote(str(paths.private_binary))}
ARTIFACT_DIR={shlex.quote(str(paths.artifact_dir))}
SOURCE_BRANCH={shlex.quote(paths.source_branch)}
CANDIDATE_SOURCE_REF={shlex.quote(stable_candidate_ref(run_tag))}
SOURCE_BASE_RECORD={shlex.quote(str(paths.source_base_record))}
SOURCE_COMMIT_RECORD={shlex.quote(str(paths.source_commit_record))}
METRICS_SUMMARY_JSON={shlex.quote(str(paths.candidate_metrics_summary_json))}
METRICS_SUMMARY_MD={shlex.quote(str(paths.candidate_metrics_summary_md))}
IMPLEMENTATION_DIFF={shlex.quote(str(paths.implementation_diff))}
KNOWLEDGE_CARD={shlex.quote(str(paths.knowledge_card))}
THREADS={shlex.quote(str(threads))}
CASE_ID={shlex.quote(case_id)}
FLOW_VARIANT={shlex.quote(flow_variant)}
RUN_TAG={shlex.quote(run_tag)}
START_KIND={shlex.quote(start_kind)}
PARENT_SRC={shlex.quote(str(parent_src))}
METRICS_PATH={shlex.quote(str(metrics_path))}

ensure_dpl_git_repo() {{
  local top
  top="$(git -C "$DPL_SRC" rev-parse --show-toplevel 2>/dev/null || true)"
  top="$(realpath -m "$top")"
  if [[ "$top" != "$(realpath -m "$DPL_SRC")" ]]; then
    echo "[ERROR] private source is not an independent git repo: $DPL_SRC top=$top" >&2
    exit 2
  fi
}}

acquire_workspace_git_lock() {{
  if [[ "${{DPL_EVOLVE_WORKSPACE_LOCK_HELD:-0}}" == "1" ]]; then
    return 0
  fi
  mkdir -p "$VARIANT_ROOT"
  exec 9>"$VARIANT_ROOT/.workspace_git.lock"
  if ! flock -n 9; then
    echo "[ERROR] another generated workspace helper is already mutating this private source." >&2
    echo "[INFO] Run dependent helpers serially: prepare/switch/build/evaluate/checkpoint/preserve/commit/diff." >&2
    exit 2
  fi
}}

assert_no_git_index_lock() {{
  if [[ -e "$DPL_SRC/.git/index.lock" ]]; then
    echo "[ERROR] git index lock exists in private source: $DPL_SRC/.git/index.lock" >&2
    echo "[INFO] Do not run prepare/switch/build/evaluate/checkpoint/preserve/commit helpers in parallel." >&2
    echo "[INFO] If no helper process is active, remove the stale lock manually after inspecting processes." >&2
    exit 2
  fi
}}
"""

    scripts = {
        "prepare": script_dir / "00_prepare_source.sh",
        "prepare_start_source": script_dir / "01_prepare_start_source.sh",
        "source_status": script_dir / "02_source_status.sh",
        "peer_source": script_dir / "03_fetch_peer_source.sh",
        "switch_start_branch": script_dir / "04_switch_start_branch.sh",
        "source_context": script_dir / "05_source_context.sh",
        "query_knowledge": script_dir / "08_query_knowledge.sh",
        "build": script_dir / "10_build_variant.sh",
        "fresh_build": script_dir / "11_build_variant_fresh.sh",
        "evaluate": script_dir / "20_evaluate_candidate.sh",
        "report_metrics": script_dir / "21_report_candidate_metrics.sh",
        "keep_and_finalize": script_dir / "22_keep_and_finalize.sh",
        "trial": script_dir / "25_trial_source.sh",
        "finalize": script_dir / "30_finalize_source.sh",
        "after_edit": script_dir / "run_after_edit.sh",
    }

    write_executable_script(
        scripts["prepare"],
        f"""#!/usr/bin/env bash
	set -euo pipefail
{common_vars}
acquire_workspace_git_lock
mkdir -p "$VARIANT_ROOT" "$ARTIFACT_DIR"
assert_no_git_index_lock
"$AGENT_ROOT/scripts/create_variant_start.sh" \\
  --orfs-root "$ORFS_ROOT" \\
  --variant-root "$VARIANT_ROOT" \\
  --start-kind "$START_KIND" \\
  --dpl-src "$DPL_SRC" \\
{seed_lines}  --git-branch "$SOURCE_BRANCH"
ensure_dpl_git_repo
assert_no_git_index_lock
current_branch="$(git -C "$DPL_SRC" branch --show-current)"
if [[ "$current_branch" != "$SOURCE_BRANCH" ]]; then
  echo "[ERROR] expected source branch $SOURCE_BRANCH, got $current_branch" >&2
  exit 2
fi

seed_for_kind() {{
  case "$1" in
    framework)
      printf '%s\\n' "$AGENT_ROOT/.dpl_evolve_state/seed_sources/framework_dpl_evolve"
      ;;
    diamond)
      printf '%s\\n' "$AGENT_ROOT/.dpl_evolve_state/seed_sources/diamond_dpl_evolve"
      ;;
    evolved_diamond)
      printf '%s\\n' "$AGENT_ROOT/.dpl_evolve_state/seed_sources/evolved_diamond_dpl_evolve"
      ;;
    evolved_legalm)
      printf '%s\\n' "$AGENT_ROOT/.dpl_evolve_state/seed_sources/evolved_legalm_dpl_evolve"
      ;;
    evolved_negotiation)
      printf '%s\\n' "$AGENT_ROOT/.dpl_evolve_state/seed_sources/evolved_negotiation_dpl_evolve"
      ;;
    *)
      return 2
      ;;
  esac
}}

materialize_start_branch() {{
  local kind="$1"
  local branch="start/$kind"
  local seed
  local tmp_branch
  seed="$(seed_for_kind "$kind")"
  if [[ ! -f "$seed/CMakeLists.txt" ]]; then
    echo "[WARN] cannot prepare $branch; missing seed: $seed" >&2
    return 0
  fi
  tmp_branch="__dpl_evolve_seed_${{kind}}_$$"
  git -C "$DPL_SRC" switch --orphan "$tmp_branch" >/dev/null
  git -C "$DPL_SRC" rm -r --cached . >/dev/null 2>&1 || true
  find "$DPL_SRC" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {{}} +
  rsync -a --delete --exclude='.git' "$seed/" "$DPL_SRC/"
  git -C "$DPL_SRC" add -A
  git -C "$DPL_SRC" commit -m "Seed $branch source" >/dev/null
  git -C "$DPL_SRC" branch -M "$branch"
  echo "[INFO] prepared_start_branch=$branch commit=$(git -C "$DPL_SRC" rev-parse HEAD)"
}}

prepare_start_branches() {{
  if [[ -n "$(git -C "$DPL_SRC" status --short)" ]]; then
    echo "[WARN] private source is dirty; skip start branch materialization" >&2
    return 0
  fi
  local return_branch
  return_branch="$(git -C "$DPL_SRC" branch --show-current)"
  if [[ "$return_branch" != "$SOURCE_BRANCH" ]]; then
    echo "[WARN] current branch is $return_branch, expected $SOURCE_BRANCH; skip start branch materialization" >&2
    return 0
  fi
  for kind in framework diamond evolved_diamond evolved_legalm evolved_negotiation; do
    materialize_start_branch "$kind"
  done
  git -C "$DPL_SRC" switch "$SOURCE_BRANCH" >/dev/null
  echo "[INFO] available_start_branches:"
  git -C "$DPL_SRC" for-each-ref --format='[INFO]   %(refname:short) %(objectname:short)' refs/heads/start/
}}

prepare_start_branches
git -C "$DPL_SRC" rev-parse HEAD > "$SOURCE_BASE_RECORD"
echo "[INFO] source=$DPL_SRC"
echo "[INFO] branch=$current_branch"
echo "[INFO] base_commit=$(cat "$SOURCE_BASE_RECORD")"
		""",
    )

    write_executable_script(
        scripts["prepare_start_source"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"

kind=""
usage() {{
  cat >&2 <<'USAGE'
Usage:
  01_prepare_start_source.sh --kind <prepared-start-kind>

Atomically run source preparation and switch to the Teacher-assigned prepared
start branch. Use this instead of launching 00_prepare_source.sh and
04_switch_start_branch.sh separately when Teacher assigns a start point.
USAGE
}}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --kind)
      kind="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$kind" ]]; then
  echo "[ERROR] missing --kind" >&2
  usage
  exit 2
fi

acquire_workspace_git_lock
assert_no_git_index_lock
DPL_EVOLVE_WORKSPACE_LOCK_HELD=1 "$SCRIPT_DIR/00_prepare_source.sh"
assert_no_git_index_lock
DPL_EVOLVE_WORKSPACE_LOCK_HELD=1 "$SCRIPT_DIR/04_switch_start_branch.sh" --kind "$kind"
""",
    )

    write_executable_script(
        scripts["source_status"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
if [[ ! -d "$DPL_SRC/.git" ]]; then
  echo "[INFO] source repo is not prepared yet: $DPL_SRC"
  echo "[INFO] run 00_prepare_source.sh or 01_prepare_start_source.sh first"
  exit 0
fi
ensure_dpl_git_repo
echo "[INFO] source=$DPL_SRC"
echo "[INFO] expected_source_branch=$SOURCE_BRANCH"
echo "[INFO] current_branch=$(git -C "$DPL_SRC" branch --show-current)"
echo "[INFO] head=$(git -C "$DPL_SRC" rev-parse --short HEAD) $(git -C "$DPL_SRC" log -1 --pretty=%s)"
if [[ -s "$SOURCE_BASE_RECORD" ]]; then
  echo "[INFO] source_base_commit=$(head -n 1 "$SOURCE_BASE_RECORD")"
else
  echo "[INFO] source_base_commit=<not recorded yet>"
fi
if git -C "$DPL_SRC" show-ref --verify --quiet "refs/heads/$CANDIDATE_SOURCE_REF"; then
  echo "[INFO] stable_candidate_ref=$CANDIDATE_SOURCE_REF $(git -C "$DPL_SRC" rev-parse --short "$CANDIDATE_SOURCE_REF")"
else
  echo "[INFO] stable_candidate_ref=$CANDIDATE_SOURCE_REF <not pinned yet>"
fi
echo "[INFO] source status:"
git -C "$DPL_SRC" status --short
echo "[INFO] iteration branches:"
git -C "$DPL_SRC" for-each-ref --format='[INFO]   %(refname:short) %(objectname:short) %(subject)' "refs/heads/agent/" | tail -20 || true
echo "[INFO] candidate refs:"
git -C "$DPL_SRC" for-each-ref --format='[INFO]   %(refname:short) %(objectname:short) %(subject)' "refs/heads/candidate/" | tail -20 || true
echo "[INFO] start branches:"
git -C "$DPL_SRC" for-each-ref --format='[INFO]   %(refname:short) %(objectname:short) %(subject)' "refs/heads/start/" || true
""",
    )

    write_executable_script(
        scripts["peer_source"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
peer_repo=""
peer_ref=""
label=""
paths=()

usage() {{
  cat >&2 <<'USAGE'
Usage:
  03_fetch_peer_source.sh --peer-repo <repo> --peer-ref <ref> [--label <name>] [--path <src/path> ...]

Fetch another Student's evaluated source ref into this local repo as
peer/<label>, then write a diff summary under this iteration's artifacts.
This helper does not modify the working tree. Use it to inspect and migrate
selected mechanisms onto the current iteration branch.
USAGE
}}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --peer-repo)
      peer_repo="$2"
      shift 2
      ;;
    --peer-ref)
      peer_ref="$2"
      shift 2
      ;;
    --label)
      label="$2"
      shift 2
      ;;
    --path)
      paths+=("$2")
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$peer_repo" || -z "$peer_ref" ]]; then
  echo "[ERROR] --peer-repo and --peer-ref are required" >&2
  usage
  exit 2
fi

acquire_workspace_git_lock
ensure_dpl_git_repo
assert_no_git_index_lock
peer_repo="$(realpath -m "$peer_repo")"
if [[ ! -d "$peer_repo/.git" ]]; then
  echo "[ERROR] peer repo is not a local git repo: $peer_repo" >&2
  exit 2
fi

if [[ -z "$label" ]]; then
  label="$(basename "$(dirname "$peer_repo")")_$(basename "$peer_ref")"
fi
safe_label="$(python3 - "$label" <<'PY'
import re
import sys

label = sys.argv[1]
safe = re.sub(r"[^A-Za-z0-9._-]+", "_", label).strip("._-")
print(safe or "peer_source")
PY
)"
peer_branch="peer/$safe_label"
git -C "$DPL_SRC" check-ref-format --branch "$peer_branch" >/dev/null
git -C "$DPL_SRC" fetch --no-tags "$peer_repo" "+$peer_ref:refs/heads/$peer_branch" >/dev/null
peer_commit="$(git -C "$DPL_SRC" rev-parse "$peer_branch")"

out_dir="$ARTIFACT_DIR/peer_imports"
mkdir -p "$out_dir"
summary="$out_dir/${{safe_label}}.summary.txt"
diff_path="$out_dir/${{safe_label}}.diff"

{{
  echo "[INFO] source=$DPL_SRC"
  echo "[INFO] current_branch=$(git -C "$DPL_SRC" branch --show-current)"
  echo "[INFO] local_peer_ref=$peer_branch"
  echo "[INFO] peer_repo=$peer_repo"
  echo "[INFO] peer_ref=$peer_ref"
  echo "[INFO] peer_commit=$peer_commit"
  if [[ "${{#paths[@]}}" -gt 0 ]]; then
    printf '[INFO] path_filters='
    printf '%s ' "${{paths[@]}}"
    printf '\\n'
  else
    echo "[INFO] path_filters=<all>"
  fi
  echo "[INFO] diff stat:"
  git -C "$DPL_SRC" diff --stat HEAD.."$peer_branch" -- "${{paths[@]}}" || true
  echo "[INFO] changed files:"
  git -C "$DPL_SRC" diff --name-status HEAD.."$peer_branch" -- "${{paths[@]}}" || true
}} | tee "$summary"

git -C "$DPL_SRC" diff --no-ext-diff HEAD.."$peer_branch" -- "${{paths[@]}}" > "$diff_path" || true
echo "[INFO] peer_summary=$summary"
echo "[INFO] peer_diff=$diff_path"
echo "[INFO] inspect_file_example=git -C '$DPL_SRC' show '$peer_branch:src/Optdp.cpp'"
echo "[INFO] migrate selectively on $SOURCE_BRANCH, then build/evaluate before final commit."
""",
    )

    write_executable_script(
        scripts["switch_start_branch"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
acquire_workspace_git_lock
ensure_dpl_git_repo
assert_no_git_index_lock

kind=""
usage() {{
  cat >&2 <<'USAGE'
Usage:
  04_switch_start_branch.sh --kind <prepared-start-kind>

Reset the iteration source branch to one prepared local start branch. Examples:
  framework
  diamond
  evolved_legalm

Run this after 00_prepare_source.sh and before source edits when Teacher
assigns a different start point for this Student.
USAGE
}}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --kind)
      kind="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$kind" || "$kind" == */* ]]; then
  echo "[ERROR] expected --kind to be one prepared start branch suffix without '/'" >&2
  usage
  exit 2
fi
branch="start/$kind"

if [[ -n "$(git -C "$DPL_SRC" status --short)" ]]; then
  echo "[ERROR] private source has uncommitted changes; switch start branch only before edits." >&2
  git -C "$DPL_SRC" status --short >&2
  exit 2
fi
if ! git -C "$DPL_SRC" show-ref --verify --quiet "refs/heads/$branch"; then
  echo "[ERROR] missing prepared start branch $branch; run 00_prepare_source.sh first." >&2
  echo "[INFO] existing start branches:" >&2
  git -C "$DPL_SRC" for-each-ref --format='  %(refname:short)' refs/heads/start/ >&2 || true
  exit 2
fi

git -C "$DPL_SRC" switch -C "$SOURCE_BRANCH" "$branch" >/dev/null
git -C "$DPL_SRC" rev-parse HEAD > "$SOURCE_BASE_RECORD"
python3 - "$ARTIFACT_DIR/start_branch.json" "$kind" "$branch" "$(git -C "$DPL_SRC" rev-parse HEAD)" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
payload = {{
    "active_start_kind": sys.argv[2],
    "active_start_branch": sys.argv[3],
    "active_start_commit": sys.argv[4],
}}
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
PY
echo "[INFO] switched source_branch=$SOURCE_BRANCH from $branch"
echo "[INFO] base_commit=$(cat "$SOURCE_BASE_RECORD")"
""",
    )

    write_executable_script(
        scripts["source_context"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
ensure_dpl_git_repo
cd "$DPL_SRC"

usage() {{
  cat >&2 <<'USAGE'
Usage:
  05_source_context.sh <module-relative-file> [symbol-or-text]
  05_source_context.sh <module-relative-file> --symbol <symbol-or-text>

Examples:
  05_source_context.sh src/Optdp.cpp improvePlacement
  05_source_context.sh src/Optdp.cpp --symbol improvePlacement
  05_source_context.sh src/optimization/detailed_manager.h DetailedMgr

This script only prints current local source context for edit anchoring.
Use the excerpt to make coherent mechanism-level source edits when justified by
the Teacher route and your diagnosis.
USAGE
}}

if [[ "$#" -lt 1 ]]; then
  usage
  exit 2
fi

file="$1"
shift || true

symbol=""
if [[ "$#" -gt 0 ]]; then
  case "$1" in
    --symbol|-s)
      shift
      if [[ "$#" -lt 1 ]]; then
        echo "[ERROR] --symbol requires a value" >&2
        usage
        exit 2
      fi
      symbol="$1"
      shift || true
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --*)
      echo "[ERROR] unknown option: $1" >&2
      usage
      exit 2
      ;;
    *)
      symbol="$1"
      shift || true
      ;;
  esac
fi

if [[ ! -f "$file" ]]; then
  echo "[ERROR] source file not found under private_dpl_evolve_source: $file" >&2
  echo "[INFO] close module-relative matches:" >&2
  rg --files | rg --fixed-strings -- "$file" >&2 || true
  base="$(basename "$file")"
  if [[ "$base" != "$file" ]]; then
    rg --files | rg --fixed-strings -- "$base" >&2 || true
  fi
  exit 2
fi

echo "[INFO] source=$DPL_SRC"
echo "[INFO] file=$file"

if [[ -z "$symbol" ]]; then
  echo "[INFO] no symbol provided; listing likely declarations/functions"
  rg -n '^[[:space:]]*(class|struct|enum|namespace|[A-Za-z_][A-Za-z_0-9:<>~*&[:space:]]+[[:space:]]+[A-Za-z_~][A-Za-z_0-9:~]*[[:space:]]*\\(|[A-Za-z_][A-Za-z_0-9:~]*::[A-Za-z_~][A-Za-z_0-9:~]*[[:space:]]*\\()' "$file" | head -120 || true
  exit 0
fi

echo "[INFO] symbol=$symbol"
match_lines="$(rg -n --fixed-strings -- "$symbol" "$file" || true)"
if [[ -z "$match_lines" ]]; then
  match_lines="$(rg -n -- "$symbol" "$file" || true)"
fi

if [[ -z "$match_lines" ]]; then
  echo "[WARN] symbol/text not found in $file: $symbol" >&2
  echo "[INFO] likely declarations/functions:" >&2
  rg -n '^[[:space:]]*(class|struct|enum|namespace|[A-Za-z_][A-Za-z_0-9:<>~*&[:space:]]+[[:space:]]+[A-Za-z_~][A-Za-z_0-9:~]*[[:space:]]*\\(|[A-Za-z_][A-Za-z_0-9:~]*::[A-Za-z_~][A-Za-z_0-9:~]*[[:space:]]*\\()' "$file" | head -120 >&2 || true
  exit 1
fi

echo "$match_lines" | head -20
first_line="$(printf '%s\\n' "$match_lines" | head -1 | cut -d: -f1)"
if [[ "$first_line" =~ ^[0-9]+$ ]]; then
  start=$(( first_line > 35 ? first_line - 35 : 1 ))
  end=$(( first_line + 100 ))
  echo "[INFO] excerpt lines $start..$end"
  nl -ba "$file" | sed -n "${{start}},${{end}}p"
else
  echo "[WARN] could not compute excerpt line for $symbol" >&2
fi
	""",
    )

    write_executable_script(
        scripts["query_knowledge"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
exec python3 "$AGENT_ROOT/scripts/query_knowledge.py" "$@"
""",
    )

    write_executable_script(
        scripts["build"],
        f"""#!/usr/bin/env bash
        set -euo pipefail
{common_vars}
acquire_workspace_git_lock
ensure_dpl_git_repo
assert_no_git_index_lock
"$AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \\
  --variant-root "$VARIANT_ROOT" \\
  --dpl-src "$DPL_SRC"
"$AGENT_ROOT/scripts/build_openroad_variant_relink.sh" \\
  --variant-root "$VARIANT_ROOT" \\
  --dpl-src "$DPL_SRC" \\
  --threads "$THREADS"
test -x "$PRIVATE_BINARY"
echo "[INFO] private_binary=$PRIVATE_BINARY"
""",
    )

    write_executable_script(
        scripts["fresh_build"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
acquire_workspace_git_lock
ensure_dpl_git_repo
assert_no_git_index_lock
FRESH_BUILD_DIR="$VARIANT_ROOT/build_fresh"
"$AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \\
  --variant-root "$VARIANT_ROOT" \\
  --build-dir "$FRESH_BUILD_DIR" \\
  --dpl-src "$DPL_SRC"
"$AGENT_ROOT/scripts/build_openroad_variant_relink.sh" \\
  --variant-root "$VARIANT_ROOT" \\
  --build-dir "$FRESH_BUILD_DIR" \\
  --dpl-src "$DPL_SRC" \\
  --threads "$THREADS"
test -x "$PRIVATE_BINARY"
echo "[INFO] private_binary=$PRIVATE_BINARY"
""",
    )

    write_executable_script(
        scripts["evaluate"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
acquire_workspace_git_lock
ensure_dpl_git_repo
assert_no_git_index_lock
RUN_BASELINE="$AGENT_ROOT/baseline/run_baseline.sh"
mkdir -p "$ARTIFACT_DIR"
set +e
"$RUN_BASELINE" \\
  --line evolve_default \\
  --case "$CASE_ID" \\
  --flow-variant "$FLOW_VARIANT" \\
  --threads "$THREADS" \\
  --openroad-binary "$PRIVATE_BINARY" \\
{legalize_timeout_arg}\
  --run-tag "$RUN_TAG"
status=$?
set -e
echo "$status" > "$ARTIFACT_DIR/evaluate_exit_status.txt"
if [[ "$status" -ne 0 ]]; then
  ATTEMPT_STATUS="$status" ATTEMPT_METRICS="$METRICS_PATH" ATTEMPT_TAG="$RUN_TAG" python3 - "$ARTIFACT_DIR/failed_attempts.jsonl" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
metrics_path = Path(os.environ["ATTEMPT_METRICS"])
payload = {{
    "run_tag": os.environ["ATTEMPT_TAG"],
    "exit_status": int(os.environ["ATTEMPT_STATUS"]),
    "metrics_path": str(metrics_path),
    "metrics_exists": metrics_path.exists(),
}}
if metrics_path.exists():
    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        payload["status"] = metrics.get("status")
        payload["failure"] = metrics.get("failure")
        payload["runtime_seconds"] = metrics.get("runtime_seconds")
    except Exception as exc:
        payload["metrics_parse_error"] = str(exc)
with path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(payload, sort_keys=True) + "\\n")
PY
  echo "[ERROR] DPL flow/evaluation wrapper returned status $status" >&2
  exit "$status"
fi
if [[ ! -f "$METRICS_PATH" ]]; then
  echo "[ERROR] evaluator succeeded but metrics.json is missing: $METRICS_PATH" >&2
  exit 2
fi
echo "[INFO] metrics=$METRICS_PATH"
"$SCRIPT_DIR/21_report_candidate_metrics.sh"
""",
    )

    write_executable_script(
        scripts["report_metrics"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
mkdir -p "$ARTIFACT_DIR"
if [[ ! -f "$METRICS_PATH" ]]; then
  echo "[ERROR] metrics json missing: $METRICS_PATH" >&2
  exit 2
fi
python3 "$AGENT_ROOT/scripts/report_candidate_metrics.py" \\
  --metrics "$METRICS_PATH" \\
  --output-json "$METRICS_SUMMARY_JSON" \\
  --output-md "$METRICS_SUMMARY_MD" >/dev/null
echo "[INFO] metrics_summary_json=$METRICS_SUMMARY_JSON"
echo "[INFO] metrics_summary_md=$METRICS_SUMMARY_MD"
""",
    )

    write_executable_script(
        scripts["keep_and_finalize"],
        """#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" != "--reason" || "$#" -lt 2 ]]; then
  echo "Usage: 22_keep_and_finalize.sh --reason <why-kept>" >&2
  exit 2
fi
reason="$2"
"$SCRIPT_DIR/25_trial_source.sh" keep --reason "$reason"
"$SCRIPT_DIR/30_finalize_source.sh"
""",
    )

    write_executable_script(
        scripts["trial"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
COMMAND="${{1:-}}"
if [[ "$#" -gt 0 ]]; then
  shift
fi
TRIAL_STATE="$ARTIFACT_DIR/source_trial_state.json"
TRIAL_LOG="$ARTIFACT_DIR/source_trials.jsonl"
TRIAL_DIR="$ARTIFACT_DIR/source_trials"

usage() {{
  cat >&2 <<'USAGE'
Usage:
  25_trial_source.sh begin --label <short-mechanism> [--from-ref <kept-or-rejected-ref>]
  25_trial_source.sh reject --reason <why-rejected>
  25_trial_source.sh keep --reason <why-kept>
  25_trial_source.sh status

begin  : checkpoint the current clean/base state and open one active trial.
         With --from-ref, reset the iteration branch to that prior kept/rejected
         ref as the trial workbench while preserving the current base for reject.
reject : commit/pin current work as rejected evidence, snapshot diff/metrics,
         restore the iteration branch to the begin checkpoint, and clear state.
keep   : commit/pin current work as kept evidence and clear state; branch stays
         at the kept source.
status : print active trial state and source branch status.
USAGE
}}

sanitize_label() {{
  local raw="$1"
  local safe
  safe="$(printf '%s' "$raw" | tr -cs 'A-Za-z0-9._-' '_' | sed 's/^[_\\.-]*//; s/[_\\.-]*$//' | cut -c1-80)"
  if [[ -z "$safe" ]]; then
    safe="attempt"
  fi
  printf '%s\n' "$safe"
}}

require_iteration_branch() {{
  current_branch="$(git -C "$DPL_SRC" branch --show-current)"
  if [[ "$current_branch" != "$SOURCE_BRANCH" ]]; then
    echo "[ERROR] expected source branch $SOURCE_BRANCH, got $current_branch" >&2
    exit 2
  fi
}}

commit_current_if_needed() {{
  local message="$1"
  git -C "$DPL_SRC" add -A
  if ! git -C "$DPL_SRC" diff --cached --quiet; then
    git -C "$DPL_SRC" commit -m "$message" >&2
  else
    echo "[INFO] no staged changes; pinning current HEAD" >&2
  fi
  git -C "$DPL_SRC" rev-parse HEAD
}}

write_diff_for_commit() {{
  local base_commit="$1"
  local commit="$2"
  local diff_path="$3"
  mkdir -p "$(dirname "$diff_path")"
  git -C "$DPL_SRC" diff --no-ext-diff "$base_commit".."$commit" > "$diff_path" || true
  if [[ ! -s "$diff_path" ]]; then
    git -C "$DPL_SRC" diff --no-ext-diff "$base_commit" "$commit" > "$diff_path" || true
  fi
}}

snapshot_metrics() {{
  local prefix="$1"
  local out=""
  if [[ -f "$METRICS_PATH" ]]; then
    out="$TRIAL_DIR/${{prefix}}.metrics.json"
    mkdir -p "$TRIAL_DIR"
    cp -f "$METRICS_PATH" "$out"
  fi
  printf '%s\n' "$out"
}}

append_trial_event() {{
  local action="$1"
  local ref="$2"
  local commit="$3"
  local reason="${{4:-}}"
  local diff_path="${{5:-}}"
  local metrics_snapshot="${{6:-}}"
  SOURCE_BRANCH_NOW="$(git -C "$DPL_SRC" branch --show-current)" \
  TRIAL_ACTION="$action" \
  TRIAL_REF="$ref" \
  TRIAL_COMMIT="$commit" \
  TRIAL_REASON="$reason" \
  TRIAL_DIFF="$diff_path" \
  TRIAL_METRICS="$metrics_snapshot" \
  TRIAL_RUN_TAG="$RUN_TAG" \
  DPL_SRC="$DPL_SRC" \
  python3 - "$TRIAL_LOG" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
payload = {{
    "action": os.environ["TRIAL_ACTION"],
    "branch": os.environ["SOURCE_BRANCH_NOW"],
    "diff_path": os.environ.get("TRIAL_DIFF") or None,
    "metrics_snapshot": os.environ.get("TRIAL_METRICS") or None,
    "reason": os.environ.get("TRIAL_REASON") or None,
    "ref": os.environ.get("TRIAL_REF") or None,
    "run_tag": os.environ["TRIAL_RUN_TAG"],
    "source_commit": os.environ.get("TRIAL_COMMIT") or None,
    "source_repo": os.environ["DPL_SRC"],
}}
with path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(payload, sort_keys=True) + "\\n")
PY
}}

load_state_exports() {{
  python3 - "$TRIAL_STATE" <<'PY'
import json
import shlex
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit("[ERROR] no active trial state; run begin first")
payload = json.loads(path.read_text(encoding="utf-8"))
for key, value in payload.items():
    env_key = "TRIAL_" + key.upper()
    print(f"{{env_key}}={{shlex.quote(str(value))}}")
PY
}}

label=""
reason=""
from_ref=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --label|-l)
      if [[ "$#" -lt 2 ]]; then echo "[ERROR] --label requires a value" >&2; usage; exit 2; fi
      label="$2"; shift 2 ;;
    --reason|-r)
      if [[ "$#" -lt 2 ]]; then echo "[ERROR] --reason requires a value" >&2; usage; exit 2; fi
      reason="$2"; shift 2 ;;
    --from-ref)
      if [[ "$#" -lt 2 ]]; then echo "[ERROR] --from-ref requires a value" >&2; usage; exit 2; fi
      from_ref="$2"; shift 2 ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      echo "[ERROR] unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

case "$COMMAND" in
  begin)
    if [[ -z "$label" ]]; then
      echo "[ERROR] begin requires --label" >&2
      usage
      exit 2
    fi
    acquire_workspace_git_lock
    ensure_dpl_git_repo
    assert_no_git_index_lock
    require_iteration_branch
    mkdir -p "$ARTIFACT_DIR" "$TRIAL_DIR"
    if [[ -f "$TRIAL_STATE" ]]; then
      echo "[ERROR] active trial already exists: $TRIAL_STATE" >&2
      echo "[INFO] Resolve it with: 25_trial_source.sh keep|reject --reason <why>" >&2
      exit 2
    fi
    safe_label="$(sanitize_label "$label")"
    base_commit="$(commit_current_if_needed "trial base $SOURCE_BRANCH $safe_label")"
    stamp="$(date +%Y%m%d_%H%M%S)"
    checkpoint_ref="checkpoint/${{RUN_TAG}}/${{stamp}}-${{safe_label}}"
    git -C "$DPL_SRC" check-ref-format --branch "$checkpoint_ref" >/dev/null
    git -C "$DPL_SRC" branch -f "$checkpoint_ref" "$base_commit" >/dev/null
    start_ref="$base_commit"
    start_commit="$base_commit"
    if [[ -n "$from_ref" ]]; then
      start_commit="$(git -C "$DPL_SRC" rev-parse --verify "$from_ref^{{commit}}")"
      git -C "$DPL_SRC" reset --hard "$start_commit" >/dev/null
      start_ref="$from_ref"
      echo "[INFO] trial_from_ref=$from_ref"
      echo "[INFO] trial_start_commit=$start_commit"
    fi
    TRIAL_LABEL="$label" \
    TRIAL_SAFE_LABEL="$safe_label" \
    TRIAL_BASE_COMMIT="$base_commit" \
    TRIAL_CHECKPOINT_REF="$checkpoint_ref" \
    TRIAL_FROM_REF="$start_ref" \
    TRIAL_START_COMMIT="$start_commit" \
    TRIAL_STARTED_AT="$stamp" \
    python3 - "$TRIAL_STATE" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = {{
    "base_commit": os.environ["TRIAL_BASE_COMMIT"],
    "checkpoint_ref": os.environ["TRIAL_CHECKPOINT_REF"],
    "from_ref": os.environ["TRIAL_FROM_REF"],
    "label": os.environ["TRIAL_LABEL"],
    "safe_label": os.environ["TRIAL_SAFE_LABEL"],
    "start_commit": os.environ["TRIAL_START_COMMIT"],
    "started_at": os.environ["TRIAL_STARTED_AT"],
}}
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
PY
    append_trial_event "begin" "$checkpoint_ref" "$base_commit" "trial opened from $start_ref" "" ""
    echo "[INFO] trial_base_commit=$base_commit"
    echo "[INFO] trial_checkpoint_ref=$checkpoint_ref"
    echo "[INFO] trial_state=$TRIAL_STATE"
    ;;
  reject)
    if [[ -z "$reason" ]]; then
      echo "[ERROR] reject requires --reason" >&2
      usage
      exit 2
    fi
    acquire_workspace_git_lock
    ensure_dpl_git_repo
    assert_no_git_index_lock
    require_iteration_branch
    mkdir -p "$TRIAL_DIR"
    eval "$(load_state_exports)"
    stamp="$(date +%Y%m%d_%H%M%S)"
    rejected_commit="$(commit_current_if_needed "rejected $SOURCE_BRANCH ${{TRIAL_SAFE_LABEL}}: $reason")"
    rejected_ref="rejected/${{RUN_TAG}}/${{stamp}}-${{TRIAL_SAFE_LABEL}}"
    git -C "$DPL_SRC" check-ref-format --branch "$rejected_ref" >/dev/null
    git -C "$DPL_SRC" branch -f "$rejected_ref" "$rejected_commit" >/dev/null
    diff_path="$TRIAL_DIR/${{stamp}}-${{TRIAL_SAFE_LABEL}}.rejected.diff"
    write_diff_for_commit "$TRIAL_BASE_COMMIT" "$rejected_commit" "$diff_path"
    metrics_snapshot="$(snapshot_metrics "${{stamp}}-${{TRIAL_SAFE_LABEL}}.rejected")"
    if [[ -n "$metrics_snapshot" ]]; then
      rm -f "$METRICS_PATH"
      echo "[INFO] removed canonical metrics after rejected restore; rerun evaluation for the retained source before finalize."
    fi
    append_trial_event "reject" "$rejected_ref" "$rejected_commit" "$reason" "$diff_path" "$metrics_snapshot"
    git -C "$DPL_SRC" reset --hard "$TRIAL_BASE_COMMIT" >/dev/null
    rm -f "$TRIAL_STATE"
    echo "[INFO] rejected_commit=$rejected_commit"
    echo "[INFO] rejected_ref=$rejected_ref"
    echo "[INFO] rejected_diff=$diff_path"
    if [[ -n "$metrics_snapshot" ]]; then echo "[INFO] rejected_metrics_snapshot=$metrics_snapshot"; fi
    echo "[INFO] restored_source_commit=$TRIAL_BASE_COMMIT"
    echo "[INFO] source_trials=$TRIAL_LOG"
    ;;
  keep)
    if [[ -z "$reason" ]]; then
      echo "[ERROR] keep requires --reason" >&2
      usage
      exit 2
    fi
    acquire_workspace_git_lock
    ensure_dpl_git_repo
    assert_no_git_index_lock
    require_iteration_branch
    mkdir -p "$TRIAL_DIR"
    eval "$(load_state_exports)"
    stamp="$(date +%Y%m%d_%H%M%S)"
    kept_commit="$(commit_current_if_needed "kept $SOURCE_BRANCH ${{TRIAL_SAFE_LABEL}}: $reason")"
    kept_ref="kept/${{RUN_TAG}}/${{stamp}}-${{TRIAL_SAFE_LABEL}}"
    git -C "$DPL_SRC" check-ref-format --branch "$kept_ref" >/dev/null
    git -C "$DPL_SRC" branch -f "$kept_ref" "$kept_commit" >/dev/null
    diff_path="$TRIAL_DIR/${{stamp}}-${{TRIAL_SAFE_LABEL}}.kept.diff"
    write_diff_for_commit "$TRIAL_BASE_COMMIT" "$kept_commit" "$diff_path"
    metrics_snapshot="$(snapshot_metrics "${{stamp}}-${{TRIAL_SAFE_LABEL}}.kept")"
    append_trial_event "keep" "$kept_ref" "$kept_commit" "$reason" "$diff_path" "$metrics_snapshot"
    rm -f "$TRIAL_STATE"
    echo "[INFO] kept_commit=$kept_commit"
    echo "[INFO] kept_ref=$kept_ref"
    echo "[INFO] kept_diff=$diff_path"
    if [[ -n "$metrics_snapshot" ]]; then echo "[INFO] kept_metrics_snapshot=$metrics_snapshot"; fi
    echo "[INFO] source_trials=$TRIAL_LOG"
    ;;
  status)
    ensure_dpl_git_repo
    echo "[INFO] branch=$(git -C "$DPL_SRC" branch --show-current)"
    echo "[INFO] head=$(git -C "$DPL_SRC" rev-parse --short HEAD)"
    git -C "$DPL_SRC" status --short
    if [[ -f "$TRIAL_STATE" ]]; then
      echo "[INFO] active_trial_state=$TRIAL_STATE"
      cat "$TRIAL_STATE"
    else
      echo "[INFO] active_trial_state=<none>"
    fi
    if [[ -f "$TRIAL_LOG" ]]; then
      echo "[INFO] source_trials=$TRIAL_LOG"
      tail -n 5 "$TRIAL_LOG"
    fi
    ;;
  --help|-h|"")
    usage
    if [[ -z "$COMMAND" ]]; then exit 2; fi
    ;;
  *)
    echo "[ERROR] unknown command: $COMMAND" >&2
    usage
    exit 2
    ;;
esac
""",
    )

    write_executable_script(
        scripts["finalize"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
TRIAL_STATE="$ARTIFACT_DIR/source_trial_state.json"
TRIAL_LOG="$ARTIFACT_DIR/source_trials.jsonl"

acquire_workspace_git_lock
ensure_dpl_git_repo
assert_no_git_index_lock
current_branch="$(git -C "$DPL_SRC" branch --show-current)"
if [[ "$current_branch" != "$SOURCE_BRANCH" ]]; then
  echo "[ERROR] expected source branch $SOURCE_BRANCH, got $current_branch" >&2
  exit 2
fi
if [[ -f "$TRIAL_STATE" ]]; then
  echo "[ERROR] active trial still exists: $TRIAL_STATE" >&2
  echo "[INFO] Resolve it first with: 25_trial_source.sh keep|reject --reason <why>" >&2
  exit 2
fi

git -C "$DPL_SRC" status --short
git -C "$DPL_SRC" add -A
if ! git -C "$DPL_SRC" diff --cached --quiet; then
  git -C "$DPL_SRC" commit -m {shlex.quote(f"{paths.source_branch} source update")}
fi
commit="$(git -C "$DPL_SRC" rev-parse HEAD)"
dirty="$(git -C "$DPL_SRC" status --short)"
git -C "$DPL_SRC" check-ref-format --branch "$CANDIDATE_SOURCE_REF" >/dev/null
git -C "$DPL_SRC" branch -f "$CANDIDATE_SOURCE_REF" "$commit" >/dev/null
if [[ -s "$SOURCE_BASE_RECORD" ]]; then
  SOURCE_BASE_COMMIT="$(head -n 1 "$SOURCE_BASE_RECORD")"
else
  SOURCE_BASE_COMMIT="$(git -C "$DPL_SRC" rev-list --max-parents=0 HEAD | tail -n 1)"
fi
mkdir -p "$ARTIFACT_DIR"
SOURCE_COMMIT="$commit" \
DIRTY_STATUS="$dirty" \
CANDIDATE_SOURCE_REF="$CANDIDATE_SOURCE_REF" \
DPL_SRC="$DPL_SRC" \
SOURCE_BASE_COMMIT="$SOURCE_BASE_COMMIT" \
python3 - "$SOURCE_COMMIT_RECORD" "$SOURCE_BRANCH" <<'PY'
import json
import os
import sys

path, branch = sys.argv[1], sys.argv[2]
payload = {{
    "source_base_commit": os.environ.get("SOURCE_BASE_COMMIT") or None,
    "source_candidate_ref": os.environ["CANDIDATE_SOURCE_REF"],
    "source_branch": branch,
    "source_commit": os.environ["SOURCE_COMMIT"],
    "source_repo": os.environ.get("DPL_SRC"),
    "dirty_after_commit": bool(os.environ.get("DIRTY_STATUS", "")),
    "dirty_status": os.environ.get("DIRTY_STATUS", ""),
}}
with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\\n")
PY

git -C "$DPL_SRC" diff --no-ext-diff "$SOURCE_BASE_COMMIT".."$commit" \
  > "$IMPLEMENTATION_DIFF" || true
if [[ ! -s "$IMPLEMENTATION_DIFF" ]]; then
  git -C "$DPL_SRC" diff --no-ext-diff "$SOURCE_BASE_COMMIT" "$commit" \
    > "$IMPLEMENTATION_DIFF" || true
fi
if [[ ! -s "$IMPLEMENTATION_DIFF" ]]; then
  echo "[WARN] implementation diff is empty: $IMPLEMENTATION_DIFF" >&2
else
  echo "[INFO] implementation_diff=$IMPLEMENTATION_DIFF"
fi

if [[ ! -f "$KNOWLEDGE_CARD" ]]; then
  cat > "$KNOWLEDGE_CARD" <<'EOF_KNOWLEDGE'
# Knowledge Card

## Hypothesis

## Mechanism

## Result

## Causal lesson

## Next experiment
EOF_KNOWLEDGE
fi

FINAL_SOURCE_BRANCH="$current_branch" \
FINAL_SOURCE_COMMIT="$commit" \
FINAL_CANDIDATE_REF="$CANDIDATE_SOURCE_REF" \
FINAL_DIFF="$IMPLEMENTATION_DIFF" \
FINAL_KNOWLEDGE="$KNOWLEDGE_CARD" \
DPL_SRC="$DPL_SRC" \
RUN_TAG="$RUN_TAG" \
python3 - "$TRIAL_LOG" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
payload = {{
    "action": "finalize",
    "branch": os.environ["FINAL_SOURCE_BRANCH"],
    "candidate_ref": os.environ["FINAL_CANDIDATE_REF"],
    "diff_path": os.environ["FINAL_DIFF"],
    "knowledge_card": os.environ["FINAL_KNOWLEDGE"],
    "run_tag": os.environ["RUN_TAG"],
    "source_commit": os.environ["FINAL_SOURCE_COMMIT"],
    "source_repo": os.environ["DPL_SRC"],
}}
with path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(payload, sort_keys=True) + "\\n")
PY

echo "[INFO] source_commit=$commit"
echo "[INFO] source_candidate_ref=$CANDIDATE_SOURCE_REF"
echo "[INFO] source_commit_record=$SOURCE_COMMIT_RECORD"
echo "[INFO] source_trials=$TRIAL_LOG"
echo "[INFO] knowledge_card=$KNOWLEDGE_CARD"
if [[ -n "$dirty" ]]; then
  echo "[WARN] source repo still dirty after finalize:" >&2
  printf '%s\n' "$dirty" >&2
fi
""",
    )

    write_executable_script(
        scripts["after_edit"],
        """#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/10_build_variant.sh"
"$SCRIPT_DIR/20_evaluate_candidate.sh"
"$SCRIPT_DIR/30_finalize_source.sh"
""",
    )

    readme = script_dir / "README.md"
    readme.write_text(
        render_prompt_template("packets/student_scripts_readme.md"),
        encoding="utf-8",
    )
    return scripts


def write_child_workspace_packet(
    *,
    path: Path,
    runtime: Any,
    round_dir: Path,
    teacher_operation_id: str,
    teacher_prompt_path: Path,
    case_id: str,
    flow_variant: str,
    threads: int,
    start_kind: str,
    route_label: str,
    child_id: int,
    iteration: int,
    student_id: str,
    run_tag: str,
    stable_workspace: bool,
    elite_seed_source: Path | None,
    peer_learning_path: Path,
    student_runtime_multiplier: float,
    baseline_metrics: dict[str, MetricSummary | None] | None = None,
) -> Path:
    paths = student_workspace_paths(
        round_dir=round_dir,
        iteration=iteration,
        student_id=student_id,
        stable_workspace=stable_workspace,
    )
    parent_src = child_parent_source(
        runtime=runtime,
        round_dir=round_dir,
        iteration=iteration,
        student_id=student_id,
        stable_workspace=stable_workspace,
        elite_seed_source=elite_seed_source,
        start_kind=start_kind,
    )
    use_seed_override = elite_seed_source is not None or (
        iteration > 1 and not stable_workspace
    )
    timeout_seconds, timeout_note = child_evaluation_timeout(
        runtime=runtime,
        case_id=case_id,
        flow_variant=flow_variant,
        round_id=round_id_from_dir(round_dir),
        runtime_multiplier=student_runtime_multiplier,
        baseline_metrics=baseline_metrics,
    )
    script_paths = write_student_workspace_scripts(
        runtime=runtime,
        paths=paths,
        case_id=case_id,
        flow_variant=flow_variant,
        threads=threads,
        start_kind=start_kind,
        run_tag=run_tag,
        parent_src=parent_src,
        use_seed_override=use_seed_override,
        timeout_seconds=timeout_seconds,
    )
    lineage_path = round_dir / "students" / student_id / "lineage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path = expected_metrics_path(
        runtime=runtime,
        case_id=case_id,
        flow_variant=flow_variant,
        run_tag=run_tag,
    )
    agent_root = runtime.agent_root
    teacher_last_message = runtime.operations_dir / teacher_operation_id / "codex_last_message.txt"
    workspace_template = (
        "packets/student_workspace_packet_followup.md"
        if iteration > 1
        else "packets/student_workspace_packet.md"
    )
    path.write_text(
        render_prompt_template(
            workspace_template,
            student_id=student_id,
            child_id=child_id,
            route_label=route_label,
            start_kind=start_kind,
            iteration_name=iter_name(iteration),
            case_id=case_id,
            flow_variant=flow_variant,
            threads=threads,
            run_tag=run_tag,
            parent_src=parent_src,
            source_branch=paths.source_branch,
            source_candidate_ref=stable_candidate_ref(run_tag),
            agent_root=agent_root,
            optional_reference_index=agent_root / "family_variants" / "REFERENCE_INDEX.yaml",
            optional_legalm_reference=agent_root
            / "family_variants"
            / "legalm_guidance"
            / "README.md",
            optional_diamond_reference=agent_root
            / "family_variants"
            / "openroad_diamond"
            / "README.md",
            optional_negotiation_reference=agent_root
            / "family_variants"
            / "openroad_negotiation_nblg"
            / "README.md",
            optional_dpo_source_mechanisms_insight=agent_root
            / "knowledge"
            / "insights"
            / "dpo"
            / "source_level_mechanisms.md",
            optional_strategy_inspiration_insight=agent_root
            / "knowledge"
            / "insights"
            / "case_evolution"
            / "strategy_inspiration_by_design_feature.md",
            optional_openroad_native_handoff_insight=agent_root
            / "knowledge"
            / "insights"
            / "dpo"
            / "openroad_native_handoff.md",
            skill_index=agent_root / "knowledge" / "index" / "skill_cards.jsonl",
            skill_cards_dir=agent_root / "knowledge" / "skills",
            algorithm_cards_dir=agent_root / "knowledge" / "algorithm_cards",
            skill_query_script=agent_root / "scripts" / "query_knowledge.py",
            query_knowledge_script=script_paths["query_knowledge"],
            lineage_path=lineage_path,
            student_workspace=paths.student_workspace,
            variant_root=paths.variant_root,
            dpl_src=paths.dpl_src,
            source_src_dir=paths.dpl_src / "src",
            source_optimization_dir=paths.dpl_src / "src" / "optimization",
            source_objective_dir=paths.dpl_src / "src" / "objective",
            private_binary=paths.private_binary,
            artifact_dir=paths.artifact_dir,
            candidate_metrics_summary_json=paths.candidate_metrics_summary_json,
            candidate_metrics_summary_md=paths.candidate_metrics_summary_md,
            failed_attempts=paths.artifact_dir / "failed_attempts.jsonl",
            implementation_diff=paths.implementation_diff,
            knowledge_card=paths.knowledge_card,
            source_base_record=paths.source_base_record,
            source_commit_record=paths.source_commit_record,
            session_state=paths.session_state,
            session_env_file=paths.session_env_file,
            command_script_dir=paths.student_workspace / "scripts",
            prepare_source_script=script_paths["prepare"],
            prepare_start_source_script=script_paths["prepare_start_source"],
            source_status_script=script_paths["source_status"],
            fetch_peer_source_script=script_paths["peer_source"],
            switch_start_branch_script=script_paths["switch_start_branch"],
            source_context_script=script_paths["source_context"],
            build_variant_script=script_paths["build"],
            fresh_build_script=script_paths["fresh_build"],
            evaluate_candidate_script=script_paths["evaluate"],
            report_candidate_metrics_script=script_paths["report_metrics"],
            keep_and_finalize_script=script_paths["keep_and_finalize"],
            trial_source_script=script_paths["trial"],
            finalize_source_script=script_paths["finalize"],
            after_edit_script=script_paths["after_edit"],
            peer_learning_path=peer_learning_path,
            teacher_prompt_path=teacher_prompt_path,
            teacher_operation_id=teacher_operation_id,
            teacher_plan_last_message=teacher_last_message,
            metrics_path=metrics_path,
            timeout_note=timeout_note,
            patch_rules_skill=agent_root / "skills" / "patch_rules.md",
            source_git_workflow_skill=agent_root / "skills" / "source_git_workflow.md",
            build_openroad_skill=agent_root / "skills" / "build_openroad.md",
            evaluate_run_skill=agent_root / "skills" / "evaluate_run.md",
            trace_logging_skill=agent_root / "skills" / "trace_logging.md",
        ),
        encoding="utf-8",
    )
    return path


def write_review_artifacts_packet(
    *,
    path: Path,
    runtime: Any,
    case_id: str,
    flow_variant: str,
    child_rounds: list[ChildRound],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    chunks = [render_prompt_template("packets/teacher_review_artifacts_header.md")]
    for child in child_rounds:
        chunks.append(
            render_prompt_template(
                "packets/teacher_review_artifacts_child.md",
                student_id=child.student_id,
                route_label=child.route_label,
                operation_id=child.operation_id,
                operation_dir=child.operation_dir,
                run_tag=child.run_tag,
                prompt_path=child.prompt_path,
                workspace_packet=child.workspace_packet,
                last_message=child.last_message,
                usage_summary=child.usage_summary,
                stderr_log=child.stderr_log,
                events_jsonl=child.events_jsonl,
                student_workspace=child.student_workspace,
                dpl_src=child.dpl_src,
                source_branch=child.source_branch,
                private_binary=child.private_binary,
                failed_attempts=child.implementation_diff.parent
                / "failed_attempts.jsonl",
                source_trials=child.implementation_diff.parent
                / "source_trials.jsonl",
                implementation_diff=child.implementation_diff,
                knowledge_card=child.knowledge_card,
                source_base_record=child.source_base_record,
                source_commit_record=child.source_commit_record,
                session_state=child.session_state,
                session_env_file=child.session_env_file,
                artifact_status_block=child_artifact_status_block(
                    runtime=runtime,
                    case_id=case_id,
                    flow_variant=flow_variant,
                    child=child,
                ),
            )
        )
    path.write_text("\n".join(chunks), encoding="utf-8")
    return path


def child_prompt(
    *,
    context_path: Path,
    runtime: Any,
    round_dir: Path,
    teacher_operation_id: str,
    teacher_prompt_path: Path,
    case_id: str,
    flow_variant: str,
    threads: int,
    route_label: str,
    child_id: int,
    iteration: int,
    student_id: str,
    run_tag: str,
    workspace_packet_path: Path,
    peer_learning_path: Path,
    compact: bool = False,
    stable_workspace: bool = False,
    elite_seed_source: Path | None = None,
    student_runtime_multiplier: float = 2.0,
) -> str:
    elite_note = ""
    if elite_seed_source is not None:
        elite_note = render_prompt_template(
            "student/elite_initial_note.md",
            elite_seed_source=elite_seed_source,
        )
    return render_prompt_template(
        "student/initial.md",
        context_path=context_path,
        child_id=child_id,
        student_id=student_id,
        route_label=route_label,
        iteration_name=iter_name(iteration),
        workspace_packet_path=workspace_packet_path,
        peer_learning_path=peer_learning_path,
        teacher_plan_last_message=runtime.operations_dir
        / teacher_operation_id
        / "codex_last_message.txt",
        elite_note=elite_note,
        student_rules=render_prompt_template(
            "student/rules.md",
            student_runtime_multiplier=format_multiplier(student_runtime_multiplier),
        ),
    )


def compact_child_prompt(
    *,
    context_path: Path,
    runtime: Any,
    round_dir: Path,
    teacher_operation_id: str,
    teacher_prompt_path: Path,
    case_id: str,
    flow_variant: str,
    threads: int,
    route_label: str,
    child_id: int,
    iteration: int,
    student_id: str,
    run_tag: str,
    workspace_packet_path: Path,
    peer_learning_path: Path,
    stable_workspace: bool = False,
    elite_seed_source: Path | None = None,
    student_runtime_multiplier: float = 2.0,
) -> str:
    elite_note = ""
    if elite_seed_source is not None:
        elite_note = render_prompt_template(
            "student/elite_followup_note.md",
            elite_seed_source=elite_seed_source,
        )
    peer_context = peer_briefing(
        runtime=runtime,
        round_dir=round_dir,
        case_id=case_id,
        flow_variant=flow_variant,
        iteration=iteration,
        current_student=student_id,
        student_runtime_multiplier=student_runtime_multiplier,
    )

    return render_prompt_template(
        "student/followup.md",
        context_path=context_path,
        student_id=student_id,
        route_label=route_label,
        iteration_name=iter_name(iteration),
        teacher_plan_last_message=runtime.operations_dir
        / teacher_operation_id
        / "codex_last_message.txt",
        workspace_packet_path=workspace_packet_path,
        peer_learning_path=peer_learning_path,
        case_id=case_id,
        flow_variant=flow_variant,
        threads=threads,
        run_tag=run_tag,
        elite_note=elite_note,
        peer_context=peer_context,
        student_rules=render_prompt_template(
            "student/rules_followup.md",
            student_runtime_multiplier=format_multiplier(student_runtime_multiplier),
        ),
    )


def write_round_readme(
    *,
    runtime: Any,
    round_dir: Path,
    case_id: str,
    flow_variant: str,
    start_kind: str,
    strategies: list[str],
    metrics: dict[str, MetricSummary | None],
    launch_commands: list[list[str]],
) -> None:
    lines = [
        f"# Codex Optimization Round: {case_id}",
        "",
        f"- flow_variant: `{flow_variant}`",
        f"- start_kind: `{start_kind}`",
        f"- created_at: `{dt.datetime.now().isoformat()}`",
        "",
        "## Baseline Evidence",
        metric_table(metrics),
        "",
        "## Baseline Artifact Paths",
        baseline_artifact_block(
            runtime=runtime,
            case_id=case_id,
            flow_variant=flow_variant,
            metrics=metrics,
        ),
        "",
        "## Student Route Labels",
        *[
            f"- `{name}`: Teacher-assigned route label for bookkeeping."
            for name in strategies
        ],
        "",
        "## Launch Commands",
        "```bash",
    ]
    lines.extend(" ".join(shlex.quote(part) for part in command) for command in launch_commands)
    lines.extend(["```", ""])
    round_dir.joinpath("README.md").write_text("\n".join(lines), encoding="utf-8")


PROMPT_FORBIDDEN_TERMS = (
    "Required Commands",
    "```bash",
    "Dispatch",
    "dispatch packet",
    "global synthesis",
    "execute only",
    *NOISY_CONTEXT_MARKERS,
    "reported mechanism / next clue",
    "one coherent algorithmic change",
)


def agent_prompt_warnings(
    text: str, *, max_agent_prompt_bytes: int = 12000
) -> list[str]:
    """Return warnings for text that will be sent directly to an agent."""
    warnings: list[str] = []
    if len(text.encode("utf-8")) > max_agent_prompt_bytes:
        warnings.append(f"agent prompt exceeds {max_agent_prompt_bytes} bytes")
    for term in PROMPT_FORBIDDEN_TERMS:
        if term in text:
            warnings.append(f"agent prompt contains `{term}`")
    if text.count("/home/") > 35:
        warnings.append("agent prompt has many absolute paths")
    seen: dict[str, int] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("|") or len(line) < 24:
            continue
        seen[line] = seen.get(line, 0) + 1
    repeated_lines = [line for line, count in seen.items() if count > 2]
    if repeated_lines:
        warnings.append(
            "agent prompt repeats lines: " + "; ".join(repeated_lines[:3])
        )
    assignment_start = assigned_start_kind_from_insight(text)
    immediate_start = None
    for raw_line in text.splitlines():
        if raw_line.startswith("Initial workspace setup:"):
            immediate_match = re.search(
                r"(?:prepare_start_source_script|switch_start_branch_script) --kind\s+([A-Za-z0-9_]+)",
                raw_line,
            )
            immediate_start = immediate_match.group(1) if immediate_match else None
            break
    if assignment_start and immediate_start != assignment_start:
        warnings.append(
            "Teacher assigned start branch "
            f"`{assignment_start}` but immediate action uses `{immediate_start or 'none'}`"
        )
    if immediate_start and not assignment_start:
        warnings.append(
            "immediate action switches start branch but Teacher assignment has no primary prepared start"
        )
    return warnings


def prompt_audit(
    *, round_dir: Path, max_agent_prompt_bytes: int = 12000
) -> tuple[Path, Path, int]:
    """Audit generated prompts without launching agents.

    Machine packets are allowed to contain commands and long paths.  Agent
    prompts should stay compact and should not contain generated shell blocks.
    """
    rows: list[dict[str, Any]] = []
    warnings = 0
    files = (
        sorted(round_dir.glob("iter_*/prompts/*.md"))
        + sorted(round_dir.glob("iter_*/packet/*.md"))
        + sorted(round_dir.glob("iter_*/context/*.md"))
    )
    for path in files:
        rel = path.relative_to(round_dir)
        text = path.read_text(encoding="utf-8", errors="replace")
        rel_posix = f"/{rel.as_posix()}"
        is_agent_prompt = "/prompts/" in rel_posix
        is_context = "/context/" in rel_posix
        file_warnings: list[str] = []
        if is_agent_prompt:
            file_warnings.extend(
                agent_prompt_warnings(
                    text, max_agent_prompt_bytes=max_agent_prompt_bytes
                )
            )
        elif is_context and len(text.encode("utf-8")) > 30000:
            file_warnings.append(
                "generated context is large; evidence is retained uncapped"
            )
        warnings += len(file_warnings)
        rows.append(
            {
                "file": str(rel),
                "kind": (
                    "agent_prompt"
                    if is_agent_prompt
                    else "generated_context"
                    if is_context
                    else "generated_packet"
                ),
                "bytes": len(text.encode("utf-8")),
                "lines": text.count("\n") + 1,
                "absolute_path_count": text.count("/home/"),
                "bash_blocks": text.count("```bash"),
                "warnings": file_warnings,
            }
        )

    audit_json = round_dir / "prompt_audit.json"
    audit_md = round_dir / "PROMPT_AUDIT.md"
    audit_json.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Prompt Audit",
        "",
        f"- files: `{len(rows)}`",
        f"- warnings: `{warnings}`",
        "",
        "| file | kind | bytes | lines | paths | bash | warnings |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        warning_text = "; ".join(row["warnings"]) if row["warnings"] else "ok"
        lines.append(
            "| {file} | {kind} | {bytes} | {lines} | {paths} | {bash} | {warnings} |".format(
                file=row["file"],
                kind=row["kind"],
                bytes=row["bytes"],
                lines=row["lines"],
                paths=row["absolute_path_count"],
                bash=row["bash_blocks"],
                warnings=warning_text.replace("|", "\\|"),
            )
        )
    audit_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return audit_json, audit_md, warnings
