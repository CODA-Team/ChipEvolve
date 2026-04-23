#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


LOWER_IS_BETTER = {
    "hpwl_delta_micron",
    "runtime_seconds",
    "peak_rss_bytes",
}

HIGHER_IS_BETTER = {
    "setup_ws",
    "setup_tns",
    "hold_ws",
    "hold_tns",
}

DEFAULT_WEIGHTS = {
    "hpwl_delta_micron": 0.35,
    "runtime_seconds": 0.20,
    "peak_rss_bytes": 0.15,
    "setup_ws": 0.10,
    "setup_tns": 0.10,
    "hold_ws": 0.05,
    "hold_tns": 0.05,
}

NORMALIZATION_FLOORS = {
    "hpwl_delta_micron": 1.0,
    "runtime_seconds": 1.0,
    "peak_rss_bytes": 1_000_000.0,
    "setup_ws": 0.01,
    "setup_tns": 0.01,
    "hold_ws": 0.01,
    "hold_tns": 0.01,
}


def repo_root() -> Path:
    candidate = Path(__file__).resolve().parents[2]
    if (
        (candidate / "flow").is_dir()
        and (candidate / "tools" / "OpenROAD").is_dir()
        and (candidate / "evolve_agent").is_dir()
    ):
        return candidate
    env_root = os.environ.get("ORFS_ROOT")
    if env_root:
        env_candidate = Path(env_root).resolve()
        if (
            (env_candidate / "flow").is_dir()
            and (env_candidate / "tools" / "OpenROAD").is_dir()
            and (env_candidate / "evolve_agent").is_dir()
        ):
            return env_candidate
    raise SystemExit(
        "run_design_evolve_loop.py must run inside an ORFS workspace with this repo mounted as evolve_agent/. "
        "Re-run from the mounted workspace or set ORFS_ROOT to that workspace."
    )


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def run(
    cmd: list[str],
    *,
    cwd: Path,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        input=input_text,
        text=True,
        capture_output=True,
        check=check,
    )


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ModuleNotFoundError:
        for candidate in (
            "/opt/conda/miniforge3/envs/dreamplace/bin/python",
            "/opt/conda/miniforge3/bin/python",
            "python3",
            "python",
        ):
            resolved = shutil.which(candidate)
            if not resolved or resolved == sys.executable:
                continue
            probe = subprocess.run([resolved, "-c", "import yaml"], capture_output=True)
            if probe.returncode == 0:
                os.execv(resolved, [resolved, __file__, *sys.argv[1:]])
        raise SystemExit(
            "PyYAML is required to read problem/config files for run_design_evolve_loop.py."
        )
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(data) + "\n")


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def collapse_text(text: str, *, max_chars: int = 1200) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 3].rstrip() + "..."


def format_metric_value(key: str, value: float) -> str:
    if key == "peak_rss_bytes":
        return str(int(value))
    return f"{value:.6f}"


def metric_summary_lines(metrics: dict[str, float]) -> list[str]:
    return [
        f"- hpwl_delta_micron: {format_metric_value('hpwl_delta_micron', metrics['hpwl_delta_micron'])}",
        f"- runtime_seconds: {format_metric_value('runtime_seconds', metrics['runtime_seconds'])}",
        f"- peak_rss_bytes: {format_metric_value('peak_rss_bytes', metrics['peak_rss_bytes'])}",
        f"- setup_ws: {format_metric_value('setup_ws', metrics['setup_ws'])}",
        f"- setup_tns: {format_metric_value('setup_tns', metrics['setup_tns'])}",
        f"- hold_ws: {format_metric_value('hold_ws', metrics['hold_ws'])}",
        f"- hold_tns: {format_metric_value('hold_tns', metrics['hold_tns'])}",
    ]


def metric_delta_fraction(
    *, key: str, reference_value: float, candidate_value: float
) -> float:
    return normalize_delta(
        key=key,
        baseline_value=reference_value,
        candidate_value=candidate_value,
        lower_is_better=key in LOWER_IS_BETTER,
    )


