"""Prompt, packet, context, and prompt-audit generation."""
from __future__ import annotations

import datetime as dt
import json
import math
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from runtime_paths import clean_subprocess_env
from scripts.teacher_loop.common import (
    AGENT_ROOT,
    ChildRound,
    MetricSummary,
    iter_name,
    render_prompt_template,
    student_workspace_paths,
)
from scripts.teacher_loop.evidence import (
    baseline_artifact_block,
    candidate_artifacts,
    child_artifact_status_block,
    design_characteristics_block,
    discover_round_candidate_metrics,
    expected_metrics_path,
    metric_table,
    operation_artifact_block,
    parse_candidate_tag,
    stage_donor_signal,
    strongest_baseline_anchor,
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
            "source backups, and peer packet for evidence instead."
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
    student_runtime_multiplier: float = 4.0,
) -> str:
    if iteration <= 1:
        return "No prior peer results yet."

    round_id = round_dir.name
    previous = iter_name(iteration - 1)
    baseline_metrics: dict[str, MetricSummary | None] = {}
    for line in ("openroad_dpl_flow", "evolve_default"):
        run_tag = f"{round_id}_baseline_probe_{line}"
        baseline_metrics[line] = summarize_metrics(
            expected_metrics_path(
                runtime=runtime,
                case_id=case_id,
                flow_variant=flow_variant,
                run_tag=run_tag,
            )
        )
    _baseline_label, baseline = strongest_baseline_anchor(baseline_metrics)
    metrics_by_student: dict[str, MetricSummary] = {}
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
            metrics_by_student[student_id] = summary

    if not metrics_by_student:
        return (
            f"Previous iteration: `{previous}`\n\n"
            "No valid prior peer metrics were found. Use Teacher insight and "
            "your own source/log inspection; do not assume a peer mechanism is validated."
        )

    best_student = min(
        metrics_by_student,
        key=lambda student: (
            metrics_by_student[student].hpwl_after
            if metrics_by_student[student].hpwl_after is not None
            else float("inf")
        ),
    )
    lines = [
        f"Previous iteration: `{previous}`",
        "",
        "Peer evidence is only a pointer. Do not copy long peer reports into "
        "your reasoning. If you inspect a peer packet, source backup, or diff, "
        "first write your own 2-3 line summary of what worked before borrowing it.",
        "",
        f"Best previous clean peer by HPWL: `{best_student}`.",
    ]
    for student_id in sorted(metrics_by_student):
        summary = metrics_by_student[student_id]
        mechanism, lesson, next_step = peer_mechanism_summary(
            runtime=runtime,
            round_dir=round_dir,
            round_id=round_id,
            case_id=case_id,
            summary=summary,
        )
        label = "you" if student_id == current_student else "peer"
        hpwl = "" if summary.hpwl_after is None else f"{summary.hpwl_after:.3f}"
        runtime_s = (
            "" if summary.runtime_seconds is None else f"{summary.runtime_seconds:.3f}s"
        )
        avg_disp = "" if summary.avg_disp is None else f"{summary.avg_disp:.4f}"
        max_disp = "" if summary.max_disp is None else f"{summary.max_disp:.4f}"
        violations = summary.violations or "clean"
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
        details = []
        if mechanism:
            details.append(f"mechanism `{mechanism}`")
        if next_step:
            details.append(f"next `{next_step}`")
        suffix = "; " + "; ".join(details) if details else ""
        lines.append(
            "- {student} ({label}): HPWL `{hpwl}`, runtime `{runtime_s}`, "
            "avg/max disp `{avg_disp}/{max_disp}`, legality `{violations}`; "
            "stage `{stage_pct}`, signal `{signal}`{suffix}".format(
                student=student_id,
                label=label,
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
                suffix=suffix,
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
) -> tuple[int | None, str]:
    """Return the hard student evaluation timeout from canonical baseline runtime."""
    baseline_tag = f"{round_id}_baseline_probe_openroad_dpl_flow"
    baseline_path = expected_metrics_path(
        runtime=runtime,
        case_id=case_id,
        flow_variant=flow_variant,
        run_tag=baseline_tag,
    )
    baseline = summarize_metrics(baseline_path)
    runtime_s = baseline.runtime_seconds if baseline is not None else None
    if runtime_s is None or runtime_s <= 0:
        return (
            None,
            "Unavailable: canonical openroad_dpl_flow baseline runtime is missing. "
            f"Run baseline preflight first. Expected metrics: `{baseline_path}`",
        )
    multiplier_label = format_multiplier(runtime_multiplier)
    timeout_s = max(1, int(math.ceil(runtime_s * runtime_multiplier)))
    return (
        timeout_s,
        "Hard timeout: "
        f"`{timeout_s}s` = {multiplier_label}x canonical openroad_dpl_flow baseline runtime "
        f"`{runtime_s:.3f}s`. Timeout-killed runs are non-promotable.",
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
                / "source_backups"
                / iter_name(iteration - 1)
                / "dpl_evolve"
            )
        return student_workspace_paths(
            round_dir=round_dir,
            iteration=iteration - 1,
            student_id=student_id,
            stable_workspace=stable_workspace,
        ).dpl_src
    return start_kind_source(runtime, start_kind)


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
    seed_args = (
        f" \\\n  --seed-src {shlex.quote(str(parent_src))} \\\n  --force"
        if use_seed_override
        else ""
    )
    timeout_seconds, timeout_note = child_evaluation_timeout(
        runtime=runtime,
        case_id=case_id,
        flow_variant=flow_variant,
        round_id=round_dir.name,
        runtime_multiplier=student_runtime_multiplier,
    )
    run_baseline_cmd = shlex.quote(str(AGENT_ROOT / "baseline" / "run_baseline.sh"))
    if timeout_seconds is None:
        evaluate_command_head = run_baseline_cmd
    else:
        evaluate_command_head = (
            f"timeout --kill-after=30s {timeout_seconds}s \\\n  {run_baseline_cmd}"
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
- start_kind: `{start_kind}`
- iteration: `{iter_name(iteration)}`
- case: `{case_id}`
- flow_variant: `{flow_variant}`
- threads: `{threads}`
- run_tag: `{run_tag}`
- parent_source: `{parent_src}`

## Paths

- lineage: `{lineage_path}`
- student_workspace: `{paths.student_workspace}`
- variant_root: `{paths.variant_root}`
- private_dpl_evolve_source: `{paths.dpl_src}`
- private_binary: `{paths.private_binary}`
- artifact_dir: `{paths.artifact_dir}`
- implementation_diff: `{paths.implementation_diff}`
- knowledge_card: `{paths.knowledge_card}`
- source_backup_after_iteration: `{paths.source_backup}`
- codex_session_state: `{paths.session_state}`
- codex_identity_env: `{paths.session_env_file}`
- peer_learning_packet: `{peer_learning_path}`
- teacher_plan_prompt: `{teacher_prompt_path}`
- teacher_plan_operation: `{teacher_operation_id}`
- teacher_plan_last_message:
  `{runtime.operations_dir / teacher_operation_id / "codex_last_message.txt"}`

Note: `source_backup_after_iteration` is created by the launched orchestrator
after the child finishes. The packet-only manual path does not create it.

## Mandatory Completion Gate

Before your final answer, complete these checks.  If any check fails, report
the exact blocker and do not call the candidate successful.

- source edited only under `private_dpl_evolve_source`
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
  `HPWL final`), runtime/displacement delta, diff path, knowledge card path,
  and algorithmic validity/complexity assessment

## Evaluation Timeout

- {timeout_note}
- If evaluation times out, stop that implementation path, report it as failed
  runtime evidence, and do not rerun the same mechanism.

## Per-Iteration Execution Budget

- This packet is for one outer Teacher/Student iteration.
- Required source surface: modify legalization, improve placement, and
  mirror/orientation.
- You may use any canonical baseline line as a source donor or start-point
  hypothesis, including Diamond/openroad_dpl_flow. The evaluation still runs
  through the evolved commands, so report which line influenced the source
  changes and how the evolved behavior differs.
- Do not buy HPWL by simply running improve placement more times, repeating
  random tails, or stacking endpoints.  Distill any such clue into one bounded
  mechanism.  It is encouraged to spend available timeout budget on a deeper
  bounded improve-placement algorithm when the source change modifies
  candidates, objective, acceptance, local state, or handoff consumption.
- Work through the assigned mechanism concretely: plan related edits A/B/C for
  legalization, improve placement, and mirror/orientation; implement all three;
  add at least one legalization/improve co-optimization link where
  improve-placement scoring, candidate choice, local HPWL deltas, residual-net
  priorities, or orientation handoff affects legal-state generation;
  make the improve-placement edit concrete in `Optdp` or detailed-improvement
  support code rather than only changing an endpoint script;
  build and evaluate; inspect canonical
  `metrics.json:hpwl`, `metrics.json:hpwl_stages` when present, plus the
  relevant OpenROAD log; revise the algorithm when the result is weak or
  illegal; rebuild and re-evaluate; keep the best clean candidate.
- Revisions must change the algorithmic mechanism or its commit/selection
  logic, not only retune constants. Stop when the best clean candidate is
  clearly recorded, the mechanism is exhausted, or the blocker is concrete
  enough for Teacher to act on.
- Keep the implementation high-performance.  Do not extend slow endpoint
  families, repeated random tails, or unbounded scans for a small HPWL delta.
  If the mechanism is not plausibly making material progress toward the 5%
  research target, pivot to a bounded structural change.  For `Optdp`, prefer
  touched-net/local-box caches, compact candidate queues, and deterministic
  move/swap/window ordering over full rescans.  Keep the best bounded clean
  candidate.
- After a clean `metrics.json` exists, read only the metrics needed for the
  final report. Do not inspect evaluator/helper scripts, `post_metrics` files,
  or log tails unless the command failed or metrics are missing.
- Build/evaluation infrastructure is not your research target. Use only the
  generated commands in this packet. Do not inspect `link.txt`, reconstruct
  relink commands, or manually run `ar`, `ranlib`, `nm`, `strings`, `ldd`,
  `readelf`, or equivalent binary/link debugging. If a generated helper fails,
  fix the source issue or report the helper error as the blocker.
- Trust generated helper commands. Do not read `run_baseline.sh`,
  `build_openroad_variant_relink.py`, evaluator code, wrapper scripts, CMake
  link files, or object/archive contents.
- Do not invent relative build directories such as `build_iter03c`; every
  build directory must be an absolute path under `variant_root`.
- Do not dump full context, full event logs, or generic memory registries by
  default. Use targeted `rg`/small excerpts when extra evidence is needed.
- Teacher should have distilled the useful knowledge for this turn. Open memory
  files only when a concrete source decision needs extra evidence.
- Before the first source edit, keep exploration bounded: use `rg` first and at
  most a few small `nl -ba ... | sed -n` windows around exact symbols. Keep
  each window small enough to understand the patch site; do not page through
  hundreds of lines, whole source files, donor trees, event logs, or memory
  registries. If more source reading is unavoidable, state why in the final
  report.
- If a patch does not apply, inspect only the nearby current source around the
  intended function/state, then re-apply a smaller patch. Do not turn patch
  recovery into build-system or relink investigation.

## Prepare

```bash
mkdir -p {shlex.quote(str(paths.variant_root))}
{shlex.quote(str(runtime.agent_root / "scripts" / "create_variant_start.sh"))} \\
  --orfs-root {shlex.quote(str(runtime.orfs_root))} \\
  --variant-root {shlex.quote(str(paths.variant_root))} \\
  --start-kind {shlex.quote(start_kind)} \\
  --dpl-src {shlex.quote(str(paths.dpl_src))}{seed_args}
mkdir -p {shlex.quote(str(paths.artifact_dir))}
```

## Build

```bash
{shlex.quote(str(runtime.agent_root / "scripts" / "configure_openroad_variant_relink.sh"))} \\
  --variant-root {shlex.quote(str(paths.variant_root))} \\
  --dpl-src {shlex.quote(str(paths.dpl_src))}

{shlex.quote(str(runtime.agent_root / "scripts" / "build_openroad_variant_relink.sh"))} \\
  --variant-root {shlex.quote(str(paths.variant_root))} \\
  --dpl-src {shlex.quote(str(paths.dpl_src))} \\
  --threads {threads}
```

## Generated Fresh Build-Dir Command

Use this only if the normal generated build command returns nonzero or the
normal generated build demonstrably leaves `private_binary` missing. Run the
block exactly as written. Do not inspect CMake link files, object files, or
archives, and do not handcraft a relink command.

```bash
FRESH_BUILD_DIR={shlex.quote(str(paths.variant_root / "build_fresh"))}
{shlex.quote(str(runtime.agent_root / "scripts" / "configure_openroad_variant_relink.sh"))} \\
  --variant-root {shlex.quote(str(paths.variant_root))} \\
  --build-dir "$FRESH_BUILD_DIR" \\
  --dpl-src {shlex.quote(str(paths.dpl_src))}

{shlex.quote(str(runtime.agent_root / "scripts" / "build_openroad_variant_relink.sh"))} \\
  --variant-root {shlex.quote(str(paths.variant_root))} \\
  --build-dir "$FRESH_BUILD_DIR" \\
  --dpl-src {shlex.quote(str(paths.dpl_src))} \\
  --threads {threads}
```

Do not manually `rm`, `mv`, archive, inspect, or overwrite CMake build
products.

## Evaluate

```bash
{evaluate_command_head} \\
  --line evolve_default \\
  --case {shlex.quote(case_id)} \\
  --flow-variant {shlex.quote(flow_variant)} \\
  --threads {threads} \\
  --openroad-binary {shlex.quote(str(paths.private_binary))} \\
  --run-tag {shlex.quote(run_tag)}
```

## Diff

```bash
diff -ruN \\
  {shlex.quote(str(parent_src))} \\
  {shlex.quote(str(paths.dpl_src))} \\
  > {shlex.quote(str(paths.implementation_diff))} || true
```

## Knowledge Card

Write this file before your final answer:

`{paths.knowledge_card}`

Required sections:

- `Hypothesis`: the major flow or algorithm idea you tried.
- `Mechanism`: where it changes `detailed_placement_evolve`,
  `improve_placement_evolve`, or `optimize_mirroring_evolve`.
- `Result`: stage-wise HPWL deltas, final HPWL/runtime/displacement/legality
  versus baseline.
- `Causal lesson`: what future students should borrow or avoid.
- `Next experiment`: the next aggressive test, not a tiny parameter tweak.

## Locked Surfaces

- Do not edit evaluator, baseline Tcl, benchmark selection, root ORFS source,
  or classic `tools/OpenROAD/src/dpl`.
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
                f"- private_binary: `{child.private_binary}`",
                f"- implementation_diff: `{child.implementation_diff}`",
                f"- knowledge_card: `{child.knowledge_card}`",
                f"- source_backup_after_iteration: `{child.source_backup}`",
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
    student_runtime_multiplier: float = 4.0,
) -> str:
    elite_note = ""
    if elite_seed_source is not None:
        elite_note = f"""
## Elite Seed Assignment

This student is the protected best-so-far continuation branch for this
iteration.  The orchestrator will pre-seed your private source from:

`{elite_seed_source}`

Your task is not to continue your weaker prior workspace.  Start from this
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
    student_runtime_multiplier: float = 4.0,
) -> str:
    elite_note = ""
    if elite_seed_source is not None:
        elite_note = f"""
## Elite Seed Assignment

This student is the protected best-so-far continuation branch for this
iteration.  The orchestrator will pre-seed the private source from:

`{elite_seed_source}`

Do not treat your prior private workspace as the parent for this iteration
unless Teacher explicitly says to compare against it.  Start from the elite
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
    "historical",
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
