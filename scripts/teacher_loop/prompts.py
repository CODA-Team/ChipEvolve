"""Prompt, packet, context, and prompt-audit generation."""
from __future__ import annotations

import datetime as dt
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from runtime_paths import clean_subprocess_env
from scripts.teacher_loop.common import (
    AGENT_ROOT,
    STRATEGY_BRIEFS,
    ChildRound,
    MetricSummary,
    iter_name,
    render_prompt_template,
    student_workspace_paths,
)
from scripts.teacher_loop.evidence import (
    baseline_artifact_block,
    child_artifact_status_block,
    design_characteristics_block,
    discover_round_candidate_metrics,
    expected_metrics_path,
    metric_table,
    operation_artifact_block,
    parse_candidate_tag,
)


def read_text_excerpt(path: Path, *, max_chars: int = 6000) -> str:
    if not path.exists():
        return f"Missing: `{path}`"
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return f"Empty: `{path}`"
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[excerpt truncated]"


def previous_teacher_review_excerpt(
    *, runtime: Any, round_id: str, iteration: int, max_chars: int = 6000
) -> str:
    if iteration <= 1:
        return "No previous Teacher review exists yet."
    review_op = f"{round_id}_{iter_name(iteration - 1)}_teacher_review"
    return read_text_excerpt(
        runtime.operations_dir / review_op / "codex_last_message.txt",
        max_chars=max_chars,
    )


def focused_message_excerpt(text: str, *, max_chars: int = 900) -> str:
    keep: list[str] = []
    keywords = (
        "mechanism",
        "HPWL",
        "runtime",
        "avg",
        "max",
        "delta",
        "borrow",
        "next",
        "validity",
        "complexity",
        "metrics",
    )
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if any(keyword.lower() in line.lower() for keyword in keywords):
            keep.append(line)
        if len("\n".join(keep)) >= max_chars:
            break
    excerpt = "\n".join(keep) if keep else text.strip()
    if len(excerpt) <= max_chars:
        return excerpt
    return excerpt[:max_chars].rstrip() + "\n[truncated]"


