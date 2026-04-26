#!/usr/bin/env python3
"""Teacher/child Codex entrypoint for case-specific DPL-Evolve optimization.

This script is intentionally an orchestration layer, not another evaluator.
It creates a teacher-authored optimization round for one case, writes bounded
child prompts, and optionally launches `codex exec` workers through the existing
`run_codex_exec.py` recorder.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from runtime_paths import clean_subprocess_env, resolve_runtime_paths
from scripts.case_registry import get_case


DEFAULT_STRATEGIES = [
    "stage_a_guidance",
    "stage2_assignment_quality",
    "stage3_hpwl_polish",
    "large_case_runtime_guard",
    "paper_faithful_alm_bgd",
    "telemetry_stage_selector",
]

CANONICAL_LINES = (
    "openroad_dpl_flow",
    "evolve_default",
)

STRATEGY_BRIEFS = {
    "stage_a_guidance": (
        "Open exploration lane seeded by relaxed/static/differential guidance. "
        "The student may keep, replace, or ignore that seed after reading the "
        "case evidence and source references."
    ),
    "stage2_assignment_quality": (
        "Open exploration lane seeded by row/segment assignment quality.  The "
        "student may pivot to any stronger mechanism that can beat the case "
        "baseline under strict legality."
    ),
    "stage3_hpwl_polish": (
        "Open exploration lane seeded by post-legal HPWL polish.  The student "
        "may broaden the implementation surface if polish alone is too weak."
    ),
    "large_case_runtime_guard": (
        "Open exploration lane seeded by large-case runtime discipline.  The "
        "student may redesign stage order, data structures, or algorithms as "
        "long as runtime and legality remain independently measurable."
    ),
    "paper_faithful_alm_bgd": (
        "Open exploration lane seeded by LEGALM-style ALM/BGD ideas.  Respect "
        "papers as donors, not handcuffs; optimize the active case."
    ),
    "telemetry_stage_selector": (
        "Open exploration lane seeded by telemetry-driven stage selection.  The "
        "student may implement a different case-specific algorithm if the data "
        "supports it."
    ),
}


@dataclass(frozen=True)
class MetricSummary:
    tag: str
    metrics_path: Path
    mode: str
    hpwl_after: float | None
    hpwl_delta: float | None
    runtime_seconds: float | None
    avg_disp: float | None
    max_disp: float | None
    violations: str


@dataclass(frozen=True)
class ChildRound:
    student_id: str
    strategy: str
    operation_id: str
    run_tag: str
    prompt_path: Path
    operation_dir: Path
    last_message: Path
    usage_summary: Path
    stderr_log: Path
    events_jsonl: Path
    student_workspace: Path
    variant_root: Path
    dpl_src: Path
    private_binary: Path
    implementation_diff: Path
    source_backup: Path


@dataclass(frozen=True)
class StudentWorkspace:
    student_workspace: Path
    variant_root: Path
    dpl_src: Path
    variant_env: Path
    private_binary: Path
    artifact_dir: Path
    implementation_diff: Path
    source_backup: Path


def student_workspace_paths(
    *,
    round_dir: Path,
    iteration: int,
    student_id: str,
    stable_workspace: bool = False,
) -> StudentWorkspace:
    student_root = round_dir / "students" / student_id
    if stable_workspace:
        student_workspace = student_root / "workspace"
        artifact_dir = student_root / iter_name(iteration) / "artifacts"
    else:
        student_workspace = student_root / iter_name(iteration)
        artifact_dir = student_workspace / "artifacts"
    variant_root = student_workspace / "variant"
    dpl_src = variant_root / "dpl_evolve"
    return StudentWorkspace(
        student_workspace=student_workspace,
        variant_root=variant_root,
        dpl_src=dpl_src,
        variant_env=variant_root / "variant_env.sh",
        private_binary=variant_root / "install" / "OpenROAD" / "bin" / "openroad",
        artifact_dir=artifact_dir,
        implementation_diff=artifact_dir / "implementation.diff",
        source_backup=student_root / "source_backups" / iter_name(iteration) / "dpl_evolve",
    )


def default_round_id(case_id: str) -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"teacher_{case_id}_{stamp}"


def iter_name(iteration: int) -> str:
    return f"iter_{iteration:02d}"


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
    return MetricSummary(
        tag=metrics_path.parent.name,
        metrics_path=metrics_path,
        mode=str(legalization.get("legalizer_mode", "")),
        hpwl_after=hpwl.get("after_micron"),
        hpwl_delta=hpwl.get("delta_micron"),
        runtime_seconds=data.get("runtime_seconds"),
        avg_disp=disp.get("average_displacement_micron"),
        max_disp=disp.get("max_displacement_micron"),
        violations=str(legal.get("placement_violations", "")),
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
        tag = summary.tag
        if summary.mode == "openroad_dpl_flow" or "openroad_dpl_flow" in tag:
            by_line["openroad_dpl_flow"] = summary
        if summary.mode == "evolve_default" or "evolve_default" in tag:
            by_line["evolve_default"] = summary

    return by_line


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
        f"{round_id}_baseline",
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


def operation_artifact_block(runtime: Any, operation_id: str) -> str:
    op_dir = runtime.operations_dir / operation_id
    return f"""- operation_id: `{operation_id}`
  operation_dir: `{op_dir}`
  last_message: `{op_dir / "codex_last_message.txt"}`
  usage_summary: `{op_dir / "codex_usage_summary.json"}`
  events_large_do_not_read_by_default: `{op_dir / "codex_events.jsonl"}`
  stderr: `{op_dir / "codex_stderr.log"}`
"""


def operation_thread_id(runtime: Any, operation_id: str) -> str | None:
    summary = load_json(runtime.operations_dir / operation_id / "codex_usage_summary.json")
    if not summary:
        return None
    thread_id = summary.get("thread_id")
    return str(thread_id) if thread_id else None


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
        "## Previous Child Artifacts",
    ]
    for idx, strategy in enumerate(strategies, start=1):
        student_id = f"student_{idx:02d}"
        child_op = f"{round_id}_{iter_name(previous)}_{student_id}_{strategy}"
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


def compact_context(
    *,
    case_id: str,
    flow_variant: str,
    threads: int,
    runtime: Any,
    round_id: str,
    iteration: int,
    full_context_path: Path,
) -> str:
    return f"""# Compact Teacher Context

