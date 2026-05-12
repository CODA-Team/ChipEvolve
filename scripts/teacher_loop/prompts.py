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
    hpwl_runtime_score,
    hpwl_runtime_score_factors,
    metric_table,
    operation_artifact_block,
    parse_candidate_tag,
    score_reference_anchor,
    stage_donor_signal,
    summarize_metrics,
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
        return f"Missing: `{path}`"
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return f"Empty: `{path}`"
    if len(text) <= max_chars:
        return text
    return f"Long content is not embedded. Use this source only when needed: `{path}`"


def previous_teacher_review_excerpt(
    *, runtime: Any, round_id: str, iteration: int, max_chars: int = 6000
) -> str:
    if iteration <= 1:
        return "No previous Teacher review exists yet."
    review_op = f"{round_id}_{iter_name(iteration - 1)}_teacher_review"
    review_path = runtime.operations_dir / review_op / "codex_last_message.txt"
    if not review_path.exists():
        return f"Missing: `{review_path}`"
    text = review_path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return f"Empty: `{review_path}`"
    if any(marker in text for marker in INFRASTRUCTURE_REVIEW_MARKERS):
        return (
            "Previous Teacher review omitted because it only recorded an "
            "infrastructure/tooling failure. Use the previous child metrics, "
            "source commits, and peer packet for evidence instead."
        )
    if len(text) <= max_chars:
        return text
    return focused_message_excerpt(text, max_chars=min(max_chars, 1200))


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
        return "No prior peer results yet."

    round_id = round_dir.name
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
    _baseline_label, baseline = score_reference_anchor(baseline_metrics)
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
            invalid_note = "\n\nInvalid prior metric rows were found but are non-promotable: " + "; ".join(
                f"{student_id}={candidate_artifact_status_text(problems)}"
                for student_id, _summary, problems in invalid_rows[:4]
            )
        return (
            f"Previous iteration: `{previous}`\n\n"
            "No valid prior peer metrics were found. Use Teacher insight and "
            "your own source/log inspection; do not assume a peer mechanism is validated."
            f"{invalid_note}"
        )

    def peer_rank(student: str) -> tuple[float, float]:
        summary = metrics_by_student[student]
        hpwl_rank = (
            -float(summary.hpwl_after)
            if summary.hpwl_after is not None
            else float("-inf")
        )
        cost = hpwl_runtime_score(summary, baseline)
        cost_rank = -cost if cost is not None else float("-inf")
        return hpwl_rank, cost_rank

    best_student = max(metrics_by_student, key=peer_rank)
    lines = [
        f"Previous iteration: `{previous}`",
        "",
        "Peer evidence below is artifact-gated. Use peer packet/source paths "
        "only when Teacher names a concrete donor; summarize it briefly before borrowing.",
        "",
        f"Best previous valid clean peer by HPWL first, then lower C_HR: `{best_student}`.",
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
        score_factors = hpwl_runtime_score_factors(summary, baseline)
        score_text = "" if score_factors is None else f"{score_factors['score']:.3f}"
        h_text = "" if score_factors is None else f"{score_factors['H']:.4f}"
        r_text = "" if score_factors is None else f"{score_factors['R']:.4f}"
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
            "- {student} ({label}): C_HR `{score}` H/R `{h}/{r}`, "
            "HPWL `{hpwl}`, runtime `{runtime_s}`, "
            "avg/max disp `{avg_disp}/{max_disp}`, legality `{violations}`; "
            "stage `{stage_pct}`, signal `{signal}`".format(
                student=student_id,
                label=label,
                score=score_text,
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
            "Invalid prior metric rows are diagnostic only, not donor/elite seeds: "
            + "; ".join(
                f"{student_id}={candidate_artifact_status_text(problems)}"
                for student_id, _summary, problems in invalid_rows[:4]
            )
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
        return "No previous iteration exists. This is the first exploration round."

    previous = iteration - 1
    review_op = f"{round_id}_{iter_name(previous)}_teacher_review"
    blocks = [
        f"Previous iteration: `{iter_name(previous)}`",
        "",
        "## Previous Teacher Review",
        operation_artifact_block(runtime, review_op),
        "",
        "## Previous Teacher Review Excerpt",
        "",
        "Baseline rule: use the canonical baseline table and scoreboard in "
        "this context for current comparisons.",
        "",
        previous_teacher_review_excerpt(
            runtime=runtime,
            round_id=round_id,
            iteration=iteration,
            max_chars=8000,
        ),
        "",
        "## Previous Child Artifacts",
    ]
    for idx, route_label in enumerate(strategies, start=1):
        student_id = f"student_{idx:02d}"
        child_op = f"{round_id}_{iter_name(previous)}_{student_id}"
        blocks.append(f"### {student_id} (route label: {route_label})")
        blocks.append(operation_artifact_block(runtime, child_op))
        blocks.append(
            f"- lineage: `{round_dir / 'students' / student_id / 'lineage.json'}`"
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
        "No elite source seed is available yet."
        if elite_seed_source is None
        else (
            "`student_01` is the protected elite-continuation branch for this "
            f"iteration and will be pre-seeded from `{elite_seed_source}`."
        )
    )
    return render_prompt_template(
        "common_context.md",
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
        evolved_dpo_readme=runtime.agent_root
        / "patches"
        / "evolved_dpo"
        / "README.md",
        evolved_dpo_manifest=runtime.agent_root
        / "patches"
        / "evolved_dpo"
        / "generation_manifest.tsv",
        evolved_dpo_validation=runtime.agent_root
        / "patches"
        / "evolved_dpo"
        / "validation.tsv",
        dense_legalizer_routing_insight=runtime.agent_root
        / "knowledge"
        / "insights"
        / "case_evolution"
        / "dense_evolved_legalizer_routing.md",
        dpo_runtime_quality_insight=runtime.agent_root
        / "knowledge"
        / "insights"
        / "dpo"
        / "dpo_runtime_quality_frontier.md",
        dpo_cross_legalizer_insight=runtime.agent_root
        / "knowledge"
        / "insights"
        / "dpo"
        / "cross_legalizer_dpo_donors.md",
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
        peer_learning_path=peer_learning_path,
        prior_context=prior_context,
        student_runtime_multiplier=format_multiplier(student_runtime_multiplier),
    )


def teacher_prompt(
    *,
    context_path: Path,
    strategies: list[str],
    children: int,
    iteration: int,
    student_runtime_multiplier: float,
) -> str:
    student_roster = "\n".join(
        f"- `student_{idx:02d}`" for idx in range(1, children + 1)
    )
    route_lines = "\n".join(
        f"- `student_{idx:02d}`: Teacher assigns this route after reading "
        "context, source references, peer evidence, and metrics."
        for idx, _name in enumerate(strategies, start=1)
    )
    return render_prompt_template(
        "teacher_plan.md",
        context_path=context_path,
        iteration_name=iter_name(iteration),
        route_lines=route_lines,
        student_roster=student_roster,
        teacher_rules=render_prompt_template(
            "teacher_rules.md",
            student_runtime_multiplier=format_multiplier(student_runtime_multiplier),
        ),
        teacher_plan_output=render_prompt_template(
            "teacher_plan_output.md",
            student_insight_packet_format=render_prompt_template(
                "student_insight_packet_format.md"
            ),
        ),
        children=children,
    )


def compact_teacher_prompt(
    *,
    context_path: Path,
    strategies: list[str],
    children: int,
    iteration: int,
    student_runtime_multiplier: float,
) -> str:
    student_roster = "\n".join(
        f"- `student_{idx:02d}`" for idx in range(1, children + 1)
    )
    route_lines = "\n".join(
        f"- `student_{idx:02d}`: Teacher assigns this route after reading "
        "context, source references, peer evidence, and metrics."
        for idx, _name in enumerate(strategies, start=1)
    )
    return render_prompt_template(
        "teacher_plan_compact.md",
        context_path=context_path,
        iteration_name=iter_name(iteration),
        route_lines=route_lines,
        student_roster=student_roster,
        teacher_rules=render_prompt_template(
            "teacher_rules.md",
            student_runtime_multiplier=format_multiplier(student_runtime_multiplier),
        ),
        teacher_plan_output=render_prompt_template(
            "teacher_plan_output.md",
            student_insight_packet_format=render_prompt_template(
                "student_insight_packet_format.md"
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
        "teacher_review.md",
        context_path=context_path,
        review_packet_path=review_packet_path,
        teacher_review_rules=render_prompt_template(
            "teacher_review_rules.md",
            student_runtime_multiplier=format_multiplier(student_runtime_multiplier),
        ),
        teacher_review_output=render_prompt_template(
            "teacher_review_output.md",
            student_insight_packet_format=render_prompt_template(
                "student_insight_packet_format.md"
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
        "teacher_review_compact.md",
        context_path=context_path,
        review_packet_path=review_packet_path,
        teacher_review_rules=render_prompt_template(
            "teacher_review_rules.md",
            student_runtime_multiplier=format_multiplier(student_runtime_multiplier),
        ),
        teacher_review_output=render_prompt_template(
            "teacher_review_output.md",
            student_insight_packet_format=render_prompt_template(
                "student_insight_packet_format.md"
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
        f"`{runtime_s:.3f}s` from `metrics.json:runtime_seconds` at `{baseline_path}`. "
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
SOURCE_BASE_RECORD={shlex.quote(str(paths.source_base_record))}
SOURCE_COMMIT_RECORD={shlex.quote(str(paths.source_commit_record))}
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
"""

    scripts = {
        "prepare": script_dir / "00_prepare_source.sh",
        "switch_start_branch": script_dir / "04_switch_start_branch.sh",
        "source_context": script_dir / "05_source_context.sh",
        "apply_evolved_patch": script_dir / "06_apply_evolved_legalizer_patch.sh",
        "apply_evolved_dpo_patch": script_dir / "07_apply_evolved_dpo_patch.sh",
        "query_knowledge": script_dir / "08_query_knowledge.sh",
        "build": script_dir / "10_build_variant.sh",
        "fresh_build": script_dir / "11_build_variant_fresh.sh",
        "evaluate": script_dir / "20_evaluate_candidate.sh",
        "commit": script_dir / "30_commit_source.sh",
        "diff": script_dir / "40_write_diff.sh",
        "knowledge_template": script_dir / "50_seed_knowledge_card.sh",
        "after_edit": script_dir / "run_after_edit.sh",
    }

    write_executable_script(
        scripts["prepare"],
        f"""#!/usr/bin/env bash
	set -euo pipefail
{common_vars}
mkdir -p "$VARIANT_ROOT" "$ARTIFACT_DIR"
"$AGENT_ROOT/scripts/create_variant_start.sh" \\
  --orfs-root "$ORFS_ROOT" \\
  --variant-root "$VARIANT_ROOT" \\
  --start-kind "$START_KIND" \\
  --dpl-src "$DPL_SRC" \\
{seed_lines}  --git-branch "$SOURCE_BRANCH"
ensure_dpl_git_repo
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

dpo_patch_for_donor() {{
  case "$1" in
    neg017b)
      printf '%s\\n' "$AGENT_ROOT/patches/evolved_dpo/src_dpo_neg017b_algo1_src_cache_runtime.patch"
      ;;
    neg014)
      printf '%s\\n' "$AGENT_ROOT/patches/evolved_dpo/src_dpo_neg014_hybrid_quality.patch"
      ;;
    neg015)
      printf '%s\\n' "$AGENT_ROOT/patches/evolved_dpo/src_dpo_neg015_staged_runtime.patch"
      ;;
    *)
      return 2
      ;;
  esac
}}

materialize_dpo_branch() {{
  local kind="$1"
  local donor="$2"
  local base_branch="start/$kind"
  local branch="start/${{kind}}_dpo_${{donor}}"
  local patch
  if ! git -C "$DPL_SRC" show-ref --verify --quiet "refs/heads/$base_branch"; then
    echo "[WARN] cannot prepare $branch; missing base branch $base_branch" >&2
    return 0
  fi
  patch="$(dpo_patch_for_donor "$donor")"
  if [[ ! -f "$patch" ]]; then
    echo "[WARN] cannot prepare $branch; missing DPO patch: $patch" >&2
    return 0
  fi
  git -C "$DPL_SRC" switch --detach "$base_branch" >/dev/null
  if ! git -C "$DPL_SRC" apply --whitespace=nowarn --check "$patch"; then
    echo "[WARN] cannot prepare $branch; DPO patch does not apply: $patch" >&2
    git -C "$DPL_SRC" switch "$SOURCE_BRANCH" >/dev/null
    return 0
  fi
  git -C "$DPL_SRC" apply --whitespace=nowarn "$patch"
  git -C "$DPL_SRC" add -A
  git -C "$DPL_SRC" commit -m "Seed $branch source" >/dev/null
  git -C "$DPL_SRC" branch -f "$branch" HEAD >/dev/null
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
  for kind in framework diamond evolved_diamond evolved_legalm evolved_negotiation; do
    for donor in neg017b neg014 neg015; do
      materialize_dpo_branch "$kind" "$donor"
    done
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
        scripts["switch_start_branch"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
ensure_dpl_git_repo

kind=""
usage() {{
  cat >&2 <<'USAGE'
Usage:
  04_switch_start_branch.sh --kind <prepared-start-kind>

Reset the iteration source branch to one prepared local start branch. Examples:
  framework
  diamond
  evolved_legalm
  evolved_legalm_dpo_neg017b
  evolved_diamond_dpo_neg014

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

This script only prints current local source context for patch anchoring.
Edit with apply_patch after reading the current excerpt.
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
        scripts["apply_evolved_patch"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
ensure_dpl_git_repo

line=""
check_only=0
usage() {{
  cat >&2 <<'USAGE'
Usage:
  06_apply_evolved_legalizer_patch.sh --line diamond|legalm|negotiation [--check-only]

Apply or check exactly one evolved legalizer framework-delta patch against the
private dpl_evolve source. Use this only when Teacher assigns patch application
instead of starting directly from an evolved_* seed.
USAGE
}}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --line)
      line="$2"
      shift 2
      ;;
    --check-only)
      check_only=1
      shift
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

case "$line" in
  diamond)
    patch="$AGENT_ROOT/patches/evolved_legalizers/openroad_dpl_evolve_diamond_iter30_framework_delta.patch"
    ;;
  legalm)
    patch="$AGENT_ROOT/patches/evolved_legalizers/openroad_dpl_evolve_legalm_iter30_framework_delta.patch"
    ;;
  negotiation)
    patch="$AGENT_ROOT/patches/evolved_legalizers/openroad_dpl_evolve_negotiation_iter30_framework_delta.patch"
    ;;
  *)
    echo "[ERROR] expected --line diamond|legalm|negotiation" >&2
    usage
    exit 2
    ;;
esac

if [[ -f "$DPL_SRC/.dpl_evolve_seed_manifest.json" ]]; then
  echo "[ERROR] private source already comes from an evolved seed manifest." >&2
  echo "[ERROR] Do not stack an evolved framework-delta patch on this source." >&2
  cat "$DPL_SRC/.dpl_evolve_seed_manifest.json" >&2 || true
  exit 2
fi
if [[ ! -f "$patch" ]]; then
  echo "[ERROR] missing evolved legalizer framework-delta patch: $patch" >&2
  exit 2
fi
if [[ -n "$(git -C "$DPL_SRC" status --short)" ]]; then
  echo "[ERROR] private source has uncommitted changes; commit/stash before applying donor patch." >&2
  git -C "$DPL_SRC" status --short >&2
  exit 2
fi

if ! git -C "$DPL_SRC" apply --whitespace=nowarn --check -p3 "$patch"; then
  echo "[ERROR] evolved patch does not apply to current private source: $patch" >&2
  echo "[ERROR] Use it as review evidence or start a fresh route from the matching evolved_* seed." >&2
  exit 1
fi
if [[ "$check_only" -eq 1 ]]; then
  echo "[INFO] evolved patch check OK: line=$line patch=$patch"
  exit 0
fi
git -C "$DPL_SRC" apply --whitespace=nowarn -p3 "$patch"
git -C "$DPL_SRC" add -A
git -C "$DPL_SRC" commit -m "Apply evolved legalizer $line framework delta"
echo "[INFO] evolved patch applied and committed: line=$line"
echo "[INFO] source_commit=$(git -C "$DPL_SRC" rev-parse HEAD)"
""",
    )

    write_executable_script(
        scripts["apply_evolved_dpo_patch"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
ensure_dpl_git_repo

donor=""
check_only=0
usage() {{
  cat >&2 <<'USAGE'
Usage:
  07_apply_evolved_dpo_patch.sh --donor neg017b|neg014|neg015 [--check-only]
  07_apply_evolved_dpo_patch.sh --donor neg014_to_neg015|neg015_to_neg017b [--check-only]

Apply or check exactly one evolved DPO/improve-placement source-root patch
against the private dpl_evolve source. These patches are designed to stack on
the selected legalizer seed. Run --check-only first.
USAGE
}}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --donor|--mechanism)
      donor="$2"
      shift 2
      ;;
    --check-only)
      check_only=1
      shift
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

case "$donor" in
  neg017b|recommended|runtime_quality)
    mechanism="neg017b_algo1_src_cache_runtime"
    patch="$AGENT_ROOT/patches/evolved_dpo/src_dpo_neg017b_algo1_src_cache_runtime.patch"
    ;;
  neg014|quality|quality_ceiling)
    mechanism="neg014_hybrid_quality"
    patch="$AGENT_ROOT/patches/evolved_dpo/src_dpo_neg014_hybrid_quality.patch"
    ;;
  neg015|staged_runtime)
    mechanism="neg015_staged_runtime"
    patch="$AGENT_ROOT/patches/evolved_dpo/src_dpo_neg015_staged_runtime.patch"
    ;;
  neg014_to_neg015)
    mechanism="neg014_to_neg015_runtime_delta"
    patch="$AGENT_ROOT/patches/evolved_dpo/src_dpo_neg014_to_neg015_runtime_delta.patch"
    ;;
  neg015_to_neg017b)
    mechanism="neg015_to_neg017b_algo1_cache_delta"
    patch="$AGENT_ROOT/patches/evolved_dpo/src_dpo_neg015_to_neg017b_algo1_cache_delta.patch"
    ;;
  *)
    echo "[ERROR] expected --donor neg017b|neg014|neg015|neg014_to_neg015|neg015_to_neg017b" >&2
    usage
    exit 2
    ;;
esac

if [[ ! -f "$patch" ]]; then
  echo "[ERROR] missing evolved DPO patch: $patch" >&2
  exit 2
fi
if [[ "$check_only" -eq 0 && -n "$(git -C "$DPL_SRC" status --short)" ]]; then
  echo "[ERROR] private source has uncommitted changes; commit/stash before applying a DPO donor patch." >&2
  git -C "$DPL_SRC" status --short >&2
  exit 2
fi

already_present=0
if ! git -C "$DPL_SRC" apply --whitespace=nowarn --check "$patch" >/dev/null 2>&1; then
  if git -C "$DPL_SRC" apply --whitespace=nowarn --reverse --check "$patch" >/dev/null 2>&1; then
    already_present=1
  else
    echo "[ERROR] evolved DPO patch does not apply to current private source: $patch" >&2
    echo "[ERROR] Check the donor apply base in patches/evolved_dpo/README.md or use it as review evidence." >&2
    git -C "$DPL_SRC" apply --whitespace=nowarn --check "$patch" >&2 || true
    exit 1
  fi
fi
if [[ "$already_present" -eq 1 ]]; then
  echo "[INFO] evolved DPO patch already present: mechanism=$mechanism patch=$patch"
  echo "[INFO] This is expected on prepared start branches such as start/<legalizer>_dpo_<donor>."
  exit 0
fi
if [[ "$check_only" -eq 1 ]]; then
  echo "[INFO] evolved DPO patch check OK: mechanism=$mechanism patch=$patch"
  exit 0
fi
git -C "$DPL_SRC" apply --whitespace=nowarn "$patch"
git -C "$DPL_SRC" add -A
git -C "$DPL_SRC" commit -m "Apply evolved DPO donor $mechanism"
echo "[INFO] evolved DPO patch applied and committed: mechanism=$mechanism"
echo "[INFO] source_commit=$(git -C "$DPL_SRC" rev-parse HEAD)"
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
ensure_dpl_git_repo
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
ensure_dpl_git_repo
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
""",
    )

    write_executable_script(
        scripts["commit"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
ensure_dpl_git_repo
git -C "$DPL_SRC" status --short
git -C "$DPL_SRC" add -A
if ! git -C "$DPL_SRC" diff --cached --quiet; then
  git -C "$DPL_SRC" commit -m {shlex.quote(f"{paths.source_branch} source update")}
fi
commit="$(git -C "$DPL_SRC" rev-parse HEAD)"
dirty="$(git -C "$DPL_SRC" status --short)"
SOURCE_COMMIT="$commit" DIRTY_STATUS="$dirty" python3 - "$SOURCE_COMMIT_RECORD" "$SOURCE_BRANCH" <<'PY'
import json
import os
import sys

path, branch = sys.argv[1], sys.argv[2]
payload = {{
    "source_commit": os.environ["SOURCE_COMMIT"],
    "source_branch": branch,
    "dirty_after_commit": bool(os.environ.get("DIRTY_STATUS", "")),
    "dirty_status": os.environ.get("DIRTY_STATUS", ""),
}}
with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\\n")
PY
echo "[INFO] source_commit=$commit"
if [[ -n "$dirty" ]]; then
  echo "[WARN] source repo still dirty after commit:" >&2
  printf '%s\\n' "$dirty" >&2
fi
""",
    )

    write_executable_script(
        scripts["diff"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
ensure_dpl_git_repo
mkdir -p "$ARTIFACT_DIR"
if [[ -s "$SOURCE_BASE_RECORD" ]]; then
  SOURCE_BASE_COMMIT="$(head -n 1 "$SOURCE_BASE_RECORD")"
else
  SOURCE_BASE_COMMIT="$(git -C "$DPL_SRC" rev-list --max-parents=0 HEAD | tail -n 1)"
fi
git -C "$DPL_SRC" diff --no-ext-diff "$SOURCE_BASE_COMMIT"..HEAD \\
  > "$IMPLEMENTATION_DIFF" || true
if [[ ! -s "$IMPLEMENTATION_DIFF" ]]; then
  git -C "$DPL_SRC" diff --no-ext-diff "$SOURCE_BASE_COMMIT" \\
    > "$IMPLEMENTATION_DIFF" || true
fi
if [[ ! -s "$IMPLEMENTATION_DIFF" ]]; then
  echo "[WARN] implementation diff is empty: $IMPLEMENTATION_DIFF" >&2
else
  echo "[INFO] implementation_diff=$IMPLEMENTATION_DIFF"
fi
""",
    )

    write_executable_script(
        scripts["knowledge_template"],
        f"""#!/usr/bin/env bash
set -euo pipefail
{common_vars}
mkdir -p "$ARTIFACT_DIR"
if [[ -f "$KNOWLEDGE_CARD" ]]; then
  echo "[INFO] knowledge card already exists: $KNOWLEDGE_CARD"
  exit 0
fi
cat > "$KNOWLEDGE_CARD" <<'EOF'
# Knowledge Card

## Hypothesis

## Mechanism

## Result

## Causal lesson

## Next experiment
EOF
echo "[INFO] knowledge_card=$KNOWLEDGE_CARD"
""",
    )

    write_executable_script(
        scripts["after_edit"],
        """#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/10_build_variant.sh"
"$SCRIPT_DIR/20_evaluate_candidate.sh"
"$SCRIPT_DIR/30_commit_source.sh"
"$SCRIPT_DIR/40_write_diff.sh"
"$SCRIPT_DIR/50_seed_knowledge_card.sh"
""",
    )

    readme = script_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Generated Student Command Scripts",
                "",
                "These scripts are generated by the Teacher/Student orchestrator.",
                "Use them instead of reconstructing build, evaluator, git, or diff commands.",
                "",
                "Recommended flow:",
                "",
                "1. `00_prepare_source.sh` once before editing.",
                "2. If Teacher assigns a prepared start point, run",
                "   `04_switch_start_branch.sh --kind <framework|diamond|evolved_...|evolved_..._dpo_...>` before edits.",
                "3. Use `05_source_context.sh <src/...> [symbol]` when you need",
                "   current local source context for an apply_patch anchor.",
                "4. Use `06_apply_evolved_legalizer_patch.sh --check-only` only",
                "   when Teacher explicitly assigns an evolved framework-delta patch.",
                "5. Use `07_apply_evolved_dpo_patch.sh --check-only` only when",
                "   Teacher explicitly assigns a DPO donor patch on the current source.",
                "6. Use `08_query_knowledge.sh --stage <stage> --q <text>` when",
                "   Teacher names a skill id or you need one concise mechanism card.",
                "   Open only the relevant algorithm/pseudocode card it points to.",
                "7. Edit only the packet `private_dpl_evolve_source` with apply_patch.",
                "8. `10_build_variant.sh` after code changes.",
                "9. `20_evaluate_candidate.sh` for canonical metrics.",
                "10. `30_commit_source.sh` before the final answer.",
                "11. `40_write_diff.sh` to write the implementation diff.",
                "12. `50_seed_knowledge_card.sh` if the knowledge card does not exist yet.",
                "",
                "Use `11_build_variant_fresh.sh` only when the normal generated build",
                "script fails or leaves the private binary missing.",
                "",
                "`run_after_edit.sh` runs build, evaluation, commit, diff, and knowledge",
                "template creation after source edits are already complete.",
                "",
            ]
        ),
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
        round_id=round_dir.name,
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
    path.write_text(
        f"""# Generated Workspace Packet: {student_id}

This file is generated by the orchestrator.  It contains exact paths and
commands.  Do not ask Teacher to rewrite this content.

## Identity

- child_id: `{child_id}`
- student_id: `{student_id}`
- route_label: `{route_label}`
- round_default_start_kind: `{start_kind}`
- iteration: `{iter_name(iteration)}`
- case: `{case_id}`
- flow_variant: `{flow_variant}`
- threads: `{threads}`
- run_tag: `{run_tag}`
- parent_source: `{parent_src}`

## Start-Point / Patch Catalog Notes

- `round_default_start_kind` is only the default source seed used before Teacher
  assigns a route. If the top of your Student prompt includes `Initial
  workspace setup`, follow that setup first, then do the required source-level
  diagnosis before editing.
- If `start_kind` is `evolved_diamond`, `evolved_legalm`, or
  `evolved_negotiation`, your private source is already seeded from the
  corresponding materialized evolved legalizer source under
  `.dpl_evolve_state/seed_sources/`. Do not manually re-apply the OpenROAD-root
  patch to your private source.
- `prepare_source_script` also prepares local git start branches inside your
  private source repo:
  `start/framework`, `start/diamond`, `start/evolved_diamond`,
  `start/evolved_legalm`, and `start/evolved_negotiation`. It also prepares
  DPO donor combination branches when the patch applies, for example
  `start/evolved_legalm_dpo_neg017b`, `start/evolved_legalm_dpo_neg014`,
  `start/evolved_diamond_dpo_neg017b`, `start/diamond_dpo_neg017b`, and
  `start/framework_dpo_neg017b`. If Teacher assigns one of these start points,
  run `switch_start_branch_script --kind <branch-suffix>` before edits. The
  script resets your iteration branch `{paths.source_branch}` to that start
  point while keeping your final work on the normal iteration branch.
- Evolved legalizer patches are still useful as review/donor evidence. The
  `*_framework_delta.patch` files are deltas from prepared base+framework
  OpenROAD to the evolved legalizer line. The `*_from_clean.patch` files apply
  only to the clean OpenROAD anchor recorded in `metadata/anchors.json`.
- `evolved_diamond`, `evolved_legalm`, and `evolved_negotiation` are prior
  iter30 route-specific donor starts with measured wins on some archetypes. Use
  the matching evolved start when Teacher assigns it, or use the catalog to
  borrow a specific mechanism when your source-level diagnosis supports that
  route.
- Evolved DPO patches are improve-placement donor patches for the private
  source root. Prefer a prepared `start/<legalizer>_dpo_<donor>` branch when
  Teacher assigns a clean DPO-donor start. Use
  `apply_evolved_dpo_patch_script --donor neg017b --check-only` before applying
  the recommended runtime-quality donor, or `--donor neg014` for the
  quality-ceiling donor, only when Teacher assigns donor application to the
  current source. These patches can stack on a legalizer seed; do not hand-write
  `git apply`.

## Paths

- agent_root: `{runtime.agent_root}`
- optional_reference_index: `{runtime.agent_root / "family_variants" / "REFERENCE_INDEX.yaml"}`
- optional_legalm_reference: `{runtime.agent_root / "family_variants" / "legalm_guidance" / "README.md"}`
- optional_diamond_reference: `{runtime.agent_root / "family_variants" / "openroad_diamond" / "README.md"}`
- optional_negotiation_reference: `{runtime.agent_root / "family_variants" / "openroad_negotiation_nblg" / "README.md"}`
- optional_evolved_legalizer_catalog: `{runtime.agent_root / "patches" / "evolved_legalizers" / "README.md"}`
- optional_evolved_legalizer_manifest: `{runtime.agent_root / "patches" / "evolved_legalizers" / "generation_manifest.tsv"}`
- optional_evolved_legalizer_validation: `{runtime.agent_root / "patches" / "evolved_legalizers" / "validation.tsv"}`
- optional_evolved_diamond_framework_delta: `{runtime.agent_root / "patches" / "evolved_legalizers" / "openroad_dpl_evolve_diamond_iter30_framework_delta.patch"}`
- optional_evolved_legalm_framework_delta: `{runtime.agent_root / "patches" / "evolved_legalizers" / "openroad_dpl_evolve_legalm_iter30_framework_delta.patch"}`
- optional_evolved_negotiation_framework_delta: `{runtime.agent_root / "patches" / "evolved_legalizers" / "openroad_dpl_evolve_negotiation_iter30_framework_delta.patch"}`
- optional_evolved_dpo_catalog: `{runtime.agent_root / "patches" / "evolved_dpo" / "README.md"}`
- optional_evolved_dpo_manifest: `{runtime.agent_root / "patches" / "evolved_dpo" / "generation_manifest.tsv"}`
- optional_evolved_dpo_validation: `{runtime.agent_root / "patches" / "evolved_dpo" / "validation.tsv"}`
- optional_evolved_dpo_recommended_patch: `{runtime.agent_root / "patches" / "evolved_dpo" / "src_dpo_neg017b_algo1_src_cache_runtime.patch"}`
- optional_evolved_dpo_quality_patch: `{runtime.agent_root / "patches" / "evolved_dpo" / "src_dpo_neg014_hybrid_quality.patch"}`
- optional_dpo_runtime_quality_insight: `{runtime.agent_root / "knowledge" / "insights" / "dpo" / "dpo_runtime_quality_frontier.md"}`
- optional_dpo_cross_legalizer_insight: `{runtime.agent_root / "knowledge" / "insights" / "dpo" / "cross_legalizer_dpo_donors.md"}`
- skill_index: `{runtime.agent_root / "knowledge" / "index" / "skill_cards.jsonl"}`
- skill_cards_dir: `{runtime.agent_root / "knowledge" / "skills"}`
- algorithm_cards_dir: `{runtime.agent_root / "knowledge" / "algorithm_cards"}`
- skill_query_script: `{runtime.agent_root / "scripts" / "query_knowledge.py"}`
- generated_skill_query_helper: `{script_paths["query_knowledge"]}`
- lineage: `{lineage_path}`
- student_workspace: `{paths.student_workspace}`
- variant_root: `{paths.variant_root}`
- private_dpl_evolve_source: `{paths.dpl_src}`
- source_layout: `private_dpl_evolve_source` is the `dpl_evolve` module root;
  use `src/...`, `src/optimization/...`, and `src/objective/...` inside it.
  Do not append `tools/OpenROAD/src/dpl_evolve/` under this private source.
- source_src_dir: `{paths.dpl_src / "src"}`
- source_optimization_dir: `{paths.dpl_src / "src" / "optimization"}`
- source_objective_dir: `{paths.dpl_src / "src" / "objective"}`
- source_branch: `{paths.source_branch}`
- private_binary: `{paths.private_binary}`
- artifact_dir: `{paths.artifact_dir}`
- failed_attempts: `{paths.artifact_dir / "failed_attempts.jsonl"}`
- implementation_diff: `{paths.implementation_diff}`
- knowledge_card: `{paths.knowledge_card}`
- source_repo: `{paths.dpl_src}`
- source_base_commit: `{paths.source_base_record}`
- source_commit_record: `{paths.source_commit_record}`
- codex_session_state: `{paths.session_state}`
- codex_identity_env: `{paths.session_env_file}`
- command_script_dir: `{paths.student_workspace / "scripts"}`
- prepare_source_script: `{script_paths["prepare"]}`
- switch_start_branch_script: `{script_paths["switch_start_branch"]}`
- source_context_script: `{script_paths["source_context"]}`
- apply_evolved_legalizer_patch_script: `{script_paths["apply_evolved_patch"]}`
- apply_evolved_dpo_patch_script: `{script_paths["apply_evolved_dpo_patch"]}`
- build_variant_script: `{script_paths["build"]}`
- fresh_build_script: `{script_paths["fresh_build"]}`
- evaluate_candidate_script: `{script_paths["evaluate"]}`
- commit_source_script: `{script_paths["commit"]}`
- write_diff_script: `{script_paths["diff"]}`
- seed_knowledge_card_script: `{script_paths["knowledge_template"]}`
- after_edit_script: `{script_paths["after_edit"]}`
- peer_learning_packet: `{peer_learning_path}`
- teacher_plan_prompt: `{teacher_prompt_path}`
- teacher_plan_operation: `{teacher_operation_id}`
- teacher_plan_last_message:
  `{runtime.operations_dir / teacher_operation_id / "codex_last_message.txt"}`

Note: `source_commit_record` is written by the launched orchestrator after the
child finishes and records the committed source revision for this iteration.
The packet script path also writes a lightweight record for your own report.

## Mandatory Completion Gate

Before your final answer, complete these checks.  If any check fails, report
the exact blocker and do not call the candidate successful.

- source edited only under `private_dpl_evolve_source`
- `private_dpl_evolve_source` remains a local git repo and current branch is
  `{paths.source_branch}`
- commit your final source state before the final answer.  Use a concise commit
  message such as `{student_id} {iter_name(iteration)} mechanism`.  The
  orchestrator will create a fallback commit only if you leave uncommitted
  source changes.
- public Tcl/SWIG-wrapped class layout, especially `Opendp`, was not changed
  for ordinary algorithm state; if changed, Tcl startup was smoke-tested before
  full evaluation
- private binary exists at `private_binary`
- evaluation completed and wrote:
  `{expected_metrics_path(runtime=runtime, case_id=case_id, flow_variant=flow_variant, run_tag=run_tag)}`
- implementation diff exists and is non-empty:
  `{paths.implementation_diff}`
- knowledge card exists and is non-empty:
  `{paths.knowledge_card}`
- final answer includes metrics path, stage-wise HPWL deltas
  (`HPWLg`, `delta HPWLlg`, `delta HPWLip`, `delta HPWL final`,
  `HPWL final`), C_HR/H/R when available, runtime/displacement delta, diff
  path, knowledge card path, source commit, key counters/logs, and algorithmic
  validity/complexity assessment
- if a primary mechanism counter is zero, label that route as non-executed or
  negative evidence instead of claiming the mechanism ran

## Evaluation Timeout

- {timeout_note}
- If evaluation times out, stop that implementation path, report it as failed
  runtime evidence, and do not rerun the same mechanism.  If evaluation
  finishes well below the timeout with only a tiny HPWL gain, consider whether
  the assigned route was under-explored and whether a bounded wider search,
  exact scorer, batch transaction, or parallel candidate pass should be tested
  before finalizing.

## Required Skills

Read only these absolute repo-local skill paths for ordinary Student source
edits. Do not infer a `packet/skills/` directory and do not search for skills
relative to this packet:

- `{runtime.agent_root / "skills" / "patch_rules.md"}`
- `{runtime.agent_root / "skills" / "source_git_workflow.md"}`
- `{runtime.agent_root / "skills" / "build_openroad.md"}`
- `{runtime.agent_root / "skills" / "evaluate_run.md"}`
- `{runtime.agent_root / "skills" / "trace_logging.md"}` when the mechanism
  needs counters/logs.

Use orchestration/debug skills only if the generated helper fails and its error
is insufficient.

## Per-Iteration Execution Contract

- This packet is for one outer Teacher/Student iteration.
- Use the assigned A/B plan as the default source-level hypothesis:
  legalization/detailed placement and improve placement. Validate it against
  current source and metrics before coding, and refine it if source evidence
  shows a better mechanism. Keep `optimize_mirroring_evolve` callable for
  evaluation.
- Build at least one legalization/improve co-optimization link.
- Use generated scripts below for prepare/build/evaluate/diff/knowledge.
- If Teacher assigns `framework`, `diamond`, `evolved_diamond`,
  `evolved_legalm`, `evolved_negotiation`, or a prepared
  `<legalizer>_dpo_<donor>` start as this route's start point, use
  `switch_start_branch_script --kind <branch-suffix>` immediately after source
  preparation and before edits. Do not emulate this by manually copying source
  trees or applying patch files.
- Use `source_context_script` before nontrivial patches when you need current
  local source anchors. For donor-derived hunks or any edit based on Teacher
  prose rather than currently visible source text, this is mandatory. It only
  prints context; source edits still use `apply_patch`.
- If Teacher assigns patch application from an evolved legalizer family, use
  `apply_evolved_legalizer_patch_script --line diamond|legalm|negotiation
  --check-only` first, then apply exactly one compatible line with the same
  script. Do not manually run `git apply` on OpenROAD-root patch files.
- If Teacher assigns an evolved DPO donor on the current source, use
  `apply_evolved_dpo_patch_script --donor neg017b|neg014|neg015 --check-only`
  first, then apply exactly one compatible donor with the same script. These
  are source-root improve-placement patches; do not manually run `git apply`.
- If Teacher names a LEGO-lite skill id, query it with
  `generated_skill_query_helper --q <skill-id> --show-full` or use
  `--stage legalization|improve_placement|handoff --q <bottleneck>`.
  Treat the card as a mechanism contract: source handles, done criteria,
  metrics, and log signals. It guides but does not replace current source
  inspection.
- If the selected skill points to an algorithm/pseudocode card under
  `algorithm_cards_dir`, open only that card and translate its pseudocode into
  a local source plan before patching.
- Keep runtime bounded by the generated DPL flow timeout. The threshold is
  computed from canonical `metrics.json:runtime_seconds`, but the timeout is
  applied only to the OpenROAD legalize/improve/mirror flow. Metrics/evaluator
  collection is not timeout-wrapped.
- Treat runtime as a usable search budget, not only a failure condition.  If
  Teacher assigned an explore/aggressive route, spend that budget on a bounded
  mechanism that can materially change stage-wise or final HPWL; do not shrink
  the implementation back to a baseline-runtime retune unless source evidence
  proves the larger search is exhausted.
- After metrics exist, read only the canonical metrics/log data needed for the
  report.

## Generated Scripts

The fixed command scripts are already generated in your workspace. Use these
scripts instead of reconstructing shell commands or studying CMake/relink
internals.

- prepare source before editing: `{script_paths["prepare"]}`
- switch to a prepared local start branch when Teacher assigns one:
  `{script_paths["switch_start_branch"]}`
- print current source context for patch anchors: `{script_paths["source_context"]}`
- apply/check one evolved legalizer framework-delta patch when Teacher assigns
  that path: `{script_paths["apply_evolved_patch"]}`
- apply/check one evolved DPO source-root patch when Teacher assigns that path:
  `{script_paths["apply_evolved_dpo_patch"]}`
- query concise LEGO-lite mechanism skills:
  `{script_paths["query_knowledge"]}`
- relevant algorithm/pseudocode cards live under:
  `{runtime.agent_root / "knowledge" / "algorithm_cards"}`
- build after source edits: `{script_paths["build"]}`
- evaluate canonical metrics: `{script_paths["evaluate"]}`
- commit final source: `{script_paths["commit"]}`
- write implementation diff: `{script_paths["diff"]}`
- seed knowledge-card template if needed: `{script_paths["knowledge_template"]}`
- optional after-edit bundle: `{script_paths["after_edit"]}`
- optional fresh build fallback only if normal build fails:
  `{script_paths["fresh_build"]}`

Execution order:

1. Run `prepare_source_script`.
2. If Teacher assigns a prepared start point (`framework`, `diamond`,
   `evolved_diamond`, `evolved_legalm`, `evolved_negotiation`, or a prepared
   `<legalizer>_dpo_<donor>` branch), run `switch_start_branch_script --kind
   <branch-suffix>` before edits.
3. Use `source_context_script <src/...> [symbol]` for patch anchors, confirm
   your source-level mechanism, then edit only `private_dpl_evolve_source` with
   `apply_patch`.
4. If Teacher explicitly assigns an evolved patch application route, run
   `apply_evolved_legalizer_patch_script --line <line> --check-only`, then
   apply the same line with that script before your own mechanism edits.
5. If Teacher explicitly assigns an evolved DPO donor route, run
   `apply_evolved_dpo_patch_script --donor <donor> --check-only`, then apply
   the same donor with that script before evolving the improve-placement
   mechanism.
6. If Teacher assigns or implies a skill id, query the skill index and keep only
   the relevant skill note in context.
7. Run `build_variant_script`.
8. Run `evaluate_candidate_script`.
9. If the result is weak/illegal and time remains, revise the mechanism and
   rerun build/evaluate.
10. Run `commit_source_script`.
11. Run `write_diff_script`.
12. Write or complete `knowledge_card`.

Use `after_edit_script` only after source edits are complete; it runs build,
evaluate, commit, diff, and knowledge-card template creation in sequence.

Do not manually remove, move, archive, inspect, or overwrite CMake build
products. If a generated script fails, report that script path and its error
first; inspect lower-level build artifacts only when the script error proves
that is necessary.

The launched orchestrator also records or verifies the final commit in
`source_commit_record` after your session exits. Do not copy source trees for
lineage; the git commit is the lineage artifact.

## Knowledge Card

Write this file before your final answer:

`{paths.knowledge_card}`

Required sections:

- `Hypothesis`: the major flow or algorithm idea you tried.
- `Mechanism`: where it changes `detailed_placement_evolve` and/or
  `improve_placement_evolve`.  If downstream `optimize_mirroring_evolve`
  changes the final HPWL, describe it only as evaluation evidence, not as a
  modified mechanism.
- `Result`: stage-wise HPWL deltas, final HPWL/runtime/displacement/legality
  versus baseline.
- `Causal lesson`: what future students should borrow or avoid.
- `Next experiment`: the next aggressive test, not a tiny parameter tweak.

Also include a compact stage transition table with columns:

- `stage`
- `selected skill`
- `touched function/state`
- `expected behavior`
- `metric/log evidence`
- `done/fail reason`

## Locked Surfaces

- Do not edit evaluator, baseline Tcl, benchmark selection, root ORFS source,
  workspace helper scripts, generated command scripts, or classic
  `tools/OpenROAD/src/dpl`.
- This lock does not forbid source-level algorithm changes inside
  `private_dpl_evolve_source`. You may change internal
  `improve_placement_evolve` flow, endpoint order, pass gating, candidate
  scoring, parameterization, and legalization/improve handoff state when the
  change is bounded and proven by canonical stage metrics/runtime.
- Do not claim success through default-equivalent or no-op behavior.
- Prefer new helper files or `.cpp` implementation-local state over public
  wrapped-header layout changes for algorithm caches/handoff state.
""",
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
    chunks = [
        "# Generated Teacher Review Artifact Packet",
        "",
        "This packet is refreshed after child workers finish.  Treat "
        "`artifact_status=invalid` as non-promotable even if the child message "
        "sounds confident.",
        "",
        "Fast path: this packet already includes the validity gate, canonical "
        "metrics, artifact sizes, and exact evidence paths.  Read it once; for "
        "valid students, prefer the knowledge card for mechanism/lesson and "
        "avoid opening last messages, stderr, events, or diffs unless a field "
        "is missing or the mechanism is unclear.",
        "",
    ]
    for child in child_rounds:
        chunks.extend(
            [
                f"## {child.student_id}",
                f"- route_label: `{child.route_label}`",
                f"- operation_id: `{child.operation_id}`",
                f"- operation_dir: `{child.operation_dir}`",
                f"- run_tag: `{child.run_tag}`",
                f"- prompt: `{child.prompt_path}`",
                f"- workspace_packet: `{child.workspace_packet}`",
                f"- last_message: `{child.last_message}`",
                f"- usage_summary: `{child.usage_summary}`",
                f"- stderr_log: `{child.stderr_log}`",
                f"- events_large_do_not_read_by_default: `{child.events_jsonl}`",
                f"- student_workspace: `{child.student_workspace}`",
                f"- private_dpl_src: `{child.dpl_src}`",
                f"- source_branch: `{child.source_branch}`",
                f"- private_binary: `{child.private_binary}`",
                f"- failed_attempts: `{child.implementation_diff.parent / 'failed_attempts.jsonl'}`",
                f"- implementation_diff: `{child.implementation_diff}`",
                f"- knowledge_card: `{child.knowledge_card}`",
                f"- source_base_commit: `{child.source_base_record}`",
                f"- source_repo: `{child.dpl_src}`",
                f"- source_commit_record: `{child.source_commit_record}`",
                f"- codex_session_state: `{child.session_state}`",
                f"- codex_identity_env: `{child.session_env_file}`",
                child_artifact_status_block(
                    runtime=runtime,
                    case_id=case_id,
                    flow_variant=flow_variant,
                    child=child,
                ),
                "",
            ]
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
        elite_note = f"""
## Elite Seed Assignment

This student is the protected best-so-far continuation branch for this
iteration. The orchestrator will pre-seed your private source from:

`{elite_seed_source}`

Your task is not to continue your weaker prior workspace. Start from this
elite code path, then make the next case-specific improvement on top of it.
"""
    return render_prompt_template(
        "child_initial.md",
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
            "student_rules.md",
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
        elite_note = f"""
## Elite Seed Assignment

This student is the protected best-so-far continuation branch for this
iteration. The orchestrator will pre-seed the private source from:

`{elite_seed_source}`

Do not treat your prior private workspace as the parent for this iteration
unless Teacher explicitly says to compare against it. Start from the elite
source, then make the next aggressive improvement on top of that code.
"""
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
        "child_followup.md",
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
            "student_rules.md",
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
                r"switch_start_branch_script --kind\s+([A-Za-z0-9_]+)",
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
    files = sorted(round_dir.glob("iter_*/prompts/*.md")) + sorted(
        round_dir.glob("iter_*/packet/*.md")
    )
    for path in files:
        rel = path.relative_to(round_dir)
        text = path.read_text(encoding="utf-8", errors="replace")
        is_agent_prompt = "/prompts/" in f"/{rel.as_posix()}"
        file_warnings: list[str] = []
        if is_agent_prompt:
            file_warnings.extend(
                agent_prompt_warnings(
                    text, max_agent_prompt_bytes=max_agent_prompt_bytes
                )
            )
        warnings += len(file_warnings)
        rows.append(
            {
                "file": str(rel),
                "kind": "agent_prompt" if is_agent_prompt else "generated_packet",
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
