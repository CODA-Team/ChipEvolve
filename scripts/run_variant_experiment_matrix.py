#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

AGENT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = AGENT_ROOT / "scripts"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from learning.log2knowledge import process_run_record
from learning.report_token_roi import write_token_roi_reports
from memory.run_db import append_jsonl as append_run_record
from memory.run_db import run_db_path
from runtime_paths import resolve_runtime_paths
from run_design_evolve_loop import build_metric_vector, composite_score, legality_ok


DEFAULT_CASES = [
    "aes_nangate45",
    "ibex_nangate45",
    "jpeg_nangate45",
    "ariane133_nangate45",
    "bp_quad_nangate45",
]


@dataclass(frozen=True)
class VariantSpec:
    name: str
    family: str
    touched_symbol: str
    summary: str
    apply: Callable[[Path], list[str]]


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def replace_once(path: Path, old: str, new: str) -> None:
    text = read_text(path)
    if old not in text:
        raise RuntimeError(f"Pattern not found in {path}: {old!r}")
    write_text(path, text.replace(old, new, 1))


def replace_all(path: Path, old: str, new: str) -> None:
    text = read_text(path)
    if old not in text:
        raise RuntimeError(f"Pattern not found in {path}: {old!r}")
    write_text(path, text.replace(old, new))


def variant_file(src: Path, relative: str) -> Path:
    path = src / "src" / relative
    if not path.is_file():
        raise RuntimeError(f"Missing expected dpl_evolve file: {path}")
    return path


