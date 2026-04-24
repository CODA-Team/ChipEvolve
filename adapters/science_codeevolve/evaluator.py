"""
Thin evaluator wrapper for the local dpl_evolve control plane.

This module does not replace the baseline harness. It only:
- resolves the correct project-standard commands
- applies local run/build locking
- enforces timeout and memory budgets
- captures compact failure tails for debugging
- optionally builds OpenROAD
- runs either one baseline line or the full suite
- loads the resulting metrics JSON
- writes a compact evaluator JSON
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

AGENT_ROOT = Path(__file__).resolve().parents[2]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from runtime_paths import reexec_with_module, resolve_runtime_paths

try:
    import yaml
except ModuleNotFoundError:
    reexec_with_module("yaml", __file__, sys.argv)
    raise

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from guarded_exec import CommandResult, run_guarded_command
    from lock import DirectoryLockError
else:
    from .guarded_exec import CommandResult, run_guarded_command
    from .lock import DirectoryLockError


def runtime_paths():
    return resolve_runtime_paths(
        anchor_file=__file__,
        agent_root_levels_up=2,
        script_name="evaluator.py",
    )


def load_problem(problem_yaml: Path) -> Dict[str, Any]:
    return yaml.safe_load(problem_yaml.read_text(encoding="utf-8"))


def infer_design_config(problem: Dict[str, Any]) -> str:
    design = problem.get("design")
    platform = problem.get("platform")
    explicit = problem.get("design_config")
    if explicit:
        return explicit
    if not design or not platform:
        raise ValueError("problem.yaml must provide design/platform or design_config")
    return f"./designs/{platform}/{design}/config.mk"


def default_flow_variant(problem: Dict[str, Any], mode: str) -> str:
    design = problem.get("design", "design")
    platform = problem.get("platform", "platform")
    return f"eval_{mode}_{platform}_{design}"


def shell_join(args: Iterable[str]) -> str:
    return " ".join(subprocess.list2cmdline([arg]) for arg in args)


def baseline_root(agent_root: Path) -> Path:
    return agent_root / "baseline"


def resolve_runtime_path(
    root: Path,
    explicit_value: str | None,
    budget: Dict[str, Any],
    budget_key: str,
    default_path: Path,
) -> Path:
    value = explicit_value if explicit_value else budget.get(budget_key)
    if not value:
        return default_path
    path = Path(os.path.expandvars(os.path.expanduser(str(value))))
    if not path.is_absolute():
        if path.parts and path.parts[0] == root.name:
            return (root.parent / path).resolve()
        if path.exists() or path.parent.exists():
            return path.resolve()
        path = root / path
    return path.resolve()


def build_command(
    agent_root: Path,
    threads: int,
    build_mode: str,
    build_dir: Path,
    install_root: Path,
    openroad_binary_path: Path,
) -> List[str]:
    if build_mode == "openroad_only":
        return [
            str(agent_root / "scripts" / "build_openroad_only.sh"),
            str(threads),
        ]
    return ["./build_openroad.sh", "--local", "--threads", str(threads)]


def line_command(
    agent_root: Path,
    line: str,
    design_config: str,
    flow_variant: str,
    run_tag: str,
    threads: int,
    evolve_engine: str,
) -> List[str]:
    base = [
        str(baseline_root(agent_root) / "run_baseline.sh"),
        "--design-config",
        design_config,
        "--track",
        "strict",
        "--flow-variant",
        flow_variant,
        "--run-tag",
        run_tag,
        "--threads",
        str(threads),
    ]
    if line == "baseline_default":
        return [str(baseline_root(agent_root) / "run_or_default.sh"), *base[1:]]
    if line == "baseline_dreamplace_abacus":
        return [str(baseline_root(agent_root) / "run_dp_abacus.sh"), *base[1:]]
    if line == "evolve_line":
        return [
            str(baseline_root(agent_root) / "run_evolve_line.sh"),
            *base[1:],
            "--engine",
            evolve_engine,
        ]
    raise ValueError(f"Unsupported line: {line}")


def suite_command(
    agent_root: Path,
    design_config: str,
    flow_variant: str,
    threads: int,
    tag_prefix: str,
    evolve_engine: str,
) -> List[str]:
    cmd = [
        str(baseline_root(agent_root) / "run_baseline_suite.sh"),
        "--design-config",
        design_config,
        "--flow-variant",
        flow_variant,
        "--threads",
        str(threads),
        "--evolve-engine",
        evolve_engine,
    ]
    if tag_prefix:
        cmd.extend(["--tag-prefix", tag_prefix])
    return cmd


def report_root(root: Path, problem: Dict[str, Any], flow_variant: str) -> Path:
    return (
        root
        / "flow"
        / "reports"
        / problem["platform"]
        / problem["design"]
        / flow_variant
        / "dpl_evolve_baseline"
    )


def metrics_path_for_run(report_dir: Path, run_tag: str) -> Path:
    return report_dir / run_tag / "metrics.json"


def load_metrics(metrics_path: Path) -> Dict[str, Any]:
    return json.loads(metrics_path.read_text(encoding="utf-8"))


def summarize_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    manifest = metrics.get("manifest", {})
    legalization = metrics.get("legalization", {})
    engine = manifest.get("engine")
    if engine == "dreamplace_abacus":
        engine_path_confirmed = "dreamplace_bridge"
    elif legalization.get("use_negotiation") and legalization.get("use_abacus"):
        engine_path_confirmed = "negotiation_abacus"
    elif legalization.get("use_negotiation"):
        engine_path_confirmed = "negotiation"
    else:
        engine_path_confirmed = "diamond_default"
    return {
        "engine": engine,
        "engine_path_confirmed": engine_path_confirmed,
        "track": manifest.get("track"),
        "command_set": manifest.get("command_set"),
        "legalization_status": legalization.get("status"),
        "placement_violations": metrics.get("legality", {}).get("placement_violations"),
        "hpwl_before_micron": metrics.get("hpwl_proxy", {}).get("before_micron"),
        "hpwl_after_micron": metrics.get("hpwl_proxy", {}).get("after_micron"),
        "hpwl_delta_micron": metrics.get("hpwl_proxy", {}).get("delta_micron"),
        "runtime_seconds": metrics.get("runtime_seconds"),
        "setup_ws": metrics.get("timing_metrics", {}).get("setup_ws"),
        "setup_tns": metrics.get("timing_metrics", {}).get("setup_tns"),
        "hold_ws": metrics.get("timing_metrics", {}).get("hold_ws"),
        "hold_tns": metrics.get("timing_metrics", {}).get("hold_tns"),
        "total_power": metrics.get("power_metrics", {}).get("total"),
        "avg_displacement_micron": metrics.get("displacement", {}).get("average_displacement_micron"),
        "max_displacement_micron": metrics.get("displacement", {}).get("max_displacement_micron"),
    }


def load_suite_summary(summary_tsv: Path) -> List[Dict[str, str]]:
    with summary_tsv.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def load_budget(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        return {}
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return config.get("BUDGET_CONFIG", {})


def resolve_timeout(
    explicit_value: int | None,
    budget: Dict[str, Any],
    budget_key: str,
) -> int | None:
    if explicit_value is not None:
        return explicit_value
    value = budget.get(budget_key)
    if value in (None, "", 0):
        return None
    return int(value)


def resolve_memory_limit_bytes(
    explicit_mb: int | None,
    budget: Dict[str, Any],
    budget_key: str,
) -> int | None:
    if explicit_mb is not None:
        return explicit_mb * 1024 * 1024
    value = budget.get(budget_key)
    if value in (None, "", 0):
        return None
    return int(value) * 1024 * 1024


def run_dir_for_lock(
    root: Path,
    problem: Dict[str, Any],
    flow_variant: str,
    mode: str,
    run_tag: str | None = None,
) -> Path:
    base = report_root(root, problem, flow_variant)
    if mode == "suite":
        return base
    assert run_tag is not None
    return base / run_tag


def build_dir_for_lock(install_root: Path) -> Path:
    return install_root


def execute_step(
    cmd: List[str],
    cwd: Path,
    *,
    timeout_seconds: int | None,
    max_memory_bytes: int | None,
    monitor_interval_seconds: float,
    lock_dir: Path | None,
    env: Dict[str, str] | None = None,
) -> CommandResult:
    return run_guarded_command(
        cmd,
        cwd,
        timeout_seconds=timeout_seconds,
        max_memory_bytes=max_memory_bytes,
        monitor_interval_seconds=monitor_interval_seconds,
        env=env,
        lock_dir=lock_dir,
    )


def evaluate(args: argparse.Namespace) -> Dict[str, Any]:
    runtime = runtime_paths()
    root = runtime.orfs_root
    agent_root = runtime.agent_root
    problem = load_problem(args.problem)
    design_config = infer_design_config(problem)
    flow_variant = args.flow_variant or default_flow_variant(problem, args.mode)
    out_path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    budget = load_budget(args.config)
    build_timeout = resolve_timeout(args.build_timeout_sec, budget, "build_timeout_sec")
    eval_timeout = resolve_timeout(args.eval_timeout_sec, budget, "eval_timeout_sec")
    build_mem_bytes = resolve_memory_limit_bytes(
        args.build_mem_limit_mb, budget, "build_mem_limit_mb"
    )
    eval_mem_bytes = resolve_memory_limit_bytes(
        args.eval_mem_limit_mb, budget, "eval_mem_limit_mb"
    )
    monitor_interval_seconds = float(
        args.monitor_interval_sec
        if args.monitor_interval_sec is not None
        else budget.get("monitor_interval_sec", 0.5)
    )
    build_mode = str(budget.get("build_mode", args.build_mode or "full_local"))
    openroad_build_dir = resolve_runtime_path(
        root,
        args.openroad_build_dir,
        budget,
        "openroad_build_dir",
        root / "tools" / "OpenROAD" / "build",
    )
    openroad_install_root = resolve_runtime_path(
        root,
        args.openroad_install_root,
        budget,
        "openroad_install_root",
        root / "tools" / "install" / "OpenROAD",
    )
    openroad_bin = resolve_runtime_path(
        root,
        args.openroad_binary,
        budget,
        "openroad_binary",
        openroad_install_root / "bin" / "openroad",
    )

    build_cmd = build_command(
        agent_root,
        args.threads,
        build_mode,
        openroad_build_dir,
        openroad_install_root,
        openroad_bin,
    )
    build_env = os.environ.copy()
    build_env["OPENROAD_BUILD_DIR"] = str(openroad_build_dir)
    build_env["OPENROAD_INSTALL_ROOT"] = str(openroad_install_root)
    build_env["OPENROAD_BINARY"] = str(openroad_bin)
    run_env = os.environ.copy()
    run_env["OPENROAD_BINARY"] = str(openroad_bin)
    run_env["OPENROAD_EXE"] = str(openroad_bin)
    result: Dict[str, Any] = {
        "problem": problem.get("name"),
        "mode": args.mode,
        "design_config": design_config,
        "flow_variant": flow_variant,
        "build_mode": build_mode,
        "commands": {
            "build": shell_join(build_cmd),
        },
        "budgets": {
            "build_timeout_sec": build_timeout,
            "eval_timeout_sec": eval_timeout,
            "build_mem_limit_mb": None
            if build_mem_bytes is None
            else build_mem_bytes // (1024 * 1024),
            "eval_mem_limit_mb": None
            if eval_mem_bytes is None
            else eval_mem_bytes // (1024 * 1024),
            "monitor_interval_sec": monitor_interval_seconds,
        },
        "paths": {
            "repo_root": str(root),
            "agent_root": str(agent_root),
            "state_root": str(runtime.state_root),
            "baseline_root": str(baseline_root(agent_root)),
            "openroad_build_dir": str(openroad_build_dir),
            "openroad_install_root": str(openroad_install_root),
            "openroad_binary": str(openroad_bin),
            "report_root": str(report_root(root, problem, flow_variant)),
        },
        "command_results": {},
    }

    if args.mode == "suite":
        run_cmd = suite_command(
            agent_root,
            design_config,
            flow_variant,
            args.threads,
            args.tag_prefix,
            args.evolve_engine,
        )
        result["commands"]["run"] = shell_join(run_cmd)
        summary_tsv = report_root(root, problem, flow_variant) / "suite_runs.tsv"
        result["expected_summary_tsv"] = str(summary_tsv)
    else:
        run_tag = args.run_tag or args.line
        run_cmd = line_command(
            agent_root,
            args.line,
            design_config,
            flow_variant,
            run_tag,
            args.threads,
            args.evolve_engine,
        )
        result["line"] = args.line
        result["run_tag"] = run_tag
        result["commands"]["run"] = shell_join(run_cmd)
        result["expected_metrics_path"] = str(
            metrics_path_for_run(report_root(root, problem, flow_variant), run_tag)
        )

    if args.dry_run:
        result["status"] = "dry_run"
        return result

    try:
        if not args.use_existing:
            if not args.skip_build:
                build_result = execute_step(
                    build_cmd,
                    root,
                    timeout_seconds=build_timeout,
                    max_memory_bytes=build_mem_bytes,
                    monitor_interval_seconds=monitor_interval_seconds,
                    lock_dir=build_dir_for_lock(openroad_install_root),
                    env=build_env,
                )
                result["command_results"]["build"] = build_result.to_dict()
                if build_result.returncode != 0:
                    result["status"] = "build_failed"
                    return result

            run_result = execute_step(
                run_cmd,
                root,
                timeout_seconds=eval_timeout,
                max_memory_bytes=eval_mem_bytes,
                monitor_interval_seconds=monitor_interval_seconds,
                lock_dir=run_dir_for_lock(
                    root,
                    problem,
                    flow_variant,
                    args.mode,
                    result.get("run_tag"),
                ),
                env=run_env,
            )
            result["command_results"]["run"] = run_result.to_dict()
            if run_result.returncode != 0:
                result["status"] = "run_failed"
                return result

        if args.mode == "suite":
            summary_rows = load_suite_summary(summary_tsv)
            evaluated_rows = []
            for row in summary_rows:
                metrics_path = Path(row["metrics_json"])
                if metrics_path.exists():
                    summary = summarize_metrics(load_metrics(metrics_path))
                else:
                    summary = {"status": "missing_metrics"}
                evaluated_rows.append(
                    {
                        "label": row["label"],
                        "run_tag": row["run_tag"],
                        "metrics_json": row["metrics_json"],
                        "summary": summary,
                    }
                )
            result["status"] = "ok"
            result["suite_summary_tsv"] = str(summary_tsv)
            result["runs"] = evaluated_rows
            return result

        metrics_path = metrics_path_for_run(report_root(root, problem, flow_variant), result["run_tag"])
        metrics = load_metrics(metrics_path)
        result["status"] = "ok"
        result["metrics_path"] = str(metrics_path)
        result["summary"] = summarize_metrics(metrics)
        return result
    except DirectoryLockError as exc:
        result["status"] = "locked"
        result["error"] = str(exc)
        return result
    except FileNotFoundError as exc:
        result["status"] = "missing_artifact"
        result["error"] = str(exc)
        return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument(
        "--config",
        type=Path,
        default=None,
    )
    ap.add_argument("--mode", choices=["single", "suite"], default="single")
    ap.add_argument(
        "--line",
        choices=[
            "baseline_default",
            "baseline_dreamplace_abacus",
            "evolve_line",
        ],
        default="evolve_line",
    )
    ap.add_argument("--flow-variant")
    ap.add_argument("--run-tag")
    ap.add_argument("--tag-prefix", default="")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument(
        "--evolve-engine",
        choices=["default", "negotiation", "negotiation_abacus"],
        default="default",
    )
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--use-existing", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--build-timeout-sec", type=int)
    ap.add_argument("--eval-timeout-sec", type=int)
    ap.add_argument("--build-mem-limit-mb", type=int)
    ap.add_argument("--eval-mem-limit-mb", type=int)
    ap.add_argument("--monitor-interval-sec", type=float)
    ap.add_argument(
        "--build-mode",
        choices=["full_local", "openroad_only"],
    )
    ap.add_argument("--openroad-build-dir")
    ap.add_argument("--openroad-install-root")
    ap.add_argument("--openroad-binary")
    args = ap.parse_args()
    if args.config is None:
        args.config = runtime_paths().agent_root / "configs" / "codex_smoke.yaml"

    result = evaluate(args)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