This is a resumed/compact iteration prompt.  The stable project context,
baseline table, prior Teacher review paths, donor references, and command
boundary are stored here:

`{full_context_path}`

Use that file as the source of truth when you need details.  Do not assume the
full context is repeated in this prompt.

Essential current facts:

- case: `{case_id}`
- flow_variant: `{flow_variant}`
- threads: `{threads}`
- round_id: `{round_id}`
- iteration: `{iter_name(iteration)}`
- ORFS root: `{runtime.orfs_root}`
- agent root: `{runtime.agent_root}`
- state root: `{runtime.state_root}`
- strict comparison anchors: the orchestrator collects the canonical suite
  before Teacher planning: `openroad_dpl_flow` and `evolve_default`.
- evolved entrypoint: `detailed_placement_evolve -> improve_placement_evolve
  -> optimize_mirroring_evolve`.
- implementation surface: private `dpl_evolve` variant only; do not edit root
  ORFS source, evaluator, baseline Tcl, or classic `dpl`.

The first long prompt established the full loop.  In this compact follow-up,
continue your own student session and focus on the next algorithmic move.
"""


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
    runtime: Any,
    metrics: dict[str, MetricSummary | None],
    packet_path: Path,
    round_id: str,
    iteration: int,
    prior_context: str,
) -> str:
    host_openroad_bin = (
        runtime.orfs_root / "tools" / "OpenROAD" / "build" / "bin" / "openroad"
    )
    return f"""# Teacher Context

We are optimizing one case with the constrained `detailed_placement_evolve`
framework.

- case: `{case_id}`
- flow_variant: `{flow_variant}`
- threads: `{threads}`
- ORFS root: `{runtime.orfs_root}`
- agent root: `{runtime.agent_root}`
- state root: `{runtime.state_root}`
- current packet: `{packet_path}`
- host OpenROAD binary seed: `{host_openroad_bin}`
- round_id: `{round_id}`
- iteration: `{iter_name(iteration)}`
- LEGALM guidance reference:
  `{runtime.agent_root / "family_variants" / "legalm_guidance"}`

## Student Startpoints

Students start from concrete code and framework guidance, not from blank-page
brainstorming:

- Current evolved framework source:
  `{runtime.orfs_root / "tools" / "OpenROAD" / "src" / "dpl_evolve" / "src"}`
- LEGALM-guidance source reference:
  `{runtime.agent_root / "family_variants" / "legalm_guidance"}`
- OpenROAD Diamond code reference:
  `{runtime.agent_root / "family_variants" / "openroad_diamond"}`
- OpenROAD negotiation/NBLG repair donor:
  `{runtime.agent_root / "family_variants" / "openroad_negotiation_nblg"}`
- DREAMPlace/Abacus row-assignment donor:
  `{runtime.agent_root / "family_variants" / "dreamplace_abacus"}`

The current evolved framework source is a real starting pipeline, not a blank
page: LEGALM-style guidance, row-assignment guidance, full LEGALM-style
legalization, then Abacus-enabled negotiation repair when needed.  The student
may replace any stage or the entire `Opendp::runStudentAlgorithm` path when
case evidence suggests a stronger route.

Teacher must translate these donor references into aggressive top-level stage
guidance for the active case. Child workers may inspect multiple donors when a
larger algorithmic pivot is justified.

## Case Optimization Target

Optimize the active case aggressively but honestly:

- The current strict comparison anchors are collected before Teacher planning:
  `openroad_dpl_flow` and `evolve_default`.
- `openroad_dpl_flow` is the primary score anchor for strict HPWL.
- `evolve_default` is the clean evolved command row that tells Teacher how far
  the current root framework is from the OpenROAD DPL anchor.
- DreamPlace/Abacus remains a source donor, not an automatic baseline row.
- Do not create extra comparison lines inside the student task unless the
  human explicitly asks for them.  The orchestrator owns baseline collection.
- This optimization round starts from a measured baseline-suite preflight.  If
  any canonical row is missing, treat the round as incomplete rather than
  making a promotion decision.
- Strict legality is a hard gate.
- Strict final HPWL is the primary optimization target after legality.  Runtime
  is a soft research constraint: a moderate runtime increase is acceptable when
  it buys a meaningful strict HPWL improvement and leaves displacement
  explainable.
- Runtime and displacement regressions must be explained, not hidden.  They are
  reasons to add a sharper objective, admission test, rollback, or data
  structure, not reasons to retreat automatically to a no-op.
- The goal is to beat the baseline on the active case by enough margin to
  matter.  Tiny HPWL wins are evidence that the loop works, but they are not
  the end state.  Teacher should push students toward bold algorithmic changes
  when conservative edits only produce marginal movement.
- Broad rewrites and large-scale placement perturbations are allowed and often
  desirable.  Do not treat "moves many cells" as a failure by itself.  Judge
  whether the mechanism converts that freedom into strict HPWL/runtime/legal
  improvement, and if it does not, ask for better scoring, rollback, telemetry,
  or a stronger structural hypothesis rather than simply becoming conservative.
- A useful child result either improves the case or exposes enough code-level
  evidence for Teacher to demand a bigger pivot next iteration.  No-op,
  baseline-equivalent, or pure threshold-only results are useful only as
  controls; they should not dominate the next round.

## Build And Isolation Contract

Children must not edit the root ORFS source as their normal implementation
surface.  The root source is a seed/reference.  Each child must work inside its
own private variant source under the round directory and build a private
OpenROAD binary by relinking only `dpl_evolve` artifacts.

Default child build mode:

1. Copy or continue a private `dpl_evolve` source tree under
   `state_root/teacher_rounds/<round>/students/<student>/<iter>/variant/dpl_evolve`.
2. Edit only that private source tree.
3. Run `scripts/configure_openroad_variant_relink.sh`.
4. Run `scripts/build_openroad_variant_relink.sh`.
5. Evaluate with the private binary from the variant `install/OpenROAD/bin`.

The Teacher/Student loop uses private variant relink because it lets a student
change any evolved DPL stage while still avoiding root ORFS edits.  A child
that edits `OpenROAD-flow-scripts/tools/OpenROAD/src/dpl_evolve` directly must
call that out as a protocol violation, not as a clean result.

## Current Architecture

Teacher owns the loop:

1. Choose one case and one hypothesis.
2. Dispatch multiple child Codex workers with different bounded mechanisms.
3. Each child continues from its own previous implementation direction when
   available, edits only the evolved DPL implementation, builds, evaluates, and
   leaves evidence.
4. Teacher reads each student's result, reviews changed code, logs, telemetry,
   and metrics, then explains why each direction helped or failed.
5. Teacher keeps one or two promising directions and sends follow-up work to
   the same students for the next iteration.  Students are not frozen by a
   status word; even a failed direction should receive a concrete pivot or
   cross-learning instruction unless the human stops the round.

Child workers do not change the evaluator, benchmark selection, or classic
`tools/OpenROAD/src/dpl`.

## Current Baseline Evidence

{metric_table(metrics)}

## Baseline Artifacts To Inspect

Teacher should inspect these paths before assigning or reviewing students when
the metric table alone is not enough.  Prefer `legalize_log`, `metrics_log`,
`legalize_summary`, `check_report`, and `metrics_json`; do not broad-read large
run directories unless the focused files are insufficient.

{baseline_artifact_block(runtime=runtime, case_id=case_id, flow_variant=flow_variant, metrics=metrics)}

## Prior Iteration Context

{prior_context}

## Command Boundary

If any canonical baseline row is missing in the evidence table, do not pretend
the baseline comparison is complete.  The orchestrator normally runs this
preflight before Teacher planning; missing baseline evidence means the round
setup is not ready for promotion.

Do not invent or print concrete shell commands or file paths in Teacher plans.
The orchestrator writes exact private source, build, binary, and evaluation
commands into each student prompt.  Teacher output should focus on algorithmic
direction, code-review reasoning, cross-student learning, and risk controls.
"""


def teacher_prompt(
    *,
    context: str,
    strategies: list[str],
    children: int,
    iteration: int,
) -> str:
    strategy_lines = "\n".join(
        f"- `{name}`: {STRATEGY_BRIEFS.get(name, 'Custom bounded mechanism.')}"
        for name in strategies
    )
    return f"""{context}

# Teacher Planning Task

You are the Teacher Agent for iteration `{iter_name(iteration)}` of this
case-optimization loop.

Your job is not to implement all ideas yourself and not to prescribe a fixed
algorithm.  Your job is to set the target, constraints, useful references, and
review criteria, then let child workers make aggressive implementation choices
inside their private source.

Be synthetic and opportunistic: actively borrow the best pieces from Diamond,
NBLG/negotiation, LEGALM-style guidance, DREAMPlace/Abacus, and prior student
attempts.  Do not force children to stay pure to one paper or one stage when a
hybrid is more likely to win the active case.  Your value is to see across
schools of thought during review, combine mechanisms after seeing real code and
results, and tell each student which ideas to steal, discard, or fuse.

## Child Exploration Lanes

{strategy_lines}

These lanes are seeds for diversity, not restrictions.  Tell students they may
change any part of the evolved implementation when the case evidence supports
it.  Avoid giving concrete implementation recipes in the planning step; the
students should inspect source, design their own approach, compile, run, and
leave reviewable evidence.

## Teacher Review Policy

- Start aggressively.  The first student implementations should be real
  algorithmic alternatives, not timid constant retunes.
- Prefer mechanisms that beat OpenROAD DPL flow strict HPWL on the active case
  without breaking strict legality.  Runtime matters, but during research it is
  secondary to discovering a real quality-improving mechanism.
- Treat runtime as a tradeoff, not a veto.  A slower run with a strong strict
  HPWL gain is more valuable than a fast no-op.  Once a quality mechanism is
  found, later iterations can optimize its data structures and budget.
- Give students freedom to make broad algorithmic changes.  Do not over-specify
  candidate formulas, exact stage order, or local move recipes before seeing
  their code/results.
- Encourage ambitious code evolution along each student's lineage.  A large
  perturbation, global reassignment, or stage replacement is not bad merely
  because it is large; it is bad only if strict metrics, legality, runtime, or
  telemetry show that it is uncontrolled or ineffective.
- When a broad mechanism misses the metric target, prefer feedback such as
  "make the hypothesis sharper", "add a quality gate", "add rollback", "change
  the objective", or "borrow a stronger stage" over feedback that simply tells
  the student to shrink the edit into a safe local tweak.
- If a lineage has two marginal or baseline-equivalent rounds in a row, do not
  ask for another small retune.  Ask for a larger stage interaction change,
  different objective, stronger donor, or decisive ablation.
- Treat AES as smoke only; JPEG and larger cases are real gates.
- If a child improves one metric by using fallback or weakening legality, mark
  that mechanism as invalid and tell the same student how to pivot.
- If a child produces no clean build or no strict metrics, record the failure
  signature and tell the same student how to recover or expand scope.
- Promote one or two directions only when the evidence explains why the case
  benefited, and distinguish "small proof-of-life win" from "promotable case
  optimization".
- If no child beats baseline, tell students to expand the implementation
  surface next iteration instead of repeating a narrow local tweak.
- If children only produce tiny wins, keep the best one as a control, but assign
  at least one student to a more aggressive mechanism that could plausibly
  produce a larger quality jump even with some runtime cost.
- For iteration > 1, preserve each student's useful code lineage, but allow
  students to learn from one another's code when Teacher identifies a stronger
  mechanism.
- Deliberately cross-pollinate.  If one student finds a strong data structure,
  candidate generator, scoring term, threading pattern, or rollback guard,
  assign another student to reuse or challenge it in the next iteration.
- Teacher status labels are review guidance, not scheduler commands.  Do not
  write "stop this student"; write the next algorithmic move for that student.
- Do not output concrete shell commands or private paths.  The orchestrator
  already supplies those to students.

## Output Required

Write a concise exploration charter for {children} child workers:

- child id,
- broad exploration lane,
- useful donor/source-code references,
- case target and hard guardrails,
- what evidence the student must produce,
- what kinds of aggressive pivots are allowed,
- what Teacher will review after code/results arrive.
"""


def teacher_review_prompt(
    *,
    context: str,
    child_rounds: list[ChildRound],
) -> str:
    child_lines = []
    for child in child_rounds:
        child_lines.append(
            f"## {child.student_id}: {child.strategy}\n"
            f"- operation_id: `{child.operation_id}`\n"
            f"- operation_dir: `{child.operation_dir}`\n"
            f"- run_tag: `{child.run_tag}`\n"
            f"- prompt: `{child.prompt_path}`\n"
            f"- last_message: `{child.last_message}`\n"
            f"- usage_summary: `{child.usage_summary}`\n"
            f"- stderr_log: `{child.stderr_log}`\n"
            f"- events_large_do_not_read_by_default: `{child.events_jsonl}`\n"
            f"- student_workspace: `{child.student_workspace}`\n"
            f"- private_dpl_src: `{child.dpl_src}`\n"
            f"- private_binary: `{child.private_binary}`\n"
            f"- implementation_diff: `{child.implementation_diff}`\n"
            f"- source_backup_after_iteration: `{child.source_backup}`\n"
        )

    return f"""{context}

# Teacher Review Task

You are the Teacher Agent reviewing completed child implementations for this
iteration.

You must read each student's artifacts and inspect the code they changed.  Do
not review from metrics alone.
You must also compare the students against one another.  Teacher should use its
knowledge and judgment to identify why one mechanism is stronger, whether two
mechanisms can be combined, and what each student should learn from the other
student's implementation.

Your review should be a synthesis step, not a leaderboard.  Read all students'
code and results, extract reusable mechanisms, and propose cross-student
hybrids when the best path is a combination.  Be willing to tell a student to
borrow another student's implementation detail, broaden scope, or pivot to a
different donor family if that is what the case evidence suggests.

## Student Artifacts To Review

{chr(10).join(child_lines)}

For each student:

1. Read its `codex_last_message.txt`, `codex_usage_summary.json`, stderr hints,
   and any metrics path it reported.
2. Read `implementation_diff` first.  Inspect the private source files only
   where the diff points.  Do not load full `codex_events.jsonl` unless the
   summary is missing; if it is needed, extract only targeted lines.
3. Decide whether the mechanism is algorithmically real, merely a parameter
   tweak, or accidental/fallback behavior.
4. Compare HPWL/runtime/displacement/legality against the OpenROAD baseline
   and current evolve line in the context.
5. Verify whether the student used private variant relink or improperly edited
   root ORFS source.  Treat root-source editing as a protocol violation unless
   the human explicitly requested it.
6. Identify one concrete follow-up direction for that same student.  This can
   be continuing, pivoting, borrowing another student's mechanism, expanding
   the implementation surface, or deleting a harmful mechanism.

Cross-student synthesis:

- Compare the implementation diffs side by side before final judgment.
- Name mechanisms that should be shared between students.
- Name at least one concrete cross-pollination opportunity when any student
  produced a usable mechanism, even if no one beat baseline yet.
- Name mechanisms that should be avoided because they only move metrics by
  accident, fallback, or excessive runtime.
- Do not reject a mechanism just because it perturbs many cells or rewrites a
  full stage.  If it is currently worse, explain what evidence shows the broad
  move is not paying off, then give that student an aggressive next-step such
  as a stronger objective, sharper admission test, rollback, cross-student
  hybrid, or larger architectural pivot.
- Give each student a next step even when the current attempt failed.  A
  status word must not freeze the student.

## Output Required

Write a review table with:

- student id,
- changed mechanism,
- build/eval status,
- metrics path,
- HPWL/runtime/displacement movement,
- code quality risk,
- review status: `continue`, `pivot`, `cross_learn`, `merge_candidate`, or
  `discard_mechanism`,
- what to borrow from the other student if useful,
- next instruction for that same student.

Then write a short Teacher decision:

- best one or two lineages,
- why they are promising,
- what ideas should be cross-pollinated,
- what the next iteration should do,
- what failed mechanisms should be removed or replaced.
"""


def child_prompt(
    *,
    context: str,
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
    compact: bool = False,
    stable_workspace: bool = False,
) -> str:
    brief = STRATEGY_BRIEFS.get(strategy, "Custom bounded mechanism.")
    lineage_path = round_dir / "students" / student_id / "lineage.json"
    paths = student_workspace_paths(
        round_dir=round_dir,
        iteration=iteration,
        student_id=student_id,
        stable_workspace=stable_workspace,
    )
    previous_paths = (
        student_workspace_paths(
            round_dir=round_dir,
            iteration=iteration - 1,
            student_id=student_id,
            stable_workspace=stable_workspace,
        )
        if iteration > 1
        else None
    )
    seed_src = (
        previous_paths.dpl_src
        if previous_paths is not None
        else runtime.orfs_root / "tools" / "OpenROAD" / "src" / "dpl_evolve"
    )
    prompt_context = context
    if compact:
        prompt_context = context

    return f"""{prompt_context}

# Child Worker {child_id}: {student_id} / {strategy}

You are one child worker in a Teacher-led DPL-Evolve optimization loop.
This is iteration `{iter_name(iteration)}`.

## Exploration Seed

{brief}

This seed is not a cage.  You may keep it, combine it with another donor, or
discard it if your code reading and case evidence suggest a stronger route.
The goal is case performance, not fidelity to the seed label.

## Required Startpoint

Before editing, read:

1. The root evolved framework source in `tools/OpenROAD/src/dpl_evolve/src`
   as read-only seed/reference.
2. The LEGALM-guidance source reference under
   `family_variants/legalm_guidance`.
3. The single donor reference most relevant to your hypothesis from the
   Student Startpoints list.
4. The Teacher planning output for this iteration if it exists in the
   operation artifacts.

Your implementation should be a case-focused continuation of that framework,
not a disconnected new legalizer.  The framework already contains a concrete
LEGALM -> row assignment -> Abacus/Negotiation repair starting point, but it is
only a starting point.  In the normal relink path, aggressively modify or
replace `Opendp::runStudentAlgorithm` and any helper stages it needs.

## Student Lineage

- student_id: `{student_id}`
- lineage file: `{lineage_path}`
- student workspace: `{paths.student_workspace}`
- private variant root: `{paths.variant_root}`
- private dpl_evolve source: `{paths.dpl_src}`
- private OpenROAD binary: `{paths.private_binary}`
- implementation diff artifact: `{paths.implementation_diff}`
- post-iteration source backup: `{paths.source_backup}`
- current Teacher plan prompt: `{teacher_prompt_path}`
- current Teacher plan operation: `{teacher_operation_id}`
- current Teacher plan last_message:
  `{runtime.operations_dir / teacher_operation_id / "codex_last_message.txt"}`

