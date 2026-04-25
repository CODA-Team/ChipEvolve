#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = AGENT_ROOT / "scripts"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from family_mutations import list_supported_families, resolve_family_mutation
from materialize_family_variant import materialize_family_variant
from runtime_paths import resolve_runtime_paths
from run_variant_experiment_matrix import (
    DEFAULT_CASES,
    discover_flow_variant,
    ensure_registered_common_core,
    find_python_with_yaml,
    parse_problem,
    run_command,
    run_evaluator,
)


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tail_text(path: Path, max_chars: int = 4000) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]


def classify_eval(eval_data: dict[str, Any]) -> dict[str, Any]:
    status = eval_data.get("status", "missing")
    summary = eval_data.get("summary") or {}
    command_results = eval_data.get("command_results") or {}
    run_result = command_results.get("run") or {}
    metrics = summary.get("metrics") or eval_data.get("metrics") or {}
    legal = bool(
        status == "ok"
        and (
            summary.get("legal") is True
            or metrics.get("placement_violations", metrics.get("violations", 0)) in (0, "0", None)
        )
    )
    failure = None
    if status != "ok":
        if run_result.get("timed_out"):
            failure = "eval_timeout"
        else:
            failure = status
    elif not legal:
        failure = "legality_gate_failed"
    return {
        "status": status,
        "legal": legal,
        "failure_signature": failure,
        "run_timed_out": bool(run_result.get("timed_out")),
        "metrics_path": summary.get("metrics_path") or eval_data.get("metrics_path"),
        "run_elapsed_seconds": run_result.get("elapsed_seconds"),
    }


def build_variant(
    *,
    family: str,
    gate_root: Path,
    agent_root: Path,
    orfs_root: Path,
    state_root: Path,
    core_root: Path,
    threads: int,
    force: bool,
    env: dict[str, str],
) -> dict[str, Any]:
    variant_root = gate_root / "variant"
    src_dir = variant_root / "src" / "dpl_evolve"
    materialized = materialize_family_variant(
        family,
        src_dir,
        force=force,
        agent_root=agent_root,
        orfs_root=orfs_root,
        state_root=state_root,
    )
    configure_log = gate_root / "logs" / "configure.log"
    build_log = gate_root / "logs" / "build.log"
    configure_cmd = [
        str(agent_root / "scripts" / "configure_openroad_variant_relink.sh"),
        "--variant-root",
        str(variant_root),
        "--dpl-src",
        str(src_dir),
        "--core-root",
        str(core_root),
    ]
    started = time.time()
    run_command(configure_cmd, cwd=agent_root, env=env, log_path=configure_log)
    build_cmd = [
        str(agent_root / "scripts" / "build_openroad_variant_relink.sh"),
        "--variant-root",
        str(variant_root),
        "--dpl-src",
        str(src_dir),
        "--core-root",
        str(core_root),
        "--threads",
        str(threads),
    ]
    run_command(build_cmd, cwd=agent_root, env=env, log_path=build_log)
    elapsed = time.time() - started
    binary = variant_root / "install" / "OpenROAD" / "bin" / "openroad"
    if not binary.is_file():
        raise RuntimeError(f"Variant build did not produce binary: {binary}")

    result = {
        "status": "ok",
        "family": family,
        "source_kind": materialized.source_kind,
        "family_status": materialized.status,
        "variant_root": str(variant_root),
        "variant_src": str(src_dir),
        "openroad_binary": str(binary),
        "materialization_metadata": str(materialized.metadata_path),
        "configure_log": str(configure_log),
        "build_log": str(build_log),
        "elapsed_seconds": elapsed,
    }
    write_json(gate_root / "build.json", result)
    return result