def ranked_metric_changes(
    reference_metrics: dict[str, float],
    candidate_metrics: dict[str, float],
) -> tuple[list[str], list[str]]:
    improvements: list[tuple[float, str]] = []
    regressions: list[tuple[float, str]] = []
    for key in DEFAULT_WEIGHTS:
        delta = metric_delta_fraction(
            key=key,
            reference_value=reference_metrics[key],
            candidate_value=candidate_metrics[key],
        )
        summary = (
            f"{key}: {format_metric_value(key, reference_metrics[key])} -> "
            f"{format_metric_value(key, candidate_metrics[key])} ({delta:+.2%})"
        )
        if delta > 0:
            improvements.append((delta, summary))
        elif delta < 0:
            regressions.append((abs(delta), summary))
    improvements.sort(key=lambda item: item[0], reverse=True)
    regressions.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in improvements[:3]], [item[1] for item in regressions[:3]]


def automated_observation(
    *,
    eval_data: dict[str, Any],
    candidate_metrics: dict[str, float] | None,
    reference_metrics: dict[str, float],
    improved: bool,
) -> tuple[str, str]:
    if eval_data.get("status") != "ok":
        return (
            "The evaluator itself failed before producing a clean accepted run.",
            "Keep the next patch smaller and focus on preserving build and evaluator stability.",
        )
    if not legality_ok(eval_data):
        return (
            "The candidate was rejected by the legality/status gate, so the patch changed behavior in a way that broke placement acceptance.",
            "Avoid broad behavioral changes; prefer tighter, flag-gated edits on the same patch surface.",
        )
    if candidate_metrics is None:
        return (
            "No candidate metrics were available to compare against the current best state.",
            "Ensure the next attempt preserves a complete metrics path and produces a valid evaluator summary.",
        )

    improvements, regressions = ranked_metric_changes(reference_metrics, candidate_metrics)
    if improved:
        observation = "Accepted. The weighted score improved over the current best checkpoint."
        if improvements:
            observation += " Strongest gains: " + "; ".join(improvements)
        guidance = (
            "Build on the accepted mechanism, but keep the next patch bounded and preserve the gains above."
        )
        if regressions:
            guidance += " Watch these weaker spots: " + "; ".join(regressions)
        return observation, guidance

    observation = "Rejected. The candidate did not beat the current best composite score."
    if regressions:
        observation += " Main regressions: " + "; ".join(regressions)
    elif improvements:
        observation += " It improved some metrics but not enough to offset the full tradeoff."
    guidance = "Try a different bounded mechanism rather than repeating the same change shape."
    if regressions:
        guidance += " Prioritize avoiding: " + "; ".join(regressions)
    return observation, guidance


def render_memory_excerpt(entries: list[dict[str, Any]], *, limit: int = 4) -> str:
    if not entries:
        return "No prior attempts recorded yet."

    lines = []
    for entry in entries[-limit:]:
        attempt = entry["attempt"]
        outcome = entry["outcome"]
        observation = entry["automated_observation"]
        guidance = entry["next_attempt_guidance"]
        mechanism = entry.get("reported_mechanism") or "unspecified"
        lines.extend(
            [
                f"Attempt {attempt:02d} [{outcome}]",
                f"- mechanism: {mechanism}",
                f"- observation: {observation}",
                f"- next_attempt_guidance: {guidance}",
            ]
        )
        if entry.get("reported_summary"):
            lines.append(f"- codex_summary: {entry['reported_summary']}")
    return "\n".join(lines)