If this is not your first iteration, continue your own previous direction.
Read the prior Teacher review and your previous operation artifacts from the
Prior Iteration Context. Keep what was useful, remove what failed, and make the
next algorithmic step on your own code lineage.  If Teacher says your previous
mechanism should be discarded, do not stop; pivot within your private source and
use Teacher's cross-student synthesis to borrow useful ideas from the other
student.

If this is a resumed compact prompt, rely on your existing session memory for
the broad project framing and use the context file path above only when you
need exact baseline evidence or artifact paths.  Do not spend tokens restating
the whole framework; spend them on code, build, evaluation, and a crisp report.

## Scope

Owned implementation surface is the private source tree only:

- any file under `{paths.dpl_src / "src"}` that is needed for the algorithm;
- any local headers/build metadata under `{paths.dpl_src}` needed to compile
  that private implementation.

You are not restricted to the differential/guidance stage.  You may change the
top-level stage selector, Stage A guidance, row/cluster assignment, explicit
donor usage, negotiation/repair, polish, telemetry, data structures, and stage
budgets as long as the command contract remains
`detailed_placement_evolve -> improve_placement_evolve ->
optimize_mirroring_evolve`.

Locked surfaces:

- Do not edit classic `tools/OpenROAD/src/dpl`.
- Do not edit evaluator, scoring, baseline Tcl, or benchmark selection.
- Do not edit root `OpenROAD-flow-scripts/tools/OpenROAD/src/dpl_evolve`
  during normal child work.  Copy it into your private source first.
- Do not claim success through fallback-to-default behavior.
- Do not optimize only for a tiny case; the target case is `{case_id}`.

Workspace policy:

- If the student workspace path ends with `/workspace`, it is your persistent
  active workspace across iterations.
- Do not manually write backup directories.  The orchestrator snapshots your
  private source to `source_backups/<iter>/dpl_evolve` after each iteration.
- Before reading or editing private source paths, run the prepare command
  below so the private source definitely exists.  Reading a non-existent
  private source first wastes the iteration log and can mislead Teacher review.

## Implementation Rules

- Make one coherent algorithmic change, but do not be timid.  If the current
  baseline is strong and a local tweak will not beat it, change a larger stage
  or redesign the stage interaction.
- The top-level stage order is editable.  LEGALM, row assignment/Abacus-style
  compaction, negotiation repair, donor usage, admission tests, and rollback
  are all fair game if the target case metrics justify it.
- Prefer high-performance data structures: contiguous vectors, row/segment
  indexes, per-row work queues, bounded candidate sets, and deterministic
  thread partitioning.  Avoid Python callbacks, full-grid scans in inner loops,
  and full pair enumeration.
- Keep interfaces high-performance.  `EvolveContext` is only for control-plane
  options; do not route per-cell/per-net hot data through JSON files,
  string-keyed maps, cross-process calls, or generic callback dispatch.  Use
  node-id keyed arrays, compact row/segment indexes, bounded candidate arrays,
  and per-thread scratch buffers inside the C++ implementation.
- Large movement or broad restructuring is acceptable.  The standard is not
  "smallest perturbation"; the standard is whether your mechanism beats the
  strict baseline or leaves clear evidence for a better next iteration.
- If your broad mechanism hurts metrics, do not retreat automatically to a
  tiny patch.  Add a better objective, rollback, staging, telemetry, or a
  different donor mechanism so the next version makes the aggressive idea more
  effective.
- This must be a real algorithmic implementation change, not only scalar
  retuning unless the Teacher explicitly requested a narrow retune.
- Keep `detailed_placement_evolve` as the primary evolved placement command.
- You may change any stage inside the evolved implementation when the evidence
  supports it; do not artificially stay inside `DifferentialGuidance.cpp` if
  the bottleneck or quality issue is elsewhere.
- It is acceptable to borrow Diamond, NBLG, LEGALM, DREAMPlace/Abacus, or a
  custom hybrid mechanism, but you must make the borrowed mechanism explicit
  and show why it should beat the measured baseline on this case.
- Strict HPWL improvement matters more than preserving baseline runtime during
  research.  You may spend moderate extra runtime if the code has a plausible
  path to a larger quality gain.  Do not turn the iteration into a no-op just
  to look fast.
- A tiny HPWL win is proof of life, not an endpoint.  If your prior lineage only
  produced a marginal win or baseline-equivalent result, either amplify the
  mechanism, change the objective, add rollback that permits bolder proposals,
  or pivot to a stronger donor/stage interaction.
- Add or preserve telemetry that explains stage behavior.
- Keep legality as a hard gate.
- Compare against the OpenROAD DPL flow baseline when available in the
  context table.
- If a trial is slower or worse, say so and keep the code reviewable.

## Required Commands

Prepare your private source.  This command preserves your private source if it
already exists, so reruns do not accidentally reset your work:

```bash
mkdir -p {shlex.quote(str(paths.variant_root))}
{shlex.quote(str(runtime.agent_root / "scripts" / "create_variant_start.sh"))} \\
  --orfs-root {shlex.quote(str(runtime.orfs_root))} \\
  --variant-root {shlex.quote(str(paths.variant_root))} \\
  --dpl-src {shlex.quote(str(paths.dpl_src))}
mkdir -p {shlex.quote(str(paths.artifact_dir))}
```

Build a private OpenROAD binary by relinking only the private `dpl_evolve`
implementation:

```bash
{shlex.quote(str(runtime.agent_root / "scripts" / "configure_openroad_variant_relink.sh"))} \\
  --variant-root {shlex.quote(str(paths.variant_root))} \\
  --dpl-src {shlex.quote(str(paths.dpl_src))}

{shlex.quote(str(runtime.agent_root / "scripts" / "build_openroad_variant_relink.sh"))} \\
  --variant-root {shlex.quote(str(paths.variant_root))} \\
  --dpl-src {shlex.quote(str(paths.dpl_src))} \\
  --threads {threads}
```

Evaluate this case:

```bash
{shlex.quote(str(AGENT_ROOT / "baseline" / "run_baseline.sh"))} \\
  --line evolve_default \\
  --case {shlex.quote(case_id)} \\
  --flow-variant {shlex.quote(flow_variant)} \\
  --threads {threads} \\
  --openroad-binary {shlex.quote(str(paths.private_binary))} \\
  --run-tag {shlex.quote(run_tag)}
```

