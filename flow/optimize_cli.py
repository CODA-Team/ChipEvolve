#!/usr/bin/env python3
"""Command-line orchestration for the plain inter-iteration optimizer.

The optimization algorithms and history APIs remain in :mod:`optimize`.  Keeping
argument parsing, artifact paths, state commits, and prompt-evidence assembly here
lets those algorithms stay importable without also carrying the campaign CLI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Mapping, Optional, Sequence

from candidate_tracking import (
    bind_slots as bind_candidate_slots,
    lifecycle_path as candidate_lifecycle_path,
)
from common import _power_base, get_design_config, get_param_constraints, load_config
from modelfuncs import seed_everything
from prompt_context import build_shared_prompt_context
from optimize import (
    _print_policy_state,
    build_full_param_constraints,
    generate_next_iteration_params,
    load_iteration_history,
    load_resolved_history,
    load_stage_history,
    write_csv,
)
from search_policy import (
    persist_batch_plan,
    persist_optimization_state,
    shape_next_batch,
    update_optimization_state,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate next iteration parameters using Bayesian optimization + LLM."
    )
    parser.add_argument("platform", help="Platform name")
    parser.add_argument("design", help="Design name")
    parser.add_argument("objective", choices=["wl", "ecp", "combo", "TNS_EVAL"],
                        help="Optimization objective")
    parser.add_argument("num_runs", type=int, help="Number of parallel runs")
    parser.add_argument("--iteration", type=int, default=1,
                        help="Current iteration number")
    parser.add_argument("--total-iterations", type=int, default=6,
                        help="Total iterations in the campaign (for exploration annealing)")
    parser.add_argument("--weight-wl", type=float, default=0.5)
    parser.add_argument("--weight-ecp", type=float, default=0.5)
    parser.add_argument("--drp-config", type=Path,
                        default=Path(__file__).parent / "drp_config.json")
    parser.add_argument("--work-dir", type=Path,
                        default=Path(__file__).parent)
    parser.add_argument("--output", type=Path, default=None,
                        help="Output CSV path (default: designs/{platform}/{design}/params.csv)")
    parser.add_argument("--state-only", action="store_true",
                        help="Update campaign best/state without generating a next batch")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)

    derived_seed = seed_everything(
        os.environ.get("DRP_SEED"), os.environ.get("DRP_ITER", ""),
        args.platform, args.design, "optimize")

    config = load_config(args.drp_config)
    backup_dir = args.work_dir / "backup_dir"
    history = load_iteration_history(
        backup_dir, args.platform, args.design, args.iteration
    )
    print(f"Loaded {len(history)} historical entries from {args.iteration} iterations")

    # Keep globally attributable observations separate from lineage-resolved children.
    resolved_history = load_resolved_history(
        backup_dir, args.platform, args.design, args.iteration)
    routing_history = load_stage_history(
        backup_dir, args.platform, args.design, args.iteration, "routing")

    design_cfg = get_design_config(config, args.platform, args.design)
    baseline = design_cfg.get("baseline", {}) if design_cfg else {}
    state_path = (args.work_dir / "designs" / args.platform / args.design
                  / "optimization_state.json")
    campaign_id = None
    try:
        campaign_id = json.loads(
            (backup_dir / args.platform / args.design
             / "campaign_manifest.json").read_text()).get("campaign_id")
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    state = update_optimization_state(
        state_path,
        current_iteration=args.iteration,
        objective=args.objective,
        clean_history=history,
        resolved_history=resolved_history,
        routing_history=routing_history,
        policy_config=config,
        power_budget=config.get("power_budget"),
        power_base=_power_base(args.platform, args.design),
        wl_base=float(baseline.get("wl_base", 1.0)),
        ecp_base=float(baseline.get("ecp_base", 1.0)),
        weight_wl=args.weight_wl,
        weight_ecp=args.weight_ecp,
        num_runs=args.num_runs,
        platform=args.platform,
        design=args.design,
        campaign_id=campaign_id,
        persist=False,
    )
    _print_policy_state(state)
    if args.state_only:
        persist_optimization_state(state_path, state)
        print("[search-policy] state-only update complete; no next batch requested.")
        return
    if state.get("enabled") and state.get("stop_requested"):
        persist_optimization_state(state_path, state)
        print("[search-policy] early stop requested; skipping next-batch generation.")
        return

    full_constraints = build_full_param_constraints(
        config, args.platform, args.design)
    cp0 = None
    try:
        cp0 = float((args.work_dir / "designs" / args.platform / args.design
                     / "cp0.txt").read_text().strip())
    except (OSError, TypeError, ValueError):
        pass
    try:
        from prompt_evidence import build_prompt_evidence, load_model_score_evidence

        model_score_records = load_model_score_evidence(
            backup_dir, args.platform, args.design, args.iteration)
        prompt_evidence = build_prompt_evidence(
            args.objective,
            history,
            resolved_history=resolved_history,
            routing_history=routing_history,
            optimization_state=state,
            constraints=full_constraints,
            power_base=_power_base(args.platform, args.design),
            power_budget=config.get("power_budget"),
            cp0=cp0,
            model_score_records=model_score_records,
        )
        prompt_evidence.update(build_shared_prompt_context(
            config, args.platform, args.design, args.objective,
            prompt_evidence))
    except Exception as exc:
        print(f"[optimize][WARN] structured prompt evidence unavailable ({exc}).",
              file=sys.stderr)
        prompt_evidence = {}
    next_lifecycle = candidate_lifecycle_path(args.work_dir, args.iteration + 1)

    params_list = generate_next_iteration_params(
        config=config,
        platform=args.platform,
        design=args.design,
        objective=args.objective,
        num_runs=args.num_runs,
        history=history,
        weight_wl=args.weight_wl,
        weight_ecp=args.weight_ecp,
        total_iters=args.total_iterations,
        candidate_campaign_id=(campaign_id or f"adhoc:{args.platform}:{args.design}"),
        candidate_iteration=args.iteration + 1,
        candidate_lifecycle_path=next_lifecycle,
        prompt_evidence=prompt_evidence,
    )

    params_list, batch_plan = shape_next_batch(
        params_list,
        clean_history=history,
        resolved_history=resolved_history,
        routing_history=routing_history,
        state=state,
        full_constraints=full_constraints,
        num_runs=args.num_runs,
        seed=derived_seed,
        policy_config=config,
    )
    bind_candidate_slots(
        next_lifecycle,
        params_list,
        stage="search_policy_shaped",
        details=batch_plan.get("candidate_slots", {}),
    )

    csv_path = args.output or (
        args.work_dir / "designs" / args.platform / args.design
        / f"{args.platform}_{args.design}.csv")
    synthesis_constraints = get_param_constraints(config, "synthesis", design_cfg)
    placement_constraints = get_param_constraints(config, "placement", design_cfg)
    param_order = (
        list(synthesis_constraints.keys())
        + list(placement_constraints.keys())
        + ["clk_period"]
    )

    write_csv(params_list, csv_path, param_order)
    csv_sha256 = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    planned_slots = batch_plan.get("candidate_slots", [])
    csv_event_details = []
    for run_id in range(1, len(params_list) + 1):
        slot_detail = (
            planned_slots[run_id - 1]
            if isinstance(planned_slots, list) and run_id <= len(planned_slots)
            and isinstance(planned_slots[run_id - 1], Mapping)
            else {}
        )
        csv_event_details.append({
            **dict(slot_detail),
            "csv_path": str(csv_path.resolve()),
            "csv_sha256": csv_sha256,
            "row_number": run_id,
        })
    bind_candidate_slots(
        next_lifecycle,
        params_list,
        stage="csv_written",
        details=csv_event_details,
    )

    # Commit state last so a crash cannot publish a contract for an incomplete CSV.
    state = persist_batch_plan(
        state_path, state, batch_plan,
        csv_path=csv_path,
        target_iteration=args.iteration + 1,
        expected_rows=args.num_runs,
    )
    _print_policy_state(state, state.get("next_batch_plan", batch_plan))


if __name__ == "__main__":
    main()