def write_experience_journal(
    *,
    path: Path,
    loop_id: str,
    baseline_metrics: dict[str, float],
    entries: list[dict[str, Any]],
) -> None:
    lines = [
        f"# {loop_id} Experience Journal",
        "",
        "This file is the persistent local memory for the automated design evolve loop.",
        "Each new Codex attempt receives a compact excerpt from this journal.",
        "",
        "## Baseline Metrics",
    ]
    lines.extend(metric_summary_lines(baseline_metrics))
    lines.append("")
    lines.append("## Attempts")

    if not entries:
        lines.extend(["", "No attempts recorded yet."])
    else:
        for entry in entries:
            lines.extend(
                [
                    "",
                    f"### Attempt {entry['attempt']:02d} [{entry['outcome']}]",
                    f"- run_tag: `{entry['run_tag']}`",
                    f"- codex_operation_id: `{entry['codex_operation_id']}`",
                    f"- score: `{entry.get('score_text', 'n/a')}`",
                    f"- mechanism: `{entry.get('reported_mechanism', 'unspecified')}`",
                    f"- observation: {entry['automated_observation']}",
                    f"- next_attempt_guidance: {entry['next_attempt_guidance']}",
                ]
            )
            if entry.get("reported_summary"):
                lines.append(f"- codex_summary: {entry['reported_summary']}")
            if entry.get("metrics"):
                lines.append("- metrics:")
                for metric_line in metric_summary_lines(entry["metrics"]):
                    lines.append(f"  {metric_line}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def infer_prompt_path(problem: dict[str, Any], root: Path) -> Path:
    design = problem["design"]
    platform = problem["platform"]
    return (
        root
        / "evolve_agent"
        / "tasks"
        / "design_evolve"
        / f"{platform}__{design}.md"
    )


def discover_flow_variant(problem: dict[str, Any], root: Path) -> str:
    pattern = (
        root
        / "flow"
        / "results"
        / problem["platform"]
        / problem["design"]
    )
    candidates = sorted(
        pattern.glob("*/3_4_place_resized.odb"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise SystemExit(
            f"No reusable 3_4_place_resized.odb found under {pattern}. "
            "Run evolve_agent/scripts/run_place_batch.sh first."
        )
    return candidates[0].parent.name


def build_metric_vector(eval_data: dict[str, Any]) -> dict[str, float]:
    summary = eval_data.get("summary", {})
    command_run = eval_data.get("command_results", {}).get("run", {})
    return {
        "hpwl_delta_micron": float(summary.get("hpwl_delta_micron") or 0.0),
        "runtime_seconds": float(summary.get("runtime_seconds") or 0.0),
        "peak_rss_bytes": float(command_run.get("peak_rss_bytes") or 0.0),
        "setup_ws": float(summary.get("setup_ws") or 0.0),
        "setup_tns": float(summary.get("setup_tns") or 0.0),
        "hold_ws": float(summary.get("hold_ws") or 0.0),
        "hold_tns": float(summary.get("hold_tns") or 0.0),
    }


def normalize_delta(
    *,
    key: str,
    baseline_value: float,
    candidate_value: float,
    lower_is_better: bool,
) -> float:
    denom = max(abs(baseline_value), NORMALIZATION_FLOORS.get(key, 1e-9))
    if lower_is_better:
        return (baseline_value - candidate_value) / denom
    return (candidate_value - baseline_value) / denom


def composite_score(
    baseline_metrics: dict[str, float],
    candidate_metrics: dict[str, float],
) -> tuple[float, dict[str, float]]:
    components: dict[str, float] = {}
    total = 0.0
    for key, weight in DEFAULT_WEIGHTS.items():
        if key in LOWER_IS_BETTER:
            delta = normalize_delta(
                key=key,
                baseline_value=baseline_metrics[key],
                candidate_value=candidate_metrics[key],
                lower_is_better=True,
            )
        else:
            delta = normalize_delta(
                key=key,
                baseline_value=baseline_metrics[key],
                candidate_value=candidate_metrics[key],
                lower_is_better=False,
            )
        weighted = weight * delta
        components[key] = weighted
        total += weighted
    return total, components


def legality_ok(eval_data: dict[str, Any]) -> bool:
    if eval_data.get("status") != "ok":
        return False
    summary = eval_data.get("summary", {})
    if summary.get("legalization_status") != "ok":
        return False
    placement_violations = str(summary.get("placement_violations") or "").strip()
    return placement_violations in ("", "0", "0.0", "[]", "null")


def run_evaluator(
    *,
    root: Path,
    problem_path: Path,
    config_path: Path,
    flow_variant: str,
    run_tag: str,
    evolve_engine: str,
    threads: int,
    out_path: Path,
) -> dict[str, Any]:
    cmd = [
        "python3",
        "evolve_agent/adapters/science_codeevolve/evaluator.py",
        "--problem",
        str(problem_path),
        "--config",
        str(config_path),
        "--mode",
        "single",
        "--line",
        "evolve_line",
        "--flow-variant",
        flow_variant,
        "--run-tag",
        run_tag,
        "--evolve-engine",
        evolve_engine,
        "--threads",
        str(threads),
        "--out",
        str(out_path),
    ]
    completed = run(cmd, cwd=root, check=False)
    if completed.returncode != 0:
        raise SystemExit(
            "Evaluator invocation failed.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return json.loads(out_path.read_text(encoding="utf-8"))


def create_checkpoint(
    *,
    root: Path,
    checkpoint_id: str,
    title: str,
    summary: str,
    base_checkpoint: str | None,
    what_changed: list[str],
    what_was_run: list[str],
    result_summary: str,
    evidence: list[Path],
) -> None:
    cmd = [
        "python3",
        "evolve_agent/scripts/checkpoint.py",
        "create",
        "--checkpoint-id",
        checkpoint_id,
        "--title",
        title,
        "--summary",
        summary,
        "--result-summary",
        result_summary,
    ]
    if base_checkpoint:
        cmd.extend(["--base-checkpoint", base_checkpoint])
    for item in what_changed:
        cmd.extend(["--what-changed", item])
    for item in what_was_run:
        cmd.extend(["--what-was-run", item])
    for item in evidence:
        cmd.extend(["--evidence", str(item)])
    completed = run(cmd, cwd=root, check=False)
    if completed.returncode != 0:
        raise SystemExit(
            "Checkpoint creation failed.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def restore_checkpoint(root: Path, checkpoint_id: str) -> None:
    cmd = [
        "python3",
        "evolve_agent/scripts/checkpoint.py",
        "restore",
        "--checkpoint-id",
        checkpoint_id,
        "--force",
    ]
    completed = run(cmd, cwd=root, check=False)
    if completed.returncode != 0:
        raise SystemExit(
            "Checkpoint restore failed.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def refresh_packet(root: Path, problem_dir: Path) -> None:
    cmd = [
        "python3",
        "evolve_agent/adapters/science_codeevolve/kb_query.py",
        "--problem_dir",
        str(problem_dir),
        "--out_dir",
        "evolve_agent/knowledge/packets",
    ]
    completed = run(cmd, cwd=root, check=False)
    if completed.returncode != 0:
        raise SystemExit(
            "Packet refresh failed.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def generate_attempt_prompt(
    *,
    base_prompt: str,
    attempt_index: int,
    loop_id: str,
    flow_variant: str,
    run_tag: str,
    problem_path: Path,
    best_score: float,
    best_metrics: dict[str, float],
    memory_excerpt: str,
    experience_journal_path: Path,
    packet_excerpt: str,
) -> str:
    lines = [
        base_prompt.strip(),
        "",
        "---",
        "",
        "Automated loop override:",
        "- The outer Python loop is controlling build, evaluator, and acceptance.",
        "- The outer Python loop has already verified the reusable place snapshot and run the baseline.",
        "- Do not run evaluator yourself.",
        "- Do not create checkpoints yourself.",
        "- Make exactly one bounded patch and then stop.",
        "- Preserve the existing patch surface restrictions.",
        "- Do not inspect flow/Makefile, flow/scripts/*, or design config files unless the task explicitly expands beyond the target plane.",
        "- Do not re-check whether place will rerun; trust the packet and the outer loop for that attempt.",
        "",
        f"Attempt index: {attempt_index}",
        f"Loop id: {loop_id}",
        f"Reusable FLOW_VARIANT: {flow_variant}",
        f"Planned evaluator run tag after your patch: {run_tag}",
        f"Problem file: {problem_path.as_posix()}",
        f"Persistent loop journal: {experience_journal_path.as_posix()}",
        "",
        "The current workspace already reflects the best accepted checkpoint so far.",
        "Use the persistent memory below to avoid repeating rejected ideas blindly.",
        "",
        "Authoritative run packet for this attempt:",
        packet_excerpt,
        "",
        "Persistent loop memory:",
        memory_excerpt,
        "",
        "Current best composite state:",
        f"- best_score: {best_score:.6f}",
    ]
    lines.extend(metric_summary_lines(best_metrics))
    lines.extend(
        [
        "",
        "Optimization target for this loop:",
        "- improve the weighted combination of hpwl delta, runtime, memory, WNS, and TNS",
        "- legality must stay clean",
        "- runtime and memory regressions are not acceptable without offsetting gains",
        "",
        "In your final response, include:",
        "- touched files",
        "- mechanism family",
        "- why this patch should improve the tracked metrics",
        "- rollback condition if the evaluator rejects it",
        "- concise observation summary for future attempts",
        "- concise next-attempt advice if this patch gets rejected",
    ]
    )
    return "\n".join(lines) + "\n"


def codex_operation_dir(root: Path, operation_id: str) -> Path:
    return root / "evolve_agent" / "checkpoints" / "operations" / operation_id


def read_codex_report(root: Path, operation_id: str) -> dict[str, str]:
    op_dir = codex_operation_dir(root, operation_id)
    last_message = collapse_text(read_text_if_exists(op_dir / "codex_last_message.txt"))
    first_sentence = last_message.split(". ")[0].strip() if last_message else ""
    mechanism = collapse_text(first_sentence or last_message, max_chars=240)
    return {
        "summary": last_message,
        "mechanism": mechanism if mechanism else "unspecified",
    }


def run_codex_attempt(
    *,
    root: Path,
    operation_id: str,
    prompt_text: str,
    sandbox: str,
    model: str | None,
    profile: str | None,
) -> dict[str, Any]:
    op_dir = codex_operation_dir(root, operation_id)
    if op_dir.exists():
        raise SystemExit(
            f"Codex operation directory already exists: {op_dir}\n"
            "Use a fresh loop id or remove the old operation before retrying."
        )
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".md",
        prefix=f"{operation_id}_",
        delete=False,
    ) as prompt_fh:
        prompt_fh.write(prompt_text)
        prompt_path = Path(prompt_fh.name)

    try:
        cmd = [
            "python3",
            "evolve_agent/scripts/run_codex_exec.py",
            "--operation-id",
            operation_id,
            "--prompt-file",
            str(prompt_path),
            "--sandbox",
            sandbox,
        ]
        if model:
            cmd.extend(["--model", model])
        if profile:
            cmd.extend(["--profile", profile])

        completed = run(cmd, cwd=root, check=False)
    finally:
        prompt_path.unlink(missing_ok=True)

    usage_path = (
        root
        / "evolve_agent"
        / "checkpoints"
        / "operations"
        / operation_id
        / "codex_usage_summary.json"
    )
    if not usage_path.exists():
        raise SystemExit(
            "Codex invocation did not produce codex_usage_summary.json.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    usage = json.loads(usage_path.read_text(encoding="utf-8"))
    if completed.returncode != 0 or int(usage.get("returncode", 0) or 0) != 0:
        raise SystemExit(
            "Codex invocation failed.\n"
            f"operation_id: {operation_id}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}\n"
            f"usage_summary:\n{json.dumps(usage, indent=2)}"
        )
    usage["stdout"] = completed.stdout
    usage["stderr"] = completed.stderr
    return usage


def write_loop_readme(
    path: Path,
    *,
    loop_id: str,
    problem: dict[str, Any],
    problem_path: Path,
    prompt_path: Path,
    flow_variant: str,
    evolve_engine: str,
    max_attempts: int,
    best_checkpoint: str,
    best_score: float,
    best_metrics: dict[str, float],
    stop_reason: str,
    started_at: str,
    finished_at: str,
    elapsed_seconds: float,
    experience_journal_path: Path,
    experience_log_path: Path,
) -> None:
    lines = [
        f"# {loop_id}",
        "",
        "Automated design evolve loop record.",
        "",
        f"- problem: `{problem['name']}`",
        f"- problem_path: `{problem_path}`",
        f"- prompt_path: `{prompt_path}`",
        f"- design: `{problem['platform']}/{problem['design']}`",
        f"- flow_variant: `{flow_variant}`",
        f"- evolve_engine: `{evolve_engine}`",
        f"- max_attempts: `{max_attempts}`",
        f"- best_checkpoint: `{best_checkpoint}`",
        f"- best_score: `{best_score:.6f}`",
        f"- stop_reason: `{stop_reason}`",
        f"- started_at: `{started_at}`",
        f"- finished_at: `{finished_at}`",
        f"- elapsed_seconds: `{elapsed_seconds:.3f}`",
        f"- experience_journal: `{experience_journal_path}`",
        f"- experience_log: `{experience_log_path}`",
        "",
        "## Best metrics",
    ]
    lines.extend([f"- `{line[2:]}`" if line.startswith("- ") else line for line in metric_summary_lines(best_metrics)])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", required=True, type=Path)
    ap.add_argument("--prompt-file", type=Path)
    ap.add_argument("--loop-id", default=f"design_evolve_{now_stamp()}")
    ap.add_argument("--flow-variant")
    ap.add_argument("--evolve-engine", default="default")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument(
        "--config",
        type=Path,
        default=None,
    )
    ap.add_argument("--max-attempts", type=int, default=3)
    ap.add_argument("--sandbox", default="workspace-write")
    ap.add_argument("--model")
    ap.add_argument("--profile")
    ap.add_argument("--continue-after-improvement", action="store_true")
    ap.add_argument("--min-score-delta", type=float, default=1e-6)
    args = ap.parse_args()
    if args.config is None:
        args.config = repo_root() / "evolve_agent" / "configs" / "codex_design_specific.yaml"

    root = repo_root()
    loop_started_at = dt.datetime.now().isoformat()
    loop_start_time = time.perf_counter()
    problem_path = args.problem.resolve()
    problem_dir = problem_path.parent
    problem = load_yaml(problem_path)
    prompt_path = args.prompt_file.resolve() if args.prompt_file else infer_prompt_path(problem, root)
    base_prompt = prompt_path.read_text(encoding="utf-8")
    flow_variant = args.flow_variant or discover_flow_variant(problem, root)

    loop_dir = root / "evolve_agent" / "checkpoints" / "operations" / args.loop_id
    if loop_dir.exists():
        raise SystemExit(
            f"Loop directory already exists: {loop_dir}\n"
            "Use a fresh --loop-id to avoid mixing attempts from different runs."
        )
    loop_dir.mkdir(parents=True, exist_ok=False)
    attempts_path = loop_dir / "attempts.jsonl"
    experience_log_path = loop_dir / "experience_log.jsonl"
    experience_journal_path = loop_dir / "experience_journal.md"
    state_path = loop_dir / "loop_state.json"
    readme_path = loop_dir / "README.md"
    experience_entries: list[dict[str, Any]] = []

    refresh_packet(root, problem_dir)
    packet_path = root / "evolve_agent" / "knowledge" / "packets" / "current_run_packet.md"
    packet_excerpt = packet_path.read_text(encoding="utf-8").strip()

    baseline_run_tag = f"{args.loop_id}_baseline"
    baseline_eval_path = loop_dir / "baseline_eval.json"
    baseline_eval = run_evaluator(
        root=root,
        problem_path=problem_path,
        config_path=args.config,
        flow_variant=flow_variant,
        run_tag=baseline_run_tag,
        evolve_engine=args.evolve_engine,
        threads=args.threads,
        out_path=baseline_eval_path,
    )
    if not legality_ok(baseline_eval):
        raise SystemExit("Initial baseline evaluator run did not pass legality/status gates.")

    baseline_metrics = build_metric_vector(baseline_eval)
    best_metrics = dict(baseline_metrics)
    best_score = 0.0
    best_checkpoint = f"{args.loop_id}__baseline"
    write_experience_journal(
        path=experience_journal_path,
        loop_id=args.loop_id,
        baseline_metrics=baseline_metrics,
        entries=experience_entries,
    )

    create_checkpoint(
        root=root,
        checkpoint_id=best_checkpoint,
        title=f"{args.loop_id} baseline anchor",
        summary="Baseline checkpoint before automated Codex evolve loop.",
        base_checkpoint=None,
        what_changed=["captured starting workspace state"],
        what_was_run=[
            f"baseline evaluator run_tag={baseline_run_tag}",
            f"flow_variant={flow_variant}",
        ],
        result_summary="baseline anchor captured",
        evidence=[baseline_eval_path],
    )

    stop_reason = "max_attempts_reached"

    for attempt_index in range(1, args.max_attempts + 1):
        restore_checkpoint(root, best_checkpoint)
        reference_metrics = dict(best_metrics)

        attempt_run_tag = f"{args.loop_id}_attempt_{attempt_index:02d}"
        codex_op_id = f"{args.loop_id}__codex_attempt_{attempt_index:02d}"
        eval_path = loop_dir / f"attempt_{attempt_index:02d}_eval.json"
        memory_excerpt = render_memory_excerpt(experience_entries)
        prompt_text = generate_attempt_prompt(
            base_prompt=base_prompt,
            attempt_index=attempt_index,
            loop_id=args.loop_id,
            flow_variant=flow_variant,
            run_tag=attempt_run_tag,
            problem_path=problem_path.relative_to(root),
            best_score=best_score,
            best_metrics=best_metrics,
            memory_excerpt=memory_excerpt,
            experience_journal_path=experience_journal_path.relative_to(root),
            packet_excerpt=packet_excerpt,
        )
        codex_usage = run_codex_attempt(
            root=root,
            operation_id=codex_op_id,
            prompt_text=prompt_text,
            sandbox=args.sandbox,
            model=args.model,
            profile=args.profile,
        )
        codex_report = read_codex_report(root, codex_op_id)

        eval_data = run_evaluator(
            root=root,
            problem_path=problem_path,
            config_path=args.config,
            flow_variant=flow_variant,
            run_tag=attempt_run_tag,
            evolve_engine=args.evolve_engine,
            threads=args.threads,
            out_path=eval_path,
        )

        attempt_record: dict[str, Any] = {
            "attempt": attempt_index,
            "codex_operation_id": codex_op_id,
            "run_tag": attempt_run_tag,
            "eval_json": str(eval_path),
            "eval_status": eval_data.get("status"),
            "codex_usage_json": str(
                codex_operation_dir(root, codex_op_id) / "codex_usage_summary.json"
            ),
            "token_usage": codex_usage.get("usage", {}),
            "codex_elapsed_seconds": codex_usage.get("elapsed_seconds"),
            "reported_summary": codex_report["summary"],
            "reported_mechanism": codex_report["mechanism"],
        }

        attempt_metrics: dict[str, float] | None = None
        improved = False
        if legality_ok(eval_data):
            attempt_metrics = build_metric_vector(eval_data)
            score, components = composite_score(baseline_metrics, attempt_metrics)
            improved = score > (best_score + args.min_score_delta)
            attempt_record["score"] = score
            attempt_record["score_components"] = components
            attempt_record["metrics"] = attempt_metrics
            attempt_record["improved"] = improved

            if improved:
                best_score = score
                best_metrics = dict(attempt_metrics)
                accepted_checkpoint = f"{args.loop_id}__best_attempt_{attempt_index:02d}"
                create_checkpoint(
                    root=root,
                    checkpoint_id=accepted_checkpoint,
                    title=f"{args.loop_id} accepted attempt {attempt_index:02d}",
                    summary="Accepted candidate from automated Codex evolve loop.",
                    base_checkpoint=best_checkpoint,
                    what_changed=[
                        "bounded legalizer patch accepted",
                        f"codex operation: {codex_op_id}",
                    ],
                    what_was_run=[
                        f"codex attempt {attempt_index:02d}",
                        f"evaluator run_tag={attempt_run_tag}",
                    ],
                    result_summary=f"accepted with score {score:.6f}",
                    evidence=[
                        eval_path,
                        codex_operation_dir(root, codex_op_id) / "codex_usage_summary.json",
                    ],
                )
                best_checkpoint = accepted_checkpoint
            else:
                restore_checkpoint(root, best_checkpoint)
        else:
            attempt_record["improved"] = False
            restore_checkpoint(root, best_checkpoint)

        observation, next_guidance = automated_observation(
            eval_data=eval_data,
            candidate_metrics=attempt_metrics,
            reference_metrics=reference_metrics,
            improved=improved,
        )
        outcome = "accepted" if improved else "rejected"
        attempt_record["outcome"] = outcome
        attempt_record["automated_observation"] = observation
        attempt_record["next_attempt_guidance"] = next_guidance
        memory_entry = {
            "attempt": attempt_index,
            "outcome": outcome,
            "run_tag": attempt_run_tag,
            "codex_operation_id": codex_op_id,
            "score_text": (
                f"{attempt_record['score']:.6f}"
                if "score" in attempt_record
                else "n/a"
            ),
            "reported_summary": codex_report["summary"],
            "reported_mechanism": codex_report["mechanism"],
            "automated_observation": observation,
            "next_attempt_guidance": next_guidance,
            "metrics": attempt_metrics,
        }
        experience_entries.append(memory_entry)
        append_jsonl(experience_log_path, memory_entry)
        write_experience_journal(
            path=experience_journal_path,
            loop_id=args.loop_id,
            baseline_metrics=baseline_metrics,
            entries=experience_entries,
        )

        append_jsonl(attempts_path, attempt_record)

        if improved and not args.continue_after_improvement:
            stop_reason = "improvement_found"
            break

    loop_finished_at = dt.datetime.now().isoformat()
    loop_elapsed_seconds = time.perf_counter() - loop_start_time

    loop_state = {
        "loop_id": args.loop_id,
        "problem": problem["name"],
        "problem_path": str(problem_path),
        "prompt_path": str(prompt_path),
        "flow_variant": flow_variant,
        "evolve_engine": args.evolve_engine,
        "max_attempts": args.max_attempts,
        "best_checkpoint": best_checkpoint,
        "best_score": best_score,
        "best_metrics": best_metrics,
        "stop_reason": stop_reason,
        "started_at": loop_started_at,
        "finished_at": loop_finished_at,
        "elapsed_seconds": round(loop_elapsed_seconds, 3),
        "baseline_eval": str(baseline_eval_path),
        "attempts_jsonl": str(attempts_path),
        "experience_log": str(experience_log_path),
        "experience_journal": str(experience_journal_path),
    }
    write_json(state_path, loop_state)
    write_loop_readme(
        readme_path,
        loop_id=args.loop_id,
        problem=problem,
        problem_path=problem_path,
        prompt_path=prompt_path,
        flow_variant=flow_variant,
        evolve_engine=args.evolve_engine,
        max_attempts=args.max_attempts,
        best_checkpoint=best_checkpoint,
        best_score=best_score,
        best_metrics=best_metrics,
        stop_reason=stop_reason,
        started_at=loop_started_at,
        finished_at=loop_finished_at,
        elapsed_seconds=loop_elapsed_seconds,
        experience_journal_path=experience_journal_path,
        experience_log_path=experience_log_path,
    )

    print(json.dumps(loop_state, indent=2))


if __name__ == "__main__":
    main()