After editing and before your final answer, write a reviewable diff artifact:

```bash
diff -ruN \\
  {shlex.quote(str(runtime.orfs_root / "tools" / "OpenROAD" / "src" / "dpl_evolve"))} \\
  {shlex.quote(str(paths.dpl_src))} \\
  > {shlex.quote(str(paths.implementation_diff))} || true
```

## Final Response Required

Report:

- touched files,
- exact mechanism,
- build result,
- metrics path,
- private binary path,
- implementation diff path,
- HPWL/runtime/displacement vs baseline,
- telemetry snippet,
- rollback condition.

Also write enough detail that the Teacher can review your code and decide
whether your lineage should continue into the next iteration.
"""


def write_round_readme(
    *,
    runtime: Any,
    round_dir: Path,
    case_id: str,
    flow_variant: str,
    strategies: list[str],
    metrics: dict[str, MetricSummary | None],
    launch_commands: list[list[str]],
) -> None:
    lines = [
        f"# Codex Optimization Round: {case_id}",
        "",
        f"- flow_variant: `{flow_variant}`",
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
        "## Child Strategies",
        *[f"- `{name}`: {STRATEGY_BRIEFS.get(name, 'Custom bounded mechanism.')}" for name in strategies],
        "",
        "## Launch Commands",
        "```bash",
    ]
    lines.extend(" ".join(shlex.quote(part) for part in command) for command in launch_commands)
    lines.extend(["```", ""])
    round_dir.joinpath("README.md").write_text("\n".join(lines), encoding="utf-8")


def build_codex_exec_command(
    *,
    run_codex: Path,
    operation_id: str,
    prompt_path: Path,
    sandbox: str,
    add_dir: Path,
    model: str | None,
    reasoning_effort: str | None,
    profile: str | None,
    resume_session_id: str | None = None,
    codex_home: Path | None = None,
) -> list[str]:
    cmd = [
        sys.executable,
        str(run_codex),
        "--operation-id",
        operation_id,
        "--prompt-file",
        str(prompt_path),
        "--sandbox",
        sandbox,
        "--add-dir",
        str(add_dir),
    ]
    if codex_home is not None:
        cmd.extend(["--codex-home", str(codex_home)])
    if model:
        cmd.extend(["--model", model])
    if reasoning_effort:
        cmd.extend(["--config", f'model_reasoning_effort="{reasoning_effort}"'])
    if profile:
        cmd.extend(["--profile", profile])
    if resume_session_id:
        cmd.extend(["--resume-session-id", resume_session_id])
    return cmd


def append_lineage(
    *,
    round_dir: Path,
    student_id: str,
    strategy: str,
    iteration: int,
    operation_id: str,
    run_tag: str,
    prompt_path: Path,
) -> None:
    student_dir = round_dir / "students" / student_id
    student_dir.mkdir(parents=True, exist_ok=True)
    lineage_path = student_dir / "lineage.json"
    if lineage_path.exists():
        data = load_json(lineage_path) or {}
    else:
        data = {"student_id": student_id, "strategy": strategy, "iterations": []}
    data.setdefault("iterations", []).append(
        {
            "iteration": iter_name(iteration),
            "strategy": strategy,
            "operation_id": operation_id,
            "run_tag": run_tag,
            "prompt": str(prompt_path),
        }
    )
    lineage_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_commands(
    commands: list[list[str]],
    *,
    max_parallel: int,
    dry_run: bool,
) -> int:
    if dry_run:
        for command in commands:
            print(" ".join(shlex.quote(part) for part in command))
        return 0

    active: list[subprocess.Popen[Any]] = []
    failures = 0
    pending = list(commands)
    while pending or active:
        while pending and len(active) < max_parallel:
            command = pending.pop(0)
            print("[optimize_case] launch:", " ".join(shlex.quote(part) for part in command))
            active.append(subprocess.Popen(command, env=clean_subprocess_env()))
        next_active: list[subprocess.Popen[Any]] = []
        for proc in active:
            rc = proc.poll()
            if rc is None:
                next_active.append(proc)
            elif rc != 0:
                failures += 1
        active = next_active
        if active:
            time.sleep(2)
    return 1 if failures else 0


def backup_child_sources(child_rounds: list[ChildRound]) -> None:
    """Snapshot each child's current source after its iteration.

    The active workspace may be stable across iterations, so the immutable
    review anchor is this source backup plus the per-iteration diff artifact.
    """
    for child in child_rounds:
        if not child.dpl_src.exists():
            print(
                "[optimize_case] warning: cannot backup missing child source "
                f"for {child.student_id}: {child.dpl_src}",
                file=sys.stderr,
            )
            continue
        backup = child.source_backup
        if backup.exists():
            shutil.rmtree(backup)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            child.dpl_src,
            backup,
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
        print(f"[optimize_case] backed up {child.student_id} source: {backup}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Teacher/child Codex entrypoint for optimizing one DPL case."
    )
    parser.add_argument("--case", default="jpeg_nangate45")
    parser.add_argument(
        "--flow-variant",
        default=None,
        help=(
            "ORFS FLOW_VARIANT containing 3_4_place_resized.odb. If omitted, "
            "uses DPL_EVOLVE_FLOW_VARIANT or a placeholder for dry-run prompts."
        ),
    )
    parser.add_argument("--round-id")
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Teacher/child/review loop iterations to generate or launch.",
    )
    parser.add_argument("--children", type=int, default=4)
    parser.add_argument("--strategy", action="append", default=[])
    parser.add_argument("--threads", type=int, default=10)
    parser.add_argument("--max-parallel", type=int, default=2)
    parser.add_argument("--model")
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high", "xhigh"],
        help="Passed to codex exec as model_reasoning_effort.",
    )
    parser.add_argument(
        "--resume-sessions",
        action="store_true",
        help=(
            "For iteration > 1, resume each student's previous Codex exec "
            "session instead of starting a fresh one."
        ),
    )
    parser.add_argument(
        "--compact-after-first",
        action="store_true",
        help=(
            "After iteration 1, write full context to a file and send compact "
            "student follow-up prompts that point to it."
        ),
    )
    parser.add_argument(
        "--stable-student-workspaces",
        action="store_true",
        help=(
            "Keep each student's active source workspace stable across "
            "iterations and snapshot that source after every iteration."
        ),
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        help=(
            "Local CODEX_HOME for launched teacher/student sessions. Defaults "
            "to DPL_EVOLVE_STATE_ROOT/codex_home unless --global-codex-home is set."
        ),
    )
    parser.add_argument(
        "--global-codex-home",
        action="store_true",
        help="Use the user's default ~/.codex instead of a local state-root CODEX_HOME.",
    )
    parser.add_argument("--profile")
    parser.add_argument("--sandbox", default="workspace-write")
    parser.add_argument("--teacher-only", action="store_true")
    parser.add_argument(
        "--skip-baseline-preflight",
        action="store_true",
        help="Do not run/refresh the canonical baseline suite before planning.",
    )
    parser.add_argument(
        "--refresh-baseline",
        action="store_true",
        help="Deprecated alias: the canonical baseline suite is refreshed by default.",
    )
    parser.add_argument(
        "--reuse-baseline-preflight",
        action="store_true",
        help=(
            "Reuse existing OpenROAD/evolve baseline metrics if all "
            "canonical rows already exist."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--launch", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runtime = resolve_runtime_paths(
        anchor_file=__file__,
        agent_root_levels_up=1,
        script_name="optimize_case_with_codex.py",
    )
    codex_home = None
    if not args.global_codex_home:
        codex_home = args.codex_home or (runtime.state_root / "codex_home")
    get_case(args.case)  # Validate early.
    if not args.flow_variant:
        args.flow_variant = os.environ.get(
            "DPL_EVOLVE_FLOW_VARIANT",
            "<FLOW_VARIANT_WITH_3_4_PLACE_RESIZED_ODB>",
        )
    if args.launch and args.flow_variant.startswith("<"):
        raise SystemExit(
            "--launch requires --flow-variant or DPL_EVOLVE_FLOW_VARIANT; "
            "the dry-run placeholder is not runnable."
        )

    iterations = max(1, args.iterations)
    strategies = args.strategy or DEFAULT_STRATEGIES[: max(1, args.children)]
    strategies = strategies[: max(1, args.children)]
    round_id = args.round_id or default_round_id(args.case)
    round_dir = runtime.state_root / "teacher_rounds" / round_id
    round_dir.mkdir(parents=True, exist_ok=True)
    run_codex = runtime.agent_root / "scripts" / "run_codex_exec.py"
    dry_run = args.dry_run or not args.launch

    all_commands: list[list[str]] = []
    manifest_iterations: list[dict[str, Any]] = []
    last_metrics: dict[str, MetricSummary | None] | None = None
    baseline_preflight_commands: list[list[str]] = []

    if not args.skip_baseline_preflight:
        baseline_metrics, baseline_preflight_commands = ensure_baseline_suite(
            runtime=runtime,
            case_id=args.case,
            flow_variant=args.flow_variant,
            threads=args.threads,
            round_id=round_id,
            refresh=args.refresh_baseline or not args.reuse_baseline_preflight,
            dry_run=dry_run,
        )
        last_metrics = baseline_metrics
        all_commands.extend(baseline_preflight_commands)

    for iteration in range(1, iterations + 1):
        iteration_dir = round_dir / iter_name(iteration)
        prompt_dir = iteration_dir / "prompts"
        packet_dir = iteration_dir / "packet"
        prompt_dir.mkdir(parents=True, exist_ok=True)

        packet_path = build_packet(
            agent_root=runtime.agent_root,
            case_id=args.case,
            packet_dir=packet_dir,
        )
        metrics = discover_case_metrics(
            orfs_root=runtime.orfs_root,
            case_id=args.case,
            flow_variant=args.flow_variant,
        )
        if (
            not dry_run
            and not args.skip_baseline_preflight
            and not baseline_suite_complete(metrics)
        ):
            missing = ", ".join(line for line in CANONICAL_LINES if metrics.get(line) is None)
            raise SystemExit(
                "Missing canonical baseline metrics after baseline preflight "
                f"({missing}); refusing to start Teacher planning without the "
                "full comparison anchor."
            )
        last_metrics = metrics
        prior_context = prior_iteration_context(
            runtime=runtime,
            round_dir=round_dir,
            round_id=round_id,
            iteration=iteration,
            strategies=strategies,
        )
        context = common_context(
            case_id=args.case,
            flow_variant=args.flow_variant,
            threads=args.threads,
            runtime=runtime,
            metrics=metrics,
            packet_path=packet_path,
            round_id=round_id,
            iteration=iteration,
            prior_context=prior_context,
        )
        full_context_path = write_iteration_context(
            iteration_dir=iteration_dir,
            context=context,
        )
        child_context = context
        compact_child_prompts = bool(args.compact_after_first and iteration > 1)
        if compact_child_prompts:
            child_context = compact_context(
                case_id=args.case,
                flow_variant=args.flow_variant,
                threads=args.threads,
                runtime=runtime,
                round_id=round_id,
                iteration=iteration,
                full_context_path=full_context_path,
            )

        teacher_op = f"{round_id}_{iter_name(iteration)}_teacher_plan"
        teacher_path = prompt_dir / "teacher_plan.md"
        teacher_path.write_text(
            teacher_prompt(
                context=context,
                strategies=strategies,
                children=len(strategies),
                iteration=iteration,
            ),
            encoding="utf-8",
        )
        teacher_cmd = build_codex_exec_command(
            run_codex=run_codex,
            operation_id=teacher_op,
            prompt_path=teacher_path,
            sandbox=args.sandbox,
            add_dir=runtime.agent_root,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            profile=args.profile,
            codex_home=codex_home,
        )

        child_commands: list[list[str]] = []
        child_rounds: list[ChildRound] = []
        if not args.teacher_only:
            for idx, strategy in enumerate(strategies, start=1):
                student_id = f"student_{idx:02d}"
                operation_id = f"{round_id}_{iter_name(iteration)}_{student_id}_{strategy}"
                run_tag = f"{operation_id}_{args.case}"
                prompt_path = prompt_dir / f"{student_id}_{strategy}.md"
                prompt_path.write_text(
                    child_prompt(
                        context=child_context,
                        runtime=runtime,
                        round_dir=round_dir,
                        teacher_operation_id=teacher_op,
                        teacher_prompt_path=teacher_path,
                        case_id=args.case,
                        flow_variant=args.flow_variant,
                        threads=args.threads,
                        strategy=strategy,
                        child_id=idx,
                        iteration=iteration,
                        student_id=student_id,
                        run_tag=run_tag,
                        compact=compact_child_prompts,
                        stable_workspace=args.stable_student_workspaces,
                    ),
                    encoding="utf-8",
                )
                append_lineage(
                    round_dir=round_dir,
                    student_id=student_id,
                    strategy=strategy,
                    iteration=iteration,
                    operation_id=operation_id,
                    run_tag=run_tag,
                    prompt_path=prompt_path,
                )
                paths = student_workspace_paths(
                    round_dir=round_dir,
                    iteration=iteration,
                    student_id=student_id,
                    stable_workspace=args.stable_student_workspaces,
                )
                child_round = ChildRound(
                    student_id=student_id,
                    strategy=strategy,
                    operation_id=operation_id,
                    run_tag=run_tag,
                    prompt_path=prompt_path,
                    operation_dir=runtime.operations_dir / operation_id,
                    last_message=runtime.operations_dir
                    / operation_id
                    / "codex_last_message.txt",
                    usage_summary=runtime.operations_dir
                    / operation_id
                    / "codex_usage_summary.json",
                    stderr_log=runtime.operations_dir
                    / operation_id
                    / "codex_stderr.log",
                    events_jsonl=runtime.operations_dir
                    / operation_id
                    / "codex_events.jsonl",
                    student_workspace=paths.student_workspace,
                    variant_root=paths.variant_root,
                    dpl_src=paths.dpl_src,
                    private_binary=paths.private_binary,
                    implementation_diff=paths.implementation_diff,
                    source_backup=paths.source_backup,
                )
                child_rounds.append(child_round)
                resume_session_id = None
                if args.resume_sessions and iteration > 1:
                    previous_op = (
                        f"{round_id}_{iter_name(iteration - 1)}_{student_id}_{strategy}"
                    )
                    resume_session_id = operation_thread_id(runtime, previous_op)
                child_commands.append(
                    build_codex_exec_command(
                        run_codex=run_codex,
                        operation_id=operation_id,
                        prompt_path=prompt_path,
                        sandbox=args.sandbox,
                        add_dir=runtime.agent_root,
                        model=args.model,
                        reasoning_effort=args.reasoning_effort,
                        profile=args.profile,
                        resume_session_id=resume_session_id,
                        codex_home=codex_home,
                    )
                )

        review_commands: list[list[str]] = []
        if not args.teacher_only:
            review_op = f"{round_id}_{iter_name(iteration)}_teacher_review"
            review_path = prompt_dir / "teacher_review.md"
            review_path.write_text(
                teacher_review_prompt(context=context, child_rounds=child_rounds),
                encoding="utf-8",
            )
            review_commands.append(
                build_codex_exec_command(
                    run_codex=run_codex,
                    operation_id=review_op,
                    prompt_path=review_path,
                    sandbox=args.sandbox,
                    add_dir=runtime.agent_root,
                    model=args.model,
                    reasoning_effort=args.reasoning_effort,
                    profile=args.profile,
                    codex_home=codex_home,
                )
            )

        iteration_commands = [teacher_cmd, *child_commands, *review_commands]
        all_commands.extend(iteration_commands)
        manifest_iterations.append(
            {
                "iteration": iter_name(iteration),
                "iteration_dir": str(iteration_dir),
                "packet": str(packet_path),
                "full_context": str(full_context_path),
                "compact_child_prompts": compact_child_prompts,
                "teacher_plan_operation": teacher_op,
                "children": [
                    {
                        "student_id": child.student_id,
                        "strategy": child.strategy,
                        "operation_id": child.operation_id,
                        "run_tag": child.run_tag,
                        "prompt": str(child.prompt_path),
                        "student_workspace": str(child.student_workspace),
                        "private_dpl_src": str(child.dpl_src),
                        "source_backup": str(child.source_backup),
                        "implementation_diff": str(child.implementation_diff),
                    }
                    for child in child_rounds
                ],
                "teacher_review_operation": None
                if args.teacher_only
                else f"{round_id}_{iter_name(iteration)}_teacher_review",
                "commands": iteration_commands,
            }
        )

        print(f"[optimize_case] round_dir: {round_dir}")
        print(f"[optimize_case] iteration: {iteration_dir}")
        print(f"[optimize_case] packet: {packet_path}")
        print(f"[optimize_case] prompts: {prompt_dir}")

        if not dry_run:
            rc = run_commands([teacher_cmd], max_parallel=1, dry_run=False)
            if rc:
                return rc
            if child_commands:
                rc = run_commands(
                    child_commands,
                    max_parallel=max(1, args.max_parallel),
                    dry_run=False,
                )
                if rc:
                    print(
                        "[optimize_case] warning: one or more child workers "
                        "failed; continuing to Teacher review so failures can "
                        "be analyzed and turned into next-iteration guidance.",
                        file=sys.stderr,
                    )
                backup_child_sources(child_rounds)
            if review_commands:
                rc = run_commands(review_commands, max_parallel=1, dry_run=False)
                if rc:
                    return rc

    write_round_readme(
        runtime=runtime,
        round_dir=round_dir,
        case_id=args.case,
        flow_variant=args.flow_variant,
        strategies=strategies,
        metrics=last_metrics or {},
        launch_commands=all_commands,
    )
    (round_dir / "manifest.json").write_text(
        json.dumps(
            {
                "round_id": round_id,
                "case": args.case,
                "flow_variant": args.flow_variant,
                "round_dir": str(round_dir),
                "iterations": manifest_iterations,
                "strategies": strategies,
                "model": args.model,
                "reasoning_effort": args.reasoning_effort,
                "resume_sessions": args.resume_sessions,
                "compact_after_first": args.compact_after_first,
                "stable_student_workspaces": args.stable_student_workspaces,
                "codex_home": str(codex_home) if codex_home else None,
                "global_codex_home": args.global_codex_home,
                "baseline_preflight_commands": baseline_preflight_commands,
                "commands": all_commands,
                "dry_run": dry_run,
                "launch": args.launch,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if dry_run:
        return run_commands(
            all_commands,
            max_parallel=max(1, args.max_parallel),
            dry_run=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