def mutate_greedy1(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizer.cpp")
    replace_once(path, "  // greedyImprove(1);\n", "  greedyImprove(1);\n")
    return [str(path)]


def mutate_greedy2(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizer.cpp")
    replace_once(path, "  // greedyImprove(1);\n", "  greedyImprove(2);\n")
    return [str(path)]


def mutate_search_narrow_runtime(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizer.h")
    replace_once(path, "constexpr int kHorizWindow = 20;", "constexpr int kHorizWindow = 16;")
    replace_once(path, "constexpr int kAdjWindow = 5;", "constexpr int kAdjWindow = 4;")
    return [str(path)]


def mutate_search_wide_escape(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizer.h")
    replace_once(path, "constexpr int kHorizWindow = 20;", "constexpr int kHorizWindow = 24;")
    replace_once(path, "constexpr int kAdjWindow = 5;", "constexpr int kAdjWindow = 6;")
    return [str(path)]


def mutate_history_strong(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizerPass.cpp")
    replace_all(path, "cost += g.hist_cost * penalty;", "cost += 1.15 * g.hist_cost * penalty;")
    return [str(path)]


def mutate_history_soft(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizerPass.cpp")
    replace_all(path, "cost += g.hist_cost * penalty;", "cost += 0.85 * g.hist_cost * penalty;")
    return [str(path)]


def mutate_drc_late_ramp(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizerPass.cpp")
    replace_once(
        path,
        "const double kDrcPenalty = 1e3 * (1.0 + iter);",
        "const double kDrcPenalty = 5e2 * (1.0 + 2.0 * iter);",
    )
    return [str(path)]


def mutate_disp_soft(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizer.h")
    replace_once(path, "constexpr double kMfDefault = 1.5;", "constexpr double kMfDefault = 1.2;")
    replace_once(path, "constexpr int kThDefault = 30;", "constexpr int kThDefault = 40;")
    return [str(path)]


def mutate_disp_strong(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizer.h")
    replace_once(path, "constexpr double kMfDefault = 1.5;", "constexpr double kMfDefault = 2.0;")
    replace_once(path, "constexpr int kThDefault = 30;", "constexpr int kThDefault = 24;")
    return [str(path)]


VARIANTS: dict[str, VariantSpec] = {
    "greedy1": VariantSpec(
        name="greedy1",
        family="localized_postopt",
        touched_symbol="NegotiationLegalizer::legalize",
        summary="Enable one greedyImprove pass after the main negotiation legalizer.",
        apply=mutate_greedy1,
    ),
    "greedy2": VariantSpec(
        name="greedy2",
        family="localized_postopt",
        touched_symbol="NegotiationLegalizer::legalize",
        summary="Enable two greedyImprove passes after the main negotiation legalizer.",
        apply=mutate_greedy2,
    ),
    "search_narrow_runtime": VariantSpec(
        name="search_narrow_runtime",
        family="search_window_tuning",
        touched_symbol="NegotiationLegalizer::findBestLocation",
        summary="Shrink horizontal and adjacent row windows to test runtime-sensitive cases.",
        apply=mutate_search_narrow_runtime,
    ),
    "search_wide_escape": VariantSpec(
        name="search_wide_escape",
        family="search_window_tuning",
        touched_symbol="NegotiationLegalizer::findBestLocation",
        summary="Widen horizontal and adjacent row windows to test stuck-cell escape.",
        apply=mutate_search_wide_escape,
    ),
    "history_strong": VariantSpec(
        name="history_strong",
        family="objective_cost_shaping",
        touched_symbol="NegotiationLegalizer::negotiationCost",
        summary="Increase historical congestion pressure in the negotiation objective.",
        apply=mutate_history_strong,
    ),
    "history_soft": VariantSpec(
        name="history_soft",
        family="objective_cost_shaping",
        touched_symbol="NegotiationLegalizer::negotiationCost",
        summary="Soften historical congestion pressure in the negotiation objective.",
        apply=mutate_history_soft,
    ),
    "drc_late_ramp": VariantSpec(
        name="drc_late_ramp",
        family="candidate_generation",
        touched_symbol="NegotiationLegalizer::findBestLocation",
        summary="Reduce early DRC penalty but ramp it more strongly over iterations.",
        apply=mutate_drc_late_ramp,
    ),
    "disp_soft": VariantSpec(
        name="disp_soft",
        family="objective_cost_shaping",
        touched_symbol="targetCost",
        summary="Relax max-displacement pressure to test HPWL headroom.",
        apply=mutate_disp_soft,
    ),
    "disp_strong": VariantSpec(
        name="disp_strong",
        family="objective_cost_shaping",
        touched_symbol="targetCost",
        summary="Increase max-displacement pressure to test conservative legalization.",
        apply=mutate_disp_strong,
    ),
}


def parse_problem(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith(" ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip("'\"")
        if key in {"name", "design", "platform"}:
            values[key] = value
    for key in ("name", "design", "platform"):
        if key not in values:
            raise RuntimeError(f"Problem file missing top-level {key}: {path}")
    return values


def find_python_with_yaml() -> str:
    candidates = []
    env_value = os.environ.get("DPL_EVOLVE_PYTHON_CANDIDATES", "")
    candidates.extend([item for item in env_value.split(os.pathsep) if item])
    candidates.extend(
        [
            sys.executable,
            "/opt/conda/miniforge3/envs/dreamplace/bin/python",
            "python3",
            "python",
        ]
    )
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        resolved = shutil.which(candidate) if "/" not in candidate else candidate
        if not resolved or not Path(resolved).exists():
            continue
        probe = subprocess.run(
            [resolved, "-c", "import yaml"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if probe.returncode == 0:
            return str(Path(resolved).resolve())
    raise RuntimeError("Could not find a Python interpreter with PyYAML for evaluator.py")


def run_command(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    elapsed = time.time() - started
    log_path.write_text(
        "$ " + " ".join(cmd) + "\n\n" + proc.stdout + f"\n[elapsed_seconds] {elapsed:.3f}\n",
        encoding="utf-8",
    )
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout)
    return proc


def ensure_symlink(path: Path, target: Path) -> None:
    if path.is_symlink():
        if path.resolve() == target.resolve():
            return
        path.unlink()
    if path.exists():
        return
    path.symlink_to(target)


def ensure_registered_common_core(orfs_root: Path, state_root: Path) -> Path:
    openroad_src = orfs_root / "tools" / "OpenROAD"
    head = subprocess.check_output(
        ["git", "-C", str(openroad_src), "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()
    core_root = state_root / "openroad_core" / head
    core_root.mkdir(parents=True, exist_ok=True)

    core_build = orfs_root / "tools" / "OpenROAD" / "build"
    core_install = orfs_root / "tools" / "install" / "OpenROAD"
    if not (core_build / "compile_commands.json").is_file():
        raise RuntimeError(f"Missing existing OpenROAD build compile_commands.json: {core_build}")
    if not (core_install / "bin" / "openroad").is_file():
        raise RuntimeError(f"Missing existing OpenROAD binary: {core_install / 'bin' / 'openroad'}")

    ensure_symlink(core_root / "build", core_build)
    install_parent = core_root / "install"
    install_parent.mkdir(exist_ok=True)
    ensure_symlink(install_parent / "OpenROAD", core_install)
    (core_root / "core_env.sh").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "# Registered by run_variant_experiment_matrix.py from an existing ORFS build.",
                f"export OPENROAD_CORE_ROOT={core_root}",
                f"export OPENROAD_BUILD_DIR={core_root / 'build'}",
                f"export OPENROAD_INSTALL_ROOT={core_root / 'install' / 'OpenROAD'}",
                f"export OPENROAD_BINARY={core_root / 'install' / 'OpenROAD' / 'bin' / 'openroad'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (core_root / "core_env.sh").chmod(0o755)
    return core_root


def discover_flow_variant(orfs_root: Path, problem: dict[str, str]) -> str:
    root = orfs_root / "flow" / "results" / problem["platform"] / problem["design"]
    candidates = sorted(root.glob("*/3_4_place_resized.odb"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError(f"No reusable 3_4_place_resized.odb under {root}")
    preferred = root / "place_batch_20260421_220319" / "3_4_place_resized.odb"
    if preferred.exists():
        return preferred.parent.name
    base = root / "base" / "3_4_place_resized.odb"
    if base.exists():
        return base.parent.name
    return candidates[0].parent.name


def copy_variant_source(base_src: Path, variant_src: Path) -> None:
    if variant_src.exists():
        shutil.rmtree(variant_src)
    shutil.copytree(base_src, variant_src, symlinks=True)


def configure_and_build_variant(
    *,
    spec: VariantSpec,
    exp_root: Path,
    agent_root: Path,
    orfs_root: Path,
    state_root: Path,
    core_root: Path,
    threads: int,
    env: dict[str, str],
) -> dict[str, Any]:
    variant_root = exp_root / "variants" / spec.name
    variant_src = variant_root / "src" / "dpl_evolve"
    base_src = orfs_root / "tools" / "OpenROAD" / "src" / "dpl_evolve"
    copy_variant_source(base_src, variant_src)
    touched_files = spec.apply(variant_src)

    manifest = {
        "variant": spec.name,
        "family": spec.family,
        "touched_symbol": spec.touched_symbol,
        "summary": spec.summary,
        "touched_files": touched_files,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    (variant_root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    configure_log = exp_root / "logs" / "build" / f"{spec.name}__configure.log"
    build_log = exp_root / "logs" / "build" / f"{spec.name}__build.log"
    configure_cmd = [
        str(agent_root / "scripts" / "configure_openroad_variant_relink.sh"),
        "--variant-root",
        str(variant_root),
        "--dpl-src",
        str(variant_src),
        "--core-root",
        str(core_root),
    ]
    run_command(configure_cmd, cwd=agent_root, env=env, log_path=configure_log)
    build_cmd = [
        str(agent_root / "scripts" / "build_openroad_variant_relink.sh"),
        "--variant-root",
        str(variant_root),
        "--dpl-src",
        str(variant_src),
        "--core-root",
        str(core_root),
        "--threads",
        str(threads),
    ]
    run_command(build_cmd, cwd=agent_root, env=env, log_path=build_log)

    binary = variant_root / "install" / "OpenROAD" / "bin" / "openroad"
    if not binary.is_file():
        raise RuntimeError(f"Variant build completed but binary is missing: {binary}")
    return {
        "variant": spec.name,
        "variant_root": str(variant_root),
        "variant_src": str(variant_src),
        "openroad_binary": str(binary),
        "manifest": manifest,
        "configure_log": str(configure_log),
        "build_log": str(build_log),
    }


def run_evaluator(
    *,
    python_bin: str,
    agent_root: Path,
    orfs_root: Path,
    env: dict[str, str],
    problem_path: Path,
    flow_variant: str,
    run_tag: str,
    openroad_binary: Path,
    threads: int,
    eval_timeout_sec: int,
    out_path: Path,
    log_path: Path,
) -> dict[str, Any]:
    cmd = [
        python_bin,
        str(agent_root / "adapters" / "science_codeevolve" / "evaluator.py"),
        "--problem",
        str(problem_path),
        "--config",
        str(agent_root / "configs" / "codex_design_specific.yaml"),
        "--mode",
        "single",
        "--line",
        "evolve_line",
        "--flow-variant",
        flow_variant,
        "--run-tag",
        run_tag,
        "--threads",
        str(threads),
        "--evolve-engine",
        "negotiation",
        "--skip-build",
        "--eval-timeout-sec",
        str(eval_timeout_sec),
        "--openroad-binary",
        str(openroad_binary),
        "--out",
        str(out_path),
    ]
    run_command(cmd, cwd=orfs_root, env=env, log_path=log_path, check=False)
    if not out_path.is_file():
        return {
            "status": "evaluator_failed",
            "summary": {},
            "error": f"evaluator did not create {out_path}",
        }
    try:
        return json.loads(out_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "evaluator_failed", "summary": {}, "error": str(exc)}


def failure_signature(eval_data: dict[str, Any], *, improved: bool | None) -> str | None:
    if eval_data.get("status") != "ok":
        run_result = eval_data.get("command_results", {}).get("run", {}) or {}
        stdout_tail = str(run_result.get("stdout_tail") or "")
        stderr_tail = str(run_result.get("stderr_tail") or "")
        if run_result.get("timed_out"):
            return "eval_timeout"
        if "DPL-0033" in stdout_tail or "check placement" in stdout_tail.lower():
            return "placement_check_failed"
        if "Violations remain" in stdout_tail:
            return "legalizer_did_not_converge"
        if "Terminated" in stderr_tail:
            return "run_terminated"
        return str(eval_data.get("status") or eval_data.get("error") or "evaluator_failed")
    if not legality_ok(eval_data):
        return "legality_or_placement_gate_failed"
    if improved is False:
        return "legal_but_no_score_improvement"
    return None


def write_markdown_summary(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"# Variant Experiment Matrix: {summary['experiment_id']}",
        "",
        "This run applies deterministic dpl_evolve-only mutations to private source",
        "copies, relinks private OpenROAD binaries, evaluates them from fixed",
        "placement snapshots, and writes RunDB/KnowledgeDB evidence.",
    ]
    parallelism = summary.get("parallelism") or {}
    if parallelism:
        lines.extend(
            [
                "",
                "## Parallelism",
                f"- Build jobs: `{parallelism.get('build_jobs')}`",
                f"- Build threads per job: `{parallelism.get('build_threads')}`",
                f"- Evaluator jobs: `{parallelism.get('eval_jobs')}`",
                f"- OpenROAD threads per evaluator: `{parallelism.get('eval_threads')}`",
                f"- Evaluation timeout: `{parallelism.get('eval_timeout_sec')}s`",
                "",
                "## Cases",
            ]
        )
    for case in summary["cases"]:
        lines.append(f"- `{case['case']}`: flow_variant `{case['flow_variant']}`")
    lines.extend(["", "## Variants"])
    for variant in summary["variants"]:
        lines.append(
            f"- `{variant['variant']}`: {variant['summary']} "
            f"({variant['family']}, `{variant['touched_symbol']}`)"
        )
    lines.extend(["", "## Results", ""])
    lines.append("| Case | Variant | Legal | Score | HPWL delta | Runtime | Failure |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | --- |")
    for item in summary["results"]:
        metrics = item.get("metrics") or {}
        legal = "yes" if item.get("legal") else "no"
        score = item.get("score")
        score_text = "" if score is None else f"{float(score):.6f}"
        hpwl = metrics.get("hpwl_delta_micron")
        hpwl_text = "" if hpwl is None else f"{float(hpwl):.3f}"
        runtime = metrics.get("runtime_seconds")
        runtime_text = "" if runtime is None else f"{float(runtime):.3f}"
        failure = item.get("failure_signature") or ""
        lines.append(
            f"| `{item['case']}` | `{item['variant']}` | {legal} | {score_text} | "
            f"{hpwl_text} | {runtime_text} | {failure} |"
        )
    lines.extend(
        [
            "",
            "## Artifacts",
            f"- Summary JSON: `{summary['summary_json']}`",
            f"- RunDB: `{summary['run_db']}`",
            f"- Token ROI: `{summary.get('token_roi_md', '')}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic dpl_evolve variant experiments and update evidence databases."
    )
    parser.add_argument("--experiment-id", default=f"variant_matrix_{now_stamp()}")
    parser.add_argument("--cases", nargs="+", default=DEFAULT_CASES)
    parser.add_argument("--variants", nargs="+", default=list(VARIANTS.keys()))
    parser.add_argument("--build-jobs", type=int, default=4)
    parser.add_argument("--eval-jobs", type=int, default=8)
    parser.add_argument("--build-threads", type=int, default=10)
    parser.add_argument("--eval-threads", type=int, default=10)
    parser.add_argument("--eval-timeout-sec", type=int, default=900)
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-variants", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.list_variants:
        for name, spec in sorted(VARIANTS.items()):
            print(f"{name}\t{spec.family}\t{spec.touched_symbol}\t{spec.summary}")
        return

    unknown = [name for name in args.variants if name not in VARIANTS]
    if unknown:
        raise SystemExit(f"Unknown variant(s): {', '.join(unknown)}")

    runtime = resolve_runtime_paths(
        anchor_file=__file__,
        agent_root_levels_up=1,
        script_name="run_variant_experiment_matrix.py",
    )
    agent_root = runtime.agent_root
    orfs_root = runtime.orfs_root
    state_root = runtime.state_root
    exp_root = state_root / "experiments" / args.experiment_id
    exp_root.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DPL_EVOLVE_AGENT_ROOT"] = str(agent_root)
    env["ORFS_ROOT"] = str(orfs_root)
    env["DPL_EVOLVE_STATE_ROOT"] = str(state_root)
    env["DPL_EVOLVE_SKIP_ENV_SH"] = "1"

    python_bin = find_python_with_yaml()
    core_root = ensure_registered_common_core(orfs_root, state_root)
    core_binary = core_root / "install" / "OpenROAD" / "bin" / "openroad"

    problems: dict[str, dict[str, Any]] = {}
    for case in args.cases:
        problem_path = agent_root / "problems" / case / "problem.yaml"
        if not problem_path.is_file():
            raise SystemExit(f"Missing problem file for case {case}: {problem_path}")
        problem = parse_problem(problem_path)
        flow_variant = discover_flow_variant(orfs_root, problem)
        problems[case] = {
            "case": case,
            "problem": problem,
            "problem_path": problem_path,
            "flow_variant": flow_variant,
        }

    selected_specs = [VARIANTS[name] for name in args.variants]
    planned = {
        "experiment_id": args.experiment_id,
        "agent_root": str(agent_root),
        "orfs_root": str(orfs_root),
        "state_root": str(state_root),
        "core_root": str(core_root),
        "python_bin": python_bin,
        "parallelism": {
            "build_jobs": args.build_jobs,
            "build_threads": args.build_threads,
            "eval_jobs": args.eval_jobs,
            "eval_threads": args.eval_threads,
            "eval_timeout_sec": args.eval_timeout_sec,
        },
        "cases": [
            {"case": case, "flow_variant": item["flow_variant"], **item["problem"]}
            for case, item in problems.items()
        ],
        "variants": [
            {
                "variant": spec.name,
                "family": spec.family,
                "touched_symbol": spec.touched_symbol,
                "summary": spec.summary,
            }
            for spec in selected_specs
        ],
        "dry_run": bool(args.dry_run),
    }
    (exp_root / "plan.json").write_text(json.dumps(planned, indent=2) + "\n", encoding="utf-8")
    if args.dry_run:
        print(json.dumps(planned, indent=2))
        return

    baseline_metrics: dict[str, dict[str, float]] = {}
    baseline_eval_by_case: dict[str, dict[str, Any]] = {}
    if not args.skip_baseline:
        def eval_baseline_one(case: str, item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            out_path = exp_root / "eval" / "baseline" / f"{case}.json"
            log_path = exp_root / "logs" / "eval" / f"baseline__{case}.log"
            run_tag = f"{args.experiment_id}__baseline__{case}"
            data = run_evaluator(
                python_bin=python_bin,
                agent_root=agent_root,
                orfs_root=orfs_root,
                env=env,
                problem_path=item["problem_path"],
                flow_variant=item["flow_variant"],
                run_tag=run_tag,
                openroad_binary=core_binary,
                threads=args.eval_threads,
                eval_timeout_sec=args.eval_timeout_sec,
                out_path=out_path,
                log_path=log_path,
            )
            return case, data

        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.eval_jobs)) as pool:
            future_to_case = {
                pool.submit(eval_baseline_one, case, item): case
                for case, item in problems.items()
            }
            for future in concurrent.futures.as_completed(future_to_case):
                case = future_to_case[future]
                try:
                    case, data = future.result()
                except Exception as exc:  # noqa: BLE001 - preserve baseline failure evidence.
                    data = {
                        "status": "baseline_failed",
                        "summary": {},
                        "error": str(exc),
                    }
                baseline_eval_by_case[case] = data
                if data.get("status") == "ok" and legality_ok(data):
                    baseline_metrics[case] = build_metric_vector(data)

    build_results: dict[str, dict[str, Any]] = {}
    build_errors: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.build_jobs)) as pool:
        future_to_spec = {
            pool.submit(
                configure_and_build_variant,
                spec=spec,
                exp_root=exp_root,
                agent_root=agent_root,
                orfs_root=orfs_root,
                state_root=state_root,
                core_root=core_root,
                threads=args.build_threads,
                env=env,
            ): spec
            for spec in selected_specs
        }
        for future in concurrent.futures.as_completed(future_to_spec):
            spec = future_to_spec[future]
            try:
                build_results[spec.name] = future.result()
            except Exception as exc:  # noqa: BLE001 - write evidence and continue.
                build_errors[spec.name] = str(exc)

    records: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []

    def eval_one(spec: VariantSpec, case: str, item: dict[str, Any]) -> dict[str, Any]:
        build_info = build_results.get(spec.name)
        run_tag = f"{args.experiment_id}__{spec.name}__{case}"
        run_record_path = exp_root / "run_records" / f"{run_tag}.json"
        if build_info is None:
            reason = build_errors.get(spec.name, "variant_build_failed")
            record = {
                "run_id": run_tag,
                "experiment_id": args.experiment_id,
                "problem": case,
                "patch_family": spec.family,
                "variant": spec.name,
                "touched_symbol": spec.touched_symbol,
                "target_file": "tools/OpenROAD/src/dpl_evolve",
                "status": "rejected",
                "improved": False,
                "failure_signature": reason,
                "summary": spec.summary,
                "metrics": {},
                "artifacts": {"experiment_root": str(exp_root)},
            }
            run_record_path.parent.mkdir(parents=True, exist_ok=True)
            run_record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            return record

        out_path = exp_root / "eval" / spec.name / f"{case}.json"
        log_path = exp_root / "logs" / "eval" / f"{spec.name}__{case}.log"
        eval_data = run_evaluator(
            python_bin=python_bin,
            agent_root=agent_root,
            orfs_root=orfs_root,
            env=env,
            problem_path=item["problem_path"],
            flow_variant=item["flow_variant"],
            run_tag=run_tag,
            openroad_binary=Path(build_info["openroad_binary"]),
            threads=args.eval_threads,
            eval_timeout_sec=args.eval_timeout_sec,
            out_path=out_path,
            log_path=log_path,
        )
        metrics: dict[str, float] = {}
        score = None
        score_components = None
        legal = legality_ok(eval_data)
        improved: bool | None = None
        if eval_data.get("status") == "ok":
            metrics = build_metric_vector(eval_data)
            reference = baseline_metrics.get(case)
            if reference is not None and legal:
                score, score_components = composite_score(reference, metrics)
                improved = score > 0.0
            elif legal:
                improved = False
            else:
                improved = False
        else:
            improved = False
        signature = failure_signature(eval_data, improved=improved)
        if eval_data.get("status") == "ok" and legal and case not in baseline_metrics:
            signature = "missing_baseline_reference"
        status = "accepted" if improved else "rejected"
        record = {
            "run_id": run_tag,
            "experiment_id": args.experiment_id,
            "problem": case,
            "platform": item["problem"]["platform"],
            "design": item["problem"]["design"],
            "flow_variant": item["flow_variant"],
            "patch_family": spec.family,
            "variant": spec.name,
            "touched_symbol": spec.touched_symbol,
            "target_file": "tools/OpenROAD/src/dpl_evolve",
            "status": status,
            "improved": bool(improved),
            "score": score,
            "score_components": score_components,
            "failure_signature": signature,
            "summary": spec.summary,
            "metrics": metrics,
            "artifacts": {
                "experiment_root": str(exp_root),
                "variant_root": build_info.get("variant_root"),
                "openroad_binary": build_info.get("openroad_binary"),
                "evaluator_json": str(out_path),
                "eval_log": str(log_path),
                "build_log": build_info.get("build_log"),
                "configure_log": build_info.get("configure_log"),
            },
        }
        run_record_path.parent.mkdir(parents=True, exist_ok=True)
        run_record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return record

    eval_tasks: list[tuple[VariantSpec, str, dict[str, Any]]] = [
        (spec, case, item)
        for spec in selected_specs
        for case, item in problems.items()
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.eval_jobs)) as pool:
        future_to_task = {
            pool.submit(eval_one, spec, case, item): (spec, case)
            for spec, case, item in eval_tasks
        }
        for future in concurrent.futures.as_completed(future_to_task):
            spec, case = future_to_task[future]
            try:
                record = future.result()
            except Exception as exc:  # noqa: BLE001 - persist a rejected run record.
                record = {
                    "run_id": f"{args.experiment_id}__{spec.name}__{case}",
                    "experiment_id": args.experiment_id,
                    "problem": case,
                    "patch_family": spec.family,
                    "variant": spec.name,
                    "touched_symbol": spec.touched_symbol,
                    "target_file": "tools/OpenROAD/src/dpl_evolve",
                    "status": "rejected",
                    "improved": False,
                    "failure_signature": str(exc),
                    "summary": spec.summary,
                    "metrics": {},
                    "artifacts": {"experiment_root": str(exp_root)},
                }
            records.append(record)
            append_run_record(run_db_path(state_root), record)
            process_run_record(state_root, record)
            result_rows.append(
                {
                    "case": record["problem"],
                    "variant": record["variant"],
                    "family": record["patch_family"],
                    "legal": record.get("failure_signature") not in {"legality_or_placement_gate_failed"}
                    and bool(record.get("metrics")),
                    "score": record.get("score"),
                    "metrics": record.get("metrics"),
                    "failure_signature": record.get("failure_signature"),
                    "run_id": record.get("run_id"),
                }
            )

    token_roi = write_token_roi_reports(state_root=state_root, out_dir=exp_root / "reports")
    summary = {
        "experiment_id": args.experiment_id,
        "agent_root": str(agent_root),
        "orfs_root": str(orfs_root),
        "state_root": str(state_root),
        "core_root": str(core_root),
        "parallelism": planned["parallelism"],
        "cases": planned["cases"],
        "variants": planned["variants"],
        "baseline": {
            case: {
                "status": data.get("status"),
                "legal": legality_ok(data),
                "metrics": baseline_metrics.get(case),
                "summary": data.get("summary", {}),
            }
            for case, data in baseline_eval_by_case.items()
        },
        "results": sorted(result_rows, key=lambda x: (x["case"], x["variant"])),
        "summary_json": str(exp_root / "summary.json"),
        "summary_md": str(exp_root / "SUMMARY.md"),
        "run_db": str(run_db_path(state_root)),
        "token_roi_md": str(token_roi.get("markdown", "")),
        "token_roi_json": str(token_roi.get("json", "")),
    }
    summary_path = exp_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown_summary(exp_root / "SUMMARY.md", summary)
    print(f"[INFO] Matrix experiment complete: {exp_root}")
    print(f"[INFO] Summary: {exp_root / 'SUMMARY.md'}")


if __name__ == "__main__":
    main()