def write_promotion_decision(
    path: Path,
    *,
    family: str,
    recipe_status: str,
    build_result: dict[str, Any],
    case_results: list[dict[str, Any]],
) -> None:
    lines = [
        f"# Promotion Decision: {family}",
        "",
        f"- Source status: `{recipe_status}`",
        f"- Build status: `{build_result.get('status', 'missing')}`",
        f"- OpenROAD binary: `{build_result.get('openroad_binary', '')}`",
        "",
        "## Case Results",
        "",
        "| Case | Gate | Status | Legal | Failure | Metrics |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in case_results:
        cls = item.get("classification", {})
        lines.append(
            "| `{case}` | `{gate}` | `{status}` | `{legal}` | `{failure}` | `{metrics}` |".format(
                case=item.get("case", ""),
                gate=item.get("gate_mode", ""),
                status=cls.get("status", item.get("status", "")),
                legal=cls.get("legal", ""),
                failure=cls.get("failure_signature") or "",
                metrics=cls.get("metrics_path") or "",
            )
        )
    hard_failures = [
        item
        for item in case_results
        if item.get("classification", {}).get("failure_signature")
    ]
    legal_cases = [
        item
        for item in case_results
        if item.get("classification", {}).get("legal") is True
    ]
    lines.extend(["", "## Decision", ""])
    if recipe_status.startswith("bringup_alias"):
        decision = "donor"
        reason = "This is a harness bring-up alias, not an algorithm-promotion result."
    elif build_result.get("status") != "ok":
        decision = "rejected"
        reason = "Build did not complete."
    elif hard_failures:
        decision = "repair"
        reason = "At least one gate failed or timed out."
    elif len(legal_cases) == len(case_results):
        decision = "base_candidate"
        reason = "All requested gates completed legally; large-case quality still needs review."
    else:
        decision = "repair"
        reason = "Insufficient legal gate coverage."
    lines.append(f"- Decision: `{decision}`")
    lines.append(f"- Reason: {reason}")
    lines.append("")
    lines.append("Fallback-to-diamond/default is not accepted as family success; verify engine-path logs before promotion.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run base bring-up gates for a dpl_evolve family.")
    parser.add_argument("--family")
    parser.add_argument("--experiment-id", default=f"family_base_gate_{now_stamp()}")
    parser.add_argument("--cases", nargs="+", default=DEFAULT_CASES)
    parser.add_argument("--threads", type=int, default=10)
    parser.add_argument("--eval-timeout-sec", type=int, default=900)
    parser.add_argument("--legalizer-only-first", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--list-families", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.list_families:
        for family in list_supported_families():
            print(f"{family.family}\t{family.source_kind}\t{family.status}\t{family.summary}")
        return
    if not args.family:
        raise SystemExit("--family is required unless --list-families is used")

    runtime = resolve_runtime_paths(
        anchor_file=__file__,
        agent_root_levels_up=1,
        script_name="run_family_base_gate.py",
    )
    agent_root = runtime.agent_root
    orfs_root = runtime.orfs_root
    state_root = runtime.state_root
    recipe = resolve_family_mutation(args.family)
    gate_root = state_root / "family_gates" / args.experiment_id / args.family
    gate_root.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DPL_EVOLVE_AGENT_ROOT"] = str(agent_root)
    env["ORFS_ROOT"] = str(orfs_root)
    env["DPL_EVOLVE_STATE_ROOT"] = str(state_root)
    env["DPL_EVOLVE_SKIP_ENV_SH"] = "1"

    plan = {
        "schema_version": 1,
        "experiment_id": args.experiment_id,
        "family": args.family,
        "source_kind": recipe.source_kind,
        "source_status": recipe.status,
        "cases": args.cases,
        "threads": args.threads,
        "eval_timeout_sec": args.eval_timeout_sec,
        "legalizer_only_first": args.legalizer_only_first,
        "agent_root": str(agent_root),
        "orfs_root": str(orfs_root),
        "state_root": str(state_root),
    }
    write_json(gate_root / "plan.json", plan)

    if args.dry_run:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return

    build_result: dict[str, Any]
    case_results: list[dict[str, Any]] = []
    try:
        core_root = ensure_registered_common_core(orfs_root, state_root)
        build_result = build_variant(
            family=args.family,
            gate_root=gate_root,
            agent_root=agent_root,
            orfs_root=orfs_root,
            state_root=state_root,
            core_root=core_root,
            threads=args.threads,
            force=args.force,
            env=env,
        )
    except Exception as exc:
        build_result = {
            "status": "build_failed",
            "family": args.family,
            "source_kind": recipe.source_kind,
            "family_status": recipe.status,
            "error": str(exc),
        }
        write_json(gate_root / "build.json", build_result)
        write_promotion_decision(
            gate_root / "PROMOTION_DECISION.md",
            family=args.family,
            recipe_status=recipe.status,
            build_result=build_result,
            case_results=[],
        )
        raise

    if args.build_only:
        write_promotion_decision(
            gate_root / "PROMOTION_DECISION.md",
            family=args.family,
            recipe_status=recipe.status,
            build_result=build_result,
            case_results=[],
        )
        return

    python_bin = find_python_with_yaml()
    openroad_binary = Path(build_result["openroad_binary"])
    for case in args.cases:
        problem_path = agent_root / "problems" / case / "problem.yaml"
        problem = parse_problem(problem_path)
        flow_variant = discover_flow_variant(orfs_root, problem)
        gate_modes = ["strict"]
        if args.legalizer_only_first and case == "bp_quad_nangate45":
            gate_modes = ["legalizer_only", "full_metrics"]
        for gate_mode in gate_modes:
            run_tag = f"{args.experiment_id}_{args.family}_{case}_{gate_mode}"
            out_path = gate_root / "eval" / f"{case}_{gate_mode}.json"
            log_path = gate_root / "logs" / "eval" / f"{case}_{gate_mode}.log"
            eval_data = run_evaluator(
                python_bin=python_bin,
                agent_root=agent_root,
                orfs_root=orfs_root,
                env=env,
                problem_path=problem_path,
                flow_variant=flow_variant,
                run_tag=run_tag,
                openroad_binary=openroad_binary,
                threads=args.threads,
                eval_timeout_sec=args.eval_timeout_sec,
                out_path=out_path,
                log_path=log_path,
            )
            classification = classify_eval(eval_data)
            result = {
                "case": case,
                "gate_mode": gate_mode,
                "problem_path": str(problem_path),
                "flow_variant": flow_variant,
                "run_tag": run_tag,
                "eval_json": str(out_path),
                "eval_log": str(log_path),
                "classification": classification,
                "status": eval_data.get("status"),
            }
            case_results.append(result)
            write_json(gate_root / "case_results" / f"{case}_{gate_mode}.json", result)
            if gate_mode == "legalizer_only" and classification.get("failure_signature"):
                break

    write_json(gate_root / "summary.json", {"build": build_result, "cases": case_results})
    write_promotion_decision(
        gate_root / "PROMOTION_DECISION.md",
        family=args.family,
        recipe_status=recipe.status,
        build_result=build_result,
        case_results=case_results,
    )


if __name__ == "__main__":
    main()