def peer_briefing(
    *,
    runtime: Any,
    round_dir: Path,
    case_id: str,
    flow_variant: str,
    iteration: int,
    current_student: str,
) -> str:
    if iteration <= 1:
        return "No prior peer results yet."

    round_id = round_dir.name
    previous = iter_name(iteration - 1)
    metrics_by_student: dict[str, MetricSummary] = {}
    for summary in discover_round_candidate_metrics(
        orfs_root=runtime.orfs_root,
        case_id=case_id,
        flow_variant=flow_variant,
        round_id=round_id,
    ):
        iter_part, student_id, _strategy = parse_candidate_tag(
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

    lines = [
        f"Previous iteration: `{previous}`",
        "",
        "| student | hpwl_after | runtime_s | avg_disp | max_disp | violations | reported mechanism / next clue |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for student_id in sorted(metrics_by_student):
        summary = metrics_by_student[student_id]
        exact_message = (
            runtime.operations_dir
            / f"{round_id}_{previous}_{student_id}"
            / "codex_last_message.txt"
        )
        op_matches = sorted(
            runtime.operations_dir.glob(
                f"{round_id}_{previous}_{student_id}_*/codex_last_message.txt"
            )
        )
        if exact_message.exists():
            op_matches.insert(0, exact_message)
        msg = (
            focused_message_excerpt(op_matches[0].read_text(encoding="utf-8", errors="replace"))
            if op_matches
            else "No last_message found."
        )
        label = "you" if student_id == current_student else "peer"
        lines.append(
            "| {student} ({label}) | {hpwl} | {runtime_s} | {avg_disp} | "
            "{max_disp} | {violations} | {msg} |".format(
                student=student_id,
                label=label,
                hpwl="" if summary.hpwl_after is None else f"{summary.hpwl_after:.3f}",
                runtime_s=""
                if summary.runtime_seconds is None
                else f"{summary.runtime_seconds:.3f}",
                avg_disp="" if summary.avg_disp is None else f"{summary.avg_disp:.4f}",
                max_disp="" if summary.max_disp is None else f"{summary.max_disp:.4f}",
                violations=summary.violations or "clean",
                msg=msg.replace("|", "\\|").replace("\n", "<br>"),
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
    for idx, strategy in enumerate(strategies, start=1):
        student_id = f"student_{idx:02d}"
        child_op = f"{round_id}_{iter_name(previous)}_{student_id}"
        blocks.append(f"### {student_id}: {strategy}")
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
    )


def teacher_prompt(
    *,
    context_path: Path,
    strategies: list[str],
    children: int,
    iteration: int,
) -> str:
    strategy_lines = "\n".join(
        f"- `{name}`: {STRATEGY_BRIEFS.get(name, 'Custom bounded mechanism.')}"
        for name in strategies
    )
    return render_prompt_template(
        "teacher_plan.md",
        context_path=context_path,
        iteration_name=iter_name(iteration),
        strategy_lines=strategy_lines,
        children=children,
    )


def compact_teacher_prompt(
    *,
    context_path: Path,
    strategies: list[str],
    children: int,
    iteration: int,
) -> str:
    strategy_lines = "\n".join(
        f"- `{idx:02d}` `{name}`: {STRATEGY_BRIEFS.get(name, 'Custom bounded mechanism.')}"
        for idx, name in enumerate(strategies, start=1)
    )
    return render_prompt_template(
        "teacher_plan_compact.md",
        context_path=context_path,
        iteration_name=iter_name(iteration),
        strategy_lines=strategy_lines,
        children=children,
    )


def teacher_review_prompt(
    *,
    context_path: Path,
    review_packet_path: Path,
) -> str:
    return render_prompt_template(
        "teacher_review.md",
        context_path=context_path,
        review_packet_path=review_packet_path,
    )


def compact_teacher_review_prompt(
    *,
    context_path: Path,
    review_packet_path: Path,
) -> str:
    return render_prompt_template(
        "teacher_review_compact.md",
        context_path=context_path,
        review_packet_path=review_packet_path,
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
    strategy: str,
    child_id: int,
    iteration: int,
    student_id: str,
    run_tag: str,
    stable_workspace: bool,
    elite_seed_source: Path | None,
    peer_learning_path: Path,
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
    lineage_path = round_dir / "students" / student_id / "lineage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# Generated Workspace Packet: {student_id}

This file is generated by the orchestrator.  It contains exact paths and
commands.  Do not ask Teacher to rewrite this content.

## Identity

- child_id: `{child_id}`
- student_id: `{student_id}`
- exploration_seed: `{strategy}`
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
- private binary exists at `private_binary`
- evaluation completed and wrote:
  `{expected_metrics_path(runtime=runtime, case_id=case_id, flow_variant=flow_variant, run_tag=run_tag)}`
- implementation diff exists and is non-empty:
  `{paths.implementation_diff}`
- knowledge card exists and is non-empty:
  `{paths.knowledge_card}`
- final answer includes metrics path, HPWL/runtime/displacement delta, diff path,
  knowledge card path, and algorithmic validity/complexity assessment

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

## Evaluate

```bash
{shlex.quote(str(AGENT_ROOT / "baseline" / "run_baseline.sh"))} \\
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
- `Result`: HPWL/runtime/displacement/legality versus baseline.
- `Causal lesson`: what future students should borrow or avoid.
- `Next experiment`: the next aggressive test, not a tiny parameter tweak.

## Locked Surfaces

- Do not edit evaluator, baseline Tcl, benchmark selection, root ORFS source,
  or classic `tools/OpenROAD/src/dpl`.
- Do not claim success through default-equivalent or no-op behavior.
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
    ]
    for child in child_rounds:
        chunks.extend(
            [
                f"## {child.student_id}",
                f"- exploration_seed: `{child.strategy}`",
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
    strategy: str,
    child_id: int,
    iteration: int,
    student_id: str,
    run_tag: str,
    workspace_packet_path: Path,
    peer_learning_path: Path,
    compact: bool = False,
    stable_workspace: bool = False,
    elite_seed_source: Path | None = None,
) -> str:
    brief = STRATEGY_BRIEFS.get(strategy, "Custom bounded mechanism.")
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
        strategy=strategy,
        iteration_name=iter_name(iteration),
        strategy_brief=brief,
        workspace_packet_path=workspace_packet_path,
        peer_learning_path=peer_learning_path,
        teacher_plan_last_message=runtime.operations_dir
        / teacher_operation_id
        / "codex_last_message.txt",
        elite_note=elite_note,
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
    strategy: str,
    child_id: int,
    iteration: int,
    student_id: str,
    run_tag: str,
    workspace_packet_path: Path,
    peer_learning_path: Path,
    stable_workspace: bool = False,
    elite_seed_source: Path | None = None,
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
    )

    return render_prompt_template(
        "child_followup.md",
        context_path=context_path,
        student_id=student_id,
        strategy=strategy,
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
        "## Student Exploration Seeds",
        *[f"- `{name}`: {STRATEGY_BRIEFS.get(name, 'Custom bounded mechanism.')}" for name in strategies],
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
)


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
            if len(text.encode("utf-8")) > max_agent_prompt_bytes:
                file_warnings.append(
                    f"agent prompt exceeds {max_agent_prompt_bytes} bytes"
                )
            for term in PROMPT_FORBIDDEN_TERMS:
                if term in text:
                    file_warnings.append(f"agent prompt contains `{term}`")
            if text.count("/home/") > 35:
                file_warnings.append("agent prompt has many absolute paths")
        repeated_lines = []
        seen: dict[str, int] = {}
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("|") or len(line) < 24:
                continue
            seen[line] = seen.get(line, 0) + 1
        repeated_lines = [line for line, count in seen.items() if count > 2]
        if is_agent_prompt and repeated_lines:
            file_warnings.append(
                "agent prompt repeats lines: " + "; ".join(repeated_lines[:3])
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
