#!/usr/bin/env python3
"""
LLM + Bayesian parameter generation agent for DRP-Agent.

Generates stage-specific parameters (CTS or routing) for runs that replace
killed runs after DRP. Uses a combination of:
- 20% perturbation from source run parameters
- 80% LLM + Bayesian optimization recommended parameters
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np

from modelfuncs import (
    bayesian_suggest,
    clip_params,
    latin_hypercube_sample,
    params_to_array,
    perturb_params,
)
from prompts import (
    SYSTEM_PROMPT,
    build_cts_prompt,
    build_routing_prompt,
)
from prompt_context import build_shared_prompt_context
from prompt_evidence import build_prompt_evidence, load_model_score_evidence
# config/LLM helpers now live in common.py (breaks the optimize<->agent cycle).
# Re-imported here so existing `from agent import call_llm/...` call sites keep working.
from common import (
    call_llm,
    get_design_config,
    get_param_constraints,
    load_config,
    parse_llm_json,
)
from llm_usage import LLMUsageError


def extract_current_params(config_path: Path, param_names: List[str]) -> Dict[str, float]:
    """Extract current parameter values from a config.mk file."""
    params = {}
    if not config_path.exists():
        return params

    content = config_path.read_text()
    for name in param_names:
        # Anchor the complete assignment name.  Without the line boundary,
        # PIN_LAYER_ADJUST also matched FLOORPLAN_PIN_LAYER_ADJUST and made the
        # routing proposal depend on the wrong (floorplan-scoped) value.
        pattern = (
            rf'^\s*(?:export\s+)?{re.escape(name)}\s*=\s*'
            rf'([\d.eE+\-]+)\s*(?:#.*)?$'
        )
        m = re.search(pattern, content, flags=re.MULTILINE)
        if m:
            try:
                params[name] = float(m.group(1))
            except ValueError:
                pass

    return params


_PROMPT_EVIDENCE_FIELDS = (
    "objective_contract",
    "top_successful_configs",
    "stratified_bests",
    "basin_summary",
    "parameter_distributions",
    "distance_info",
    "run_classifications",
)


def _full_prompt_constraints(config: dict, design_cfg: Optional[dict]) -> Dict[str, dict]:
    """Return the complete execution-space bounds used by prompt evidence."""
    constraints: Dict[str, dict] = {}
    for stage in ("synthesis", "placement", "cts", "routing"):
        constraints.update(get_param_constraints(config, stage, design_cfg))
    clock_range = (design_cfg or {}).get("clock_period_range")
    if isinstance(clock_range, (list, tuple)) and len(clock_range) >= 2:
        constraints["clk_period"] = {
            "type": "float",
            "range": [clock_range[0], clock_range[1]],
            "description": "Per-run implementation clock period",
        }
    return constraints


def _source_parent_family(config_path: Path, stage: str) -> Optional[str]:
    """Resolve the same stage-scoped family identity used by lineage history."""
    try:
        from lineage import config_snapshot
        from optimize import parameter_family

        snapshot = config_snapshot(config_path)
        params = dict(snapshot.get("params") or {})
        context = snapshot.get("routing_context")
        sdc = snapshot.get("effective_sdc") or {}
        sdc_identity = sdc.get("recipe_sha256", sdc.get("sha256"))
        return parameter_family(params, stage, context, sdc_identity)
    except Exception:
        return None


def build_stage_source_target_edges(
    stage: str,
    source_run_ids: List[int],
    target_run_ids: List[int],
    config_dir: Path,
    *,
    work_dir: Optional[Path] = None,
    lifecycle_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Build the positional execution map that the stage LLM must honor.

    When the current candidate lifecycle exists, the planned child identity is
    derived using the same immutable proposal key that ``drp.py`` records after the
    mutation.  If lifecycle evidence is unavailable, identity fields remain null and
    the reason is explicit; run IDs and parent families are still reported.
    """
    if stage not in {"cts", "routing"}:
        raise ValueError(f"unsupported stage for clone edges: {stage!r}")
    if not source_run_ids:
        return []

    iteration = None
    raw_iteration = os.environ.get("DRP_ITER")
    try:
        iteration = int(raw_iteration) if raw_iteration not in (None, "") else None
    except (TypeError, ValueError):
        iteration = None
    if lifecycle_path is None and work_dir is not None and iteration is not None:
        lifecycle_path = Path(work_dir) / "tmp" / f"candidate_lifecycle_iter{iteration}.json"

    lifecycle = None
    lifecycle_error = "candidate_lifecycle_not_supplied"
    if lifecycle_path is not None:
        path = Path(lifecycle_path)
        if path.is_file():
            try:
                from candidate_tracking import load_lifecycle
                lifecycle = load_lifecycle(path)
                iteration = int(lifecycle["iteration"])
                lifecycle_error = None
            except Exception as exc:
                lifecycle_error = f"candidate_lifecycle_unreadable:{type(exc).__name__}"
        else:
            lifecycle_error = "candidate_lifecycle_missing"

    slots = {}
    if lifecycle is not None:
        for slot in lifecycle.get("slots", []):
            try:
                slots[int(slot["run_id"])] = slot
            except (KeyError, TypeError, ValueError):
                continue

    clone_from_stage = "place" if stage == "cts" else "cts"
    edges = []
    for index, target_run_id in enumerate(target_run_ids):
        source_run_id = source_run_ids[index % len(source_run_ids)]
        mapping_kind = (
            "self" if int(source_run_id) == int(target_run_id) else "clone")
        source_slot = slots.get(int(source_run_id))
        target_slot = slots.get(int(target_run_id))
        source_candidate_id = (
            source_slot.get("candidate_id") if source_slot is not None else None)
        replaced_candidate_id = (
            target_slot.get("candidate_id")
            if mapping_kind == "clone" and target_slot is not None else None)
        lineage_event_id = (
            f"iter{iteration}:{clone_from_stage}:{source_run_id}->{target_run_id}"
            if iteration is not None else None)
        target_candidate_id = None
        identity_status = lifecycle_error
        if lifecycle is not None and source_slot is not None and target_slot is not None:
            try:
                from candidate_tracking import make_candidate_id
                if mapping_kind == "self":
                    target_candidate_id = source_candidate_id
                    identity_status = "self_conditioned_existing_candidate"
                else:
                    target_candidate_id = make_candidate_id(
                        lifecycle["campaign_id"], lifecycle["iteration"],
                        f"drp-edge:{lineage_event_id}")
                    identity_status = "resolved_from_candidate_lifecycle"
            except Exception as exc:
                identity_status = f"candidate_identity_unavailable:{type(exc).__name__}"
        elif lifecycle is not None:
            identity_status = "candidate_lifecycle_slot_missing"

        family = _source_parent_family(
            Path(config_dir) / f"config_{source_run_id}.mk", stage)
        edges.append({
            "edge_index": index,
            "output_index": index,
            "batch_slot_index": index,
            "stage": stage,
            "clone_from_stage": clone_from_stage,
            "source_run_id": int(source_run_id),
            "target_run_id": int(target_run_id),
            "mapping_kind": mapping_kind,
            "source_candidate_id": source_candidate_id,
            "target_candidate_id": target_candidate_id,
            "replaced_target_candidate_id": replaced_candidate_id,
            "parent_family": family,
            "family_status": "resolved" if family is not None else "not_available",
            "lineage_event_id": lineage_event_id,
            "candidate_identity_status": identity_status or "not_available",
            "campaign_id": lifecycle.get("campaign_id") if lifecycle else None,
        })
    return edges


def _stage_provenance_payload(
    *,
    stage: str,
    params: List[Dict[str, float]],
    origins: List[str],
    edges: List[Dict[str, Any]],
    proposal_conditionings: List[Dict[str, Any]],
    params_file: Path,
    params_sha256: str,
    conditioned_families: Optional[List[Any]] = None,
    llm_enabled: bool = True,
) -> Dict[str, Any]:
    """Bind each generated row to the physical run slot it will mutate."""
    from candidate_tracking import ALLOWED_ORIGINS

    if not (len(params) == len(origins) == len(edges)
            == len(proposal_conditionings)):
        raise RuntimeError(
            "stage provenance must align one-to-one with params and clone edges: "
            f"params={len(params)}, origins={len(origins)}, edges={len(edges)}, "
            f"conditionings={len(proposal_conditionings)}")
    if conditioned_families is not None and len(conditioned_families) != len(params):
        raise RuntimeError(
            "source-conditioned family count does not match generated params")

    slots = []
    for index, (origin, edge, proposal) in enumerate(zip(
            origins, edges, proposal_conditionings)):
        if origin not in ALLOWED_ORIGINS:
            raise RuntimeError(f"unsupported stage candidate origin: {origin!r}")
        source_run_id = edge.get("source_run_id")
        target_run_id = edge.get("target_run_id")
        parent_family = edge.get("parent_family")
        if source_run_id is None or target_run_id is None:
            raise RuntimeError(f"stage provenance slot {index} has no clone endpoints")
        if not isinstance(parent_family, str) or not parent_family:
            raise RuntimeError(
                f"stage provenance slot {index} has no resolved parent_family")
        actual = _proposal_conditioning(edge)
        mismatches = [
            name for name in _CONDITIONING_FIELDS
            if proposal.get(name) != actual.get(name)
        ]
        if mismatches:
            raise RuntimeError(
                f"stage proposal/execution edge mismatch at slot {index}: "
                f"{','.join(mismatches)}")
        if conditioned_families is not None:
            conditioned = conditioned_families[index]
            if str(conditioned or "") != parent_family:
                raise RuntimeError(
                    f"source-conditioned family mismatch at slot {index}: "
                    f"{conditioned!r} != {parent_family!r}")
        slots.append({
            "slot_index": index,
            "origin": origin,
            "source_run_id": int(source_run_id),
            "target_run_id": int(target_run_id),
            "mapping_kind": edge.get("mapping_kind", "clone"),
            "parent_family": parent_family,
            "lineage_event_id": edge.get("lineage_event_id"),
            "source_candidate_id": edge.get("source_candidate_id"),
            "target_candidate_id": edge.get("target_candidate_id"),
            "replaced_target_candidate_id": edge.get(
                "replaced_target_candidate_id"),
            "candidate_identity_status": edge.get("candidate_identity_status"),
            **{
                f"proposal_conditioned_{name}": proposal.get(name)
                for name in _CONDITIONING_FIELDS
            },
            **{
                f"actual_{name}": actual.get(name)
                for name in _CONDITIONING_FIELDS
            },
        })

    campaign_ids = {
        str(edge.get("campaign_id")) for edge in edges if edge.get("campaign_id")
    }
    if len(campaign_ids) > 1:
        raise RuntimeError("stage provenance clone edges span multiple campaigns")
    raw_iteration = os.environ.get("DRP_ITER", "").strip()
    iteration = int(raw_iteration) if raw_iteration.isdigit() else None
    return {
        "schema_version": 1,
        "campaign_id": next(iter(campaign_ids), None),
        "iteration": iteration,
        "stage": stage,
        "params_file": params_file.name,
        "params_sha256": params_sha256,
        "llm_enabled": bool(llm_enabled),
        "count": len(slots),
        "slots": slots,
    }


def _focus_modes_to_origins(modes: List[Any]) -> List[str]:
    mapping = {
        "agent2": "focus_agent2",
        "novelty_fallback": "focus_novelty",
    }
    try:
        return [mapping[mode] for mode in modes]
    except KeyError as exc:
        raise RuntimeError(
            f"unsupported source-conditioned routing mode: {exc.args[0]!r}") from exc


def _atomic_write_text(path: Path, content: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _prompt_edges_for_generated_slots(
    edges: Optional[List[Dict[str, Any]]],
    total_slots: int,
    first_slot: int,
    count: int,
) -> List[Dict[str, Any]]:
    """Map LLM output indices onto the batch slots they will actually occupy."""
    if not edges or count <= 0:
        return []
    result = []
    exact_execution_batch = len(edges) == total_slots
    for output_index, batch_slot in enumerate(range(first_slot, first_slot + count)):
        base = dict(edges[batch_slot % len(edges)])
        base["execution_edge_index"] = base.get("edge_index")
        base["edge_index"] = output_index
        base["output_index"] = output_index
        base["batch_slot_index"] = batch_slot
        base["mapping_scope"] = (
            "final_execution_batch" if exact_execution_batch
            else "candidate_pool_conditioning"
        )
        result.append(base)
    return result


_CONDITIONING_FIELDS = (
    "source_run_id",
    "target_run_id",
    "parent_family",
    "lineage_event_id",
    "source_candidate_id",
    "target_candidate_id",
    "replaced_target_candidate_id",
)


def _proposal_conditioning(edge: Mapping[str, Any]) -> Dict[str, Any]:
    return {name: edge.get(name) for name in _CONDITIONING_FIELDS}


def _conditioning_key(value: Mapping[str, Any]) -> Tuple[Any, ...]:
    return tuple(value.get(name) for name in (
        "lineage_event_id", "source_run_id", "target_run_id", "parent_family"))


def _edge_for_candidate_slot(
    edges: Optional[List[Dict[str, Any]]], slot_index: int
) -> Dict[str, Any]:
    if not edges:
        raise RuntimeError("stage candidate has no source-target conditioning edges")
    return _proposal_conditioning(edges[int(slot_index) % len(edges)])


def _select_conditioned_indices(
    preferred_indices: List[int],
    candidate_conditionings: List[Dict[str, Any]],
    execution_edges: List[Dict[str, Any]],
    quality: List[float],
) -> List[int]:
    """Select one scored candidate per immutable execution edge, in edge order."""
    if len(candidate_conditionings) != len(quality):
        raise RuntimeError("conditioned selection quality/provenance length mismatch")
    preference = {
        int(index): rank for rank, index in enumerate(preferred_indices)
        if 0 <= int(index) < len(candidate_conditionings)
    }
    used = set()
    selected = []
    for output_index, edge in enumerate(execution_edges):
        expected = _conditioning_key(_proposal_conditioning(edge))
        eligible = [
            index for index, conditioning in enumerate(candidate_conditionings)
            if index not in used and _conditioning_key(conditioning) == expected
        ]
        if not eligible:
            raise RuntimeError(
                f"no scored candidate remains for execution edge {output_index} "
                f"{expected}")
        chosen = min(eligible, key=lambda index: (
            0 if index in preference else 1,
            preference.get(index, len(candidate_conditionings)),
            -float(quality[index]),
            index,
        ))
        selected.append(chosen)
        used.add(chosen)
    return selected


def _enforce_scored_cts_selection_quotas(
    initial_indices: List[int],
    candidates: List[Dict[str, float]],
    quality: List[float],
    n_points: int,
    kept: List[Dict[str, float]],
    policy: Optional[Mapping[str, Any]],
) -> List[int]:
    """Keep CTS quotas using only candidates that were already GPR-scored."""
    if not policy or n_points <= 0:
        return initial_indices[:n_points]
    final_size = len(kept) + n_points
    required_local = int(round(
        final_size * float(policy.get("cts_local_window_fraction", 0.0))))
    size_window = policy.get("cts_cluster_size_window", [18, 20])
    diameter_window = policy.get("cts_cluster_diameter_window", [90, 94])

    def is_local(row):
        try:
            size = float(row.get("CTS_CLUSTER_SIZE"))
            diameter = float(row.get("CTS_CLUSTER_DIAMETER"))
            return (float(size_window[0]) <= size <= float(size_window[1])
                    and float(diameter_window[0]) <= diameter
                    <= float(diameter_window[1]))
        except (TypeError, ValueError, IndexError):
            return False

    local_count = sum(is_local(row) for row in kept)
    selected: List[int] = []
    remaining = set(range(len(candidates)))

    # Satisfy both deficits first, choosing the highest-quality scored candidate
    # whenever several points cover the same number of missing roles.
    while len(selected) < n_points and local_count < required_local:
        ranked = []
        for index in remaining:
            covers_local = local_count < required_local and is_local(candidates[index])
            coverage = int(covers_local)
            if coverage:
                score = float(quality[index]) if index < len(quality) else float("-inf")
                ranked.append((coverage, score, -index, index))
        if not ranked:
            break
        index = max(ranked)[-1]
        selected.append(index)
        remaining.remove(index)
        local_count += int(is_local(candidates[index]))

    # Preserve Agent2's diversity/quality ordering for every non-quota slot.
    for index in initial_indices:
        index = int(index)
        if index in remaining and len(selected) < n_points:
            selected.append(index)
            remaining.remove(index)
    for index in sorted(
            remaining,
            key=lambda item: (
                float(quality[item]) if item < len(quality) else float("-inf"),
                -item),
            reverse=True):
        if len(selected) >= n_points:
            break
        selected.append(index)
    return selected[:n_points]


def generate_source_conditioned_routing(
    *,
    config: dict,
    objective: str,
    platform: str,
    design: str,
    work_dir: Path,
    config_dir: Path,
    source_run_ids: List[int],
    routing_history: List[Dict],
    constraints: Dict[str, dict],
    seed,
    agentic_enabled: bool = True,
) -> Tuple[List[Dict[str, float]], Dict]:
    """Select routing knobs in the exact order of the actual DRP clone sources."""
    from routing_focus import deterministic_novelty_for_sources, propose_for_sources
    from search_policy import load_optimization_state, policy_for_context
    from lineage import CONFIG_PARAM_NAMES, config_snapshot

    if work_dir is None:
        raise RuntimeError("routing-focus source conditioning requires --work-dir")
    state_path = (work_dir / "designs" / platform / design
                  / "optimization_state.json")
    policy = policy_for_context(config, objective, platform, design)
    source_params = []
    for source_id in source_run_ids:
        snapshot = config_snapshot(config_dir / f"config_{source_id}.mk")
        params = dict(snapshot.get("params") or {})
        context = snapshot.get("routing_context")
        if isinstance(context, dict):
            params["_FLOORPLAN_CONTEXT"] = dict(context)
        sdc = snapshot.get("effective_sdc") or {}
        sdc_identity = sdc.get("recipe_sha256", sdc.get("sha256"))
        if sdc_identity:
            params["_SDC_RECIPE_SHA256"] = str(sdc_identity)
        source_params.append(params)
    required = set(CONFIG_PARAM_NAMES) | {"clk_period"}
    incomplete = {
        source_id: sorted(required - set(params))
        for source_id, params in zip(source_run_ids, source_params)
        if required - set(params)
    }
    if incomplete:
        raise RuntimeError(
            f"cannot resolve complete effective params for source runs {incomplete}")

    optimization_state = load_optimization_state(state_path)
    radius = float((policy or {}).get("routing_jitter_fraction", 0.08))
    if (not isinstance(optimization_state, dict) or policy is None
            or optimization_state.get("mode") != "ROUTING_FOCUS"):
        proposals, meta = deterministic_novelty_for_sources(
            source_params, constraints, seed, radius_fraction=radius)
        meta["fallback_cause"] = "routing_focus_state_or_policy_unavailable"
        return proposals, meta

    try:
        proposals, meta = propose_for_sources(
            source_params, routing_history, constraints, optimization_state, policy,
            seed, agentic_enabled=agentic_enabled,
        )
    except Exception as exc:
        proposals, meta = deterministic_novelty_for_sources(
            source_params, constraints, seed, radius_fraction=radius)
        meta["fallback_cause"] = f"conditional_model_failed:{exc}"
    if len(proposals) != len(source_run_ids):
        raise RuntimeError(
            f"conditional routing returned {len(proposals)} rows, "
            f"expected {len(source_run_ids)}")
    return proposals, meta


def generate_stage_params(
    stage: str,
    config: dict,
    platform: str,
    design: str,
    objective: str,
    num_kill: int,
    sorted_metrics: List[Dict],
    source_run_ids: List[int],
    target_run_ids: List[int],
    config_dir: Path,
    observed_params: Optional[List[Dict]] = None,
    observed_objectives: Optional[List[float]] = None,
    acquisition: str = "ei",
    explore_frac: Optional[float] = None,
    prompt_evidence_context: Optional[Mapping[str, Any]] = None,
    source_target_edges: Optional[List[Dict[str, Any]]] = None,
    stage_shape_seed: Any = None,
    return_origins: bool = False,
    return_provenance: bool = False,
    llm_enabled: bool = True,
    usage_context: Optional[Mapping[str, Any]] = None,
) -> Any:
    """
    Generate parameters for every execution slot at a specific stage.

    acquisition: ranks the Bayesian-fill suggestions (ei/ucb/pi — was hard-coded EI).
    explore_frac: when set, that fraction of the non-LLM fill is LHS exploration and
    the rest Bayesian exploitation (was: all-Bayesian when history exists — the
    agentic model config's explore_frac was a no-op on this intra path).

    Args:
        stage: 'cts' or 'routing'
        config: Full DRP config dict.
        platform, design: Platform and design names.
        objective: Optimization objective ('wl', 'ecp', 'combo').
        num_kill: Number of stage execution slots (legacy argument name).
        sorted_metrics: All run metrics sorted by objective (ascending).
        source_run_ids: IDs of source runs (top M, being copied).
        target_run_ids: IDs of target runs (bottom M, being replaced).
        config_dir: Directory containing config_i.mk files.
        observed_params: Historical parameter observations for Bayesian opt.
        observed_objectives: Historical objective values for Bayesian opt.
        prompt_evidence_context: Structured evidence from build_prompt_evidence.
        source_target_edges: Positional candidate/clone lineage for this batch.
        stage_shape_seed: Deterministic seed for pre-scoring CTS shaping.
        return_origins: Return ``(params, origins)`` for provenance-aware callers.
        return_provenance: Return ``(params, origins, conditionings)``.

    Returns:
        List of num_kill parameter dicts, one per run slot.
    """
    design_cfg = get_design_config(config, platform, design)
    param_constraints = get_param_constraints(config, stage, design_cfg)
    param_names = list(param_constraints.keys())
    stage_usage_context = dict(usage_context or {})
    stage_usage_context.setdefault("scope", "intra_iteration")
    stage_usage_context.setdefault("stage", stage)
    stage_usage_context.setdefault("agent", "agent2")
    stage_usage_context.setdefault("operation", "direct_parameter_proposal")
    try:
        current_iteration = int(os.environ.get("DRP_ITER", "").strip())
    except (TypeError, ValueError):
        current_iteration = None
    if current_iteration is not None:
        stage_usage_context.setdefault("iteration", current_iteration)
        stage_usage_context.setdefault("source_iteration", current_iteration)
        stage_usage_context.setdefault("target_iteration", current_iteration)

    # Determine number of perturbation vs LLM+Bayesian params
    n_perturb = max(1, int(0.2 * num_kill))
    n_llm_bayesian = num_kill - n_perturb

    if source_target_edges is None:
        source_target_edges = build_stage_source_target_edges(
            stage, source_run_ids, target_run_ids, config_dir)
    llm_edges = _prompt_edges_for_generated_slots(
        source_target_edges, num_kill, n_perturb, n_llm_bayesian)

    # Candidate positions are immutable execution-edge conditioning slots. A malformed
    # LLM row leaves its own position empty; Bayesian/LHS fill that same position
    # instead of shifting every later proposal onto the wrong parent family.
    all_params: List[Optional[Dict[str, float]]] = [None] * num_kill
    all_origins: List[Optional[str]] = [None] * num_kill
    all_conditionings = [
        _edge_for_candidate_slot(source_target_edges, index)
        for index in range(num_kill)
    ]

    # --- Part 1: Perturbation-based params (20%) ---
    for i in range(n_perturb):
        src_id = source_run_ids[i % len(source_run_ids)]
        src_config = config_dir / f"config_{src_id}.mk"
        base_params = extract_current_params(src_config, param_names)

        # Fill missing params with midpoint
        for name in param_names:
            if name not in base_params:
                lo, hi = param_constraints[name]["range"]
                base_params[name] = (lo + hi) / 2

        perturbed = perturb_params(
            base_params, param_constraints,
            perturbation_factor=0.15,
            seed=np.random.randint(0, 10000),
        )
        all_params[i] = perturbed
        all_origins[i] = "exploit"

    # --- Part 2: LLM + Bayesian params (80%) ---
    llm_params = None

    # Prepare source run info for prompt
    source_runs_info = []
    for sid in source_run_ids:
        run_metrics = next(
            (m for m in sorted_metrics if m["run_id"] == sid),
            {"run_id": sid},
        )
        src_config = config_dir / f"config_{sid}.mk"
        current_params = extract_current_params(src_config, param_names)
        run_metrics_copy = dict(run_metrics)
        run_metrics_copy[f"{stage}_params"] = current_params
        matching_edge = next(
            (edge for edge in source_target_edges
             if edge.get("source_run_id") == sid), None)
        if matching_edge is not None:
            run_metrics_copy["candidate_id"] = matching_edge.get(
                "source_candidate_id")
            run_metrics_copy["parent_family"] = matching_edge.get("parent_family")
        source_runs_info.append(run_metrics_copy)

    evidence = dict(prompt_evidence_context or {})
    prompt_context = {
        name: evidence.get(name)
        for name in _PROMPT_EVIDENCE_FIELDS
        if name in evidence
    }
    prompt_context.update(build_shared_prompt_context(
        config, platform, design, objective, evidence))
    # Historical edges in the general evidence are useful for analysis, but this
    # stage prompt needs the positional current-batch map to bind output[i].
    prompt_context["source_target_edges"] = llm_edges

    # Build prompt
    if stage == "cts":
        prompt = build_cts_prompt(
            platform=platform,
            design=design,
            objective=objective,
            num_kill=num_kill,
            num_params=n_llm_bayesian,
            metrics=sorted_metrics,
            source_runs=source_runs_info,
            param_constraints=param_constraints,
            **prompt_context,
        )
    elif stage == "routing":
        prompt = build_routing_prompt(
            platform=platform,
            design=design,
            objective=objective,
            num_kill=num_kill,
            num_params=n_llm_bayesian,
            metrics=sorted_metrics,
            source_runs=source_runs_info,
            param_constraints=param_constraints,
            **prompt_context,
        )
    else:
        prompt = None

    # Call LLM
    if llm_enabled and prompt:
        response = call_llm(
            prompt, config, usage_context=stage_usage_context)
        llm_params = parse_llm_json(response)
    elif prompt:
        print(f"[no-llm][intra:{stage}] direct parameter proposals disabled; "
              "using Bayesian/LHS fill.", file=sys.stderr)

    # Validate and clip LLM params. Guard against malformed responses (a flat list
    # of numbers, or a bare dict) so one bad LLM reply degrades to Bayesian/LHS fill
    # instead of crashing the run (clip_params expects a dict).
    if isinstance(llm_params, dict):
        llm_params = [llm_params]
    if llm_params:
        for output_index, p in enumerate(llm_params[:n_llm_bayesian]):
            if not isinstance(p, dict):
                print(f"[agent][WARN] skipping malformed LLM param entry "
                      f"(expected dict, got {type(p).__name__})", file=sys.stderr)
                continue
            clipped = clip_params(p, param_constraints)
            if output_index >= len(llm_edges):
                raise RuntimeError("LLM stage output has no conditioned clone edge")
            position = n_perturb + output_index
            all_params[position] = clipped
            all_origins[position] = "llm"
            all_conditionings[position] = _proposal_conditioning(
                llm_edges[output_index])

    # If LLM didn't return enough, fill with Bayesian and/or LHS. explore_frac (agentic
    # model config) splits the fill: that fraction explores via LHS, the rest exploits
    # via the acquisition-ranked Bayesian suggestions.
    remaining_positions = [
        index for index, params in enumerate(all_params) if params is None
    ]
    remaining = len(remaining_positions)
    if remaining > 0:
        have_obs = (observed_params is not None and observed_objectives is not None
                    and len(observed_params) >= 3)
        n_lhs = remaining if not have_obs else (
            int(round(remaining * explore_frac)) if explore_frac is not None else 0)
        n_bayes = remaining - n_lhs
        if n_bayes > 0 and have_obs:
            X_obs = params_to_array(observed_params, param_names)
            y_obs = np.array(observed_objectives)
            suggestions = bayesian_suggest(
                X_obs, y_obs, param_constraints,
                n_suggestions=n_bayes,
                seed=np.random.randint(0, 10000),
                acquisition=acquisition,
            )
            for position, suggestion in zip(remaining_positions, suggestions):
                all_params[position] = suggestion
                all_origins[position] = "bayes"
            remaining_positions = [
                index for index, params in enumerate(all_params) if params is None
            ]
        n_lhs = len(remaining_positions)
        if n_lhs > 0:
            lhs = latin_hypercube_sample(
                n_lhs, param_constraints,
                seed=np.random.randint(0, 10000),
            )
            for position, suggestion in zip(remaining_positions, lhs):
                all_params[position] = suggestion
                all_origins[position] = "lhs"

    if any(params is None for params in all_params) or any(
            origin is None for origin in all_origins):
        raise RuntimeError("stage generator left an execution-conditioned slot empty")
    complete_params = [dict(params) for params in all_params if params is not None]
    complete_origins = [str(origin) for origin in all_origins if origin is not None]

    result = _dedup_stage_params(
        complete_params, source_run_ids, config_dir,
        param_names, param_constraints)
    # CTS policy shaping is part of the candidate definition.  Doing it here means
    # agentic callers receive already-shaped points and score those exact points;
    # main() must not rewrite the selected batch a second time.
    from search_policy import shape_stage_params
    shape_seed = stage_shape_seed
    if shape_seed is None:
        shape_seed = f"{os.environ.get('DRP_SEED', '')}:{os.environ.get('DRP_ITER', '')}"
    result, stage_plan = shape_stage_params(
        result,
        stage=stage,
        objective=objective,
        platform=platform,
        design=design,
        constraints=param_constraints,
        seed=shape_seed,
        policy_config=config,
    )
    if stage_plan.get("enabled"):
        print(f"[search-policy][{stage}] pre-score directed counts="
              f"{stage_plan.get('counts', {})}", file=sys.stderr)
    origins = complete_origins[:len(result)]
    conditionings = all_conditionings[:len(result)]
    if len(origins) != len(result) or len(conditionings) != len(result):
        raise RuntimeError(
            "stage provenance does not match params count: "
            f"params={len(result)}, origins={len(origins)}, "
            f"conditionings={len(conditionings)}")
    if return_provenance:
        return result, origins, conditionings
    return (result, origins) if return_origins else result


def _dedup_stage_params(all_params: List[Dict[str, float]],
                        source_run_ids: List[int], config_dir: Path,
                        param_names: List[str],
                        param_constraints: Dict[str, dict]) -> List[Dict[str, float]]:
    """Deduplicate generated stage params. Slot i is applied to victim i, whose
    upstream config is CLONED from source_run_ids[i % len]; if the new stage params
    equal (a) that source's current stage params or (b) another already-generated
    victim's params, the run is byte-identical to an existing one and — the flow being
    deterministic — burns a slot for zero information. On collision re-perturb up to 3
    times, then accept (tiny parameter spaces would otherwise loop forever)."""
    def sig(p):
        return tuple((n, round(float(p.get(n, 0)), 4)) for n in param_names)

    src_sig = {}
    for sid in set(source_run_ids or []):
        sp = extract_current_params(config_dir / f"config_{sid}.mk", param_names)
        if len(sp) == len(param_names):
            src_sig[sid] = sig(sp)

    seen = set()
    for i, p in enumerate(all_params):
        src = source_run_ids[i % len(source_run_ids)] if source_run_ids else None
        taken = set(seen)
        if src in src_sig:
            taken.add(src_sig[src])
        s = sig(p)
        retries = 0
        while s in taken and retries < 3:
            # Explicit derived seed: perturb_params(seed=None) uses OS entropy and
            # would break campaign reproducibility.
            p = perturb_params(p, param_constraints, perturbation_factor=0.15,
                               seed=np.random.randint(0, 10000))
            s = sig(p)
            retries += 1
        if retries:
            status = "re-perturbed" if s not in taken else "still duplicate; accepted"
            print(f"[agent][dedup] slot {i}: colliding stage params {status} "
                  f"({retries} tries).", file=sys.stderr)
        all_params[i] = p
        seen.add(s)
    return all_params


def _paired_delta_objective(entry: Dict, objective: str,
                            wl_base: float, ecp_base: float,
                            power_budget: Optional[float] = None,
                            power_base: Optional[float] = None) -> Optional[float]:
    """Objective change caused by this stage mutation (lower is better)."""
    if (not entry.get("trusted")
            or entry.get("mapping_kind") == "self"):
        return None
    if objective == "TNS_EVAL":
        source_metrics = entry.get("source_metrics", {})
        child_metrics = entry.get("child_metrics", entry.get("metrics", {}))
        # Native-clock TNS is not comparable across configs or with CP_0. With a
        # constrained objective, only learn routing/CTS deltas whose child is known
        # power-feasible under exactly the same gate used by the final optimizer.
        if (source_metrics.get("tns_source") != "cp0_eval"
                or child_metrics.get("tns_source") != "cp0_eval"):
            return None
        if power_budget is not None:
            if power_base is None or power_base <= 0:
                return None
            child_power = child_metrics.get("power")
            try:
                child_power = float(child_power)
            except (TypeError, ValueError):
                return None
            if child_power > (1.0 + power_budget) * power_base:
                return None
        value = entry.get("delta_abs_tns")
    elif objective == "wl":
        value = entry.get("delta_wl")
    elif objective == "ecp":
        value = entry.get("delta_ecp")
    else:
        dwl, decp = entry.get("delta_wl"), entry.get("delta_ecp")
        if dwl is None or decp is None:
            return None
        value = 0.5 * (float(dwl) / wl_base) + 0.5 * (float(decp) / ecp_base)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _paired_agentic_history(stage_history: List[Dict], objective: str,
                            wl_base: float, ecp_base: float,
                            power_base: Optional[float],
                            power_budget: Optional[float]) -> Tuple[List[Dict], float]:
    """Encode signed paired deltas as ordinary positive minimization metrics.

    optimize_agentic's inspection API consumes metrics rather than an external y
    vector. Adding one common offset preserves every ordering and acquisition while
    allowing improvements (negative deltas) to pass through that unchanged API.
    All lineage/source/effective-config fields stay attached as agentic context.
    """
    paired = []
    for entry in stage_history:
        delta = _paired_delta_objective(
            entry, objective, wl_base, ecp_base, power_budget, power_base)
        if delta is not None:
            paired.append((entry, delta))
    if len(paired) < 3:
        return [], 0.0
    offset = max(1.0, 1.0 - min(delta for _, delta in paired))
    result = []
    for entry, delta in paired:
        shifted = delta + offset
        if objective == "wl":
            metrics = {"wl": shifted, "ecp": None, "tns": None, "power": None}
        elif objective == "ecp":
            metrics = {"wl": None, "ecp": shifted, "tns": None, "power": None}
        elif objective == "TNS_EVAL":
            metrics = {
                "wl": None, "ecp": None, "tns": -shifted,
                "tns_source": "cp0_eval", "power": power_base or 0.0,
            }
        else:
            metrics = {
                "wl": shifted * wl_base,
                "ecp": shifted * ecp_base,
                "tns": None,
                "power": None,
            }
        row = dict(entry)
        row["metrics"] = metrics
        row["paired_objective"] = delta
        row["paired_objective_shift"] = offset
        result.append(row)
    return result, offset


def generate_stage_params_agentic(
    stage: str,
    config: dict,
    platform: str,
    design: str,
    objective: str,
    num_kill: int,
    sorted_metrics: List[Dict],
    source_run_ids: List[int],
    target_run_ids: List[int],
    config_dir: Path,
    stage_history: List[Dict],
    stage_param_names: List[str],
    param_constraints: Dict[str, dict],
    wl_base: float,
    ecp_base: float,
    prompt_evidence_context: Optional[Mapping[str, Any]] = None,
    source_target_edges: Optional[List[Dict[str, Any]]] = None,
    stage_shape_seed: Any = None,
    return_origins: bool = False,
    return_provenance: bool = False,
    llm_enabled: bool = True,
    usage_context: Optional[Mapping[str, Any]] = None,
) -> Any:
    """Intra-iteration DRP-stage parameter generation via the SAME agentic framework
    as inter-iteration (optimize_agentic): Agent1 (Inspection -> Model ReAct GPR loop)
    + Agent2 (hybrid candidate pool -> GPR-score -> Selection LLM -> agglomerative
    select). No Agent3 (TextGrad critic) here, by design.

    stage_history contains lineage-resolved source/child metrics, effective config,
    parent family, and the stage-only params. Paired child-minus-source targets are
    preferred; absolute stage metrics are used only when fewer than three trusted
    pairs exist. Falls back to the plain generator on any failure / sparse history.
    """
    import numpy as np
    import optimize_agentic as oa  # lazy: heavy deps + avoids import cycles
    from common import _power_base
    # Make oa._objective_value power-budget-aware for TNS_EVAL on the intra path too.
    oa._POWER_BUDGET = config.get("power_budget")
    oa._POWER_BASE = _power_base(platform, design)
    from modelfuncs import create_model, predict_with_model, latin_hypercube_sample
    try:
        from agglomfuncs import create_quality_scores, select_points
        have_agglom = True
    except Exception:
        have_agglom = False

    llm_cfg = config.get("llm")
    stage_usage_context = dict(usage_context or {})
    stage_usage_context.setdefault("scope", "intra_iteration")
    stage_usage_context.setdefault("stage", stage)
    try:
        current_iteration = int(os.environ.get("DRP_ITER", "").strip())
    except (TypeError, ValueError):
        current_iteration = None
    if current_iteration is not None:
        stage_usage_context.setdefault("iteration", current_iteration)
        stage_usage_context.setdefault("source_iteration", current_iteration)
        stage_usage_context.setdefault("target_iteration", current_iteration)
    ag = config.get("agentic", {})
    max_iters = int(ag.get("react_max_iters", 2))
    pool_mult = int(ag.get("candidate_pool_mult", 2))
    lhs_mult = int(ag.get("lhs_pool_mult", 8))
    w_wl = w_ecp = 0.5

    paired_history, paired_offset = _paired_agentic_history(
        stage_history, objective, wl_base, ecp_base, oa._POWER_BASE,
        config.get("power_budget"))
    training_history = paired_history or stage_history
    history_mode = "paired_delta" if paired_history else "absolute_stage_metric"

    def _result(rows, origins, conditionings):
        rows, origins, conditionings = (
            list(rows), list(origins), list(conditionings))
        if not (len(rows) == len(origins) == len(conditionings)):
            raise RuntimeError(
                "agentic stage provenance does not match params count: "
                f"params={len(rows)}, origins={len(origins)}, "
                f"conditionings={len(conditionings)}")
        if return_provenance:
            return rows, origins, conditionings
        return (rows, origins) if return_origins else rows

    # Surrogate training data is stage-local. For paired mode, synthetic metrics
    # encode delta+constant so optimize_agentic's unchanged inspection API sees the
    # same lower-is-better ordering while retaining lineage context on every row.
    penalty = oa._penalty(objective, training_history,
                          wl_base, ecp_base, w_wl, w_ecp)
    X_hist, y_hist = [], []
    usable_history = []
    for h in training_history:
        if not h.get("params"):
            continue
        obj = oa._objective_value(h["metrics"], objective, wl_base, ecp_base, w_wl, w_ecp)
        X_hist.append(oa._vectorize(h["params"], stage_param_names, param_constraints))
        y_hist.append(obj if obj is not None else penalty)
        usable_history.append(h)
    X_hist = np.array(X_hist, dtype=float)
    y_hist = np.array(y_hist, dtype=float)

    def _plain():
        return generate_stage_params(
            stage=stage, config=config, platform=platform, design=design,
            objective=objective, num_kill=num_kill, sorted_metrics=sorted_metrics,
            source_run_ids=source_run_ids, target_run_ids=target_run_ids,
            config_dir=config_dir,
            observed_params=[h["params"] for h in usable_history] or None,
            observed_objectives=y_hist.tolist() or None,
            prompt_evidence_context=prompt_evidence_context,
            source_target_edges=source_target_edges,
            stage_shape_seed=stage_shape_seed,
            return_origins=return_origins,
            return_provenance=return_provenance,
            llm_enabled=llm_enabled,
            usage_context=stage_usage_context,
        )

    if len(y_hist) < 3:
        return _plain()

    # ---- Agent1: Inspection -> Model (ReAct GPR loop) ----
    print(f"\n=== [intra:{stage}] Agent1: Inspection -> Model(+ReAct GPR) ===")
    summary = {
        "stage": stage, "objective": objective, "n_samples": int(len(y_hist)),
        "best_objective": round(float(np.min(y_hist)), 4),
        "worst_objective": round(float(np.max(y_hist)), 4),
        "history_mode": history_mode,
        "paired_delta_offset": paired_offset if paired_history else None,
        "n_parent_families": len({h.get("parent_family") for h in usable_history
                                   if h.get("parent_family")}),
        "param_names": stage_param_names,
    }

    def inspect_runner(insp_cfg):
        return oa.run_inspection(usable_history, stage_param_names, param_constraints,
                                 objective, wl_base, ecp_base, w_wl, w_ecp, insp_cfg)

    try:
        agent1_cfg, inspection = oa.agent1_stages(
            llm_cfg, summary, X_hist, y_hist, oa.DEFAULT_INSTRUCTIONS,
            max_iters, inspect_runner, llm_enabled=llm_enabled,
            usage_context=stage_usage_context)
    except LLMUsageError:
        raise
    except Exception as e:
        print(f"[intra:{stage}][WARN] Agent1 failed ({e}); default model cfg.", file=sys.stderr)
        agent1_cfg, inspection = {"model": {}}, None
    model_cfg = agent1_cfg.get("model", {})
    feature_weights = inspection.get("feature_weights") if inspection else None

    # ---- Agent2: hybrid pool -> GPR-score -> Selection LLM -> agglomerative select ----
    print(f"=== [intra:{stage}] Agent2: Param Set Generator (generate + selection) ===")
    pool_size = max(num_kill, num_kill * max(1, pool_mult))
    acquisition = model_cfg.get("acquisition", "ei")
    pool, pool_origins, pool_conditionings = generate_stage_params(
        stage=stage, config=config, platform=platform, design=design,
        objective=objective, num_kill=pool_size, sorted_metrics=sorted_metrics,
        source_run_ids=source_run_ids, target_run_ids=target_run_ids,
        config_dir=config_dir,
        observed_params=[h["params"] for h in usable_history] or None,
        observed_objectives=y_hist.tolist() or None,
        acquisition=acquisition,                       # Agent1's strategy knobs now
        explore_frac=model_cfg.get("explore_frac"),    # actually reach this path
        prompt_evidence_context=prompt_evidence_context,
        source_target_edges=source_target_edges,
        stage_shape_seed=stage_shape_seed,
        return_provenance=True,
        llm_enabled=llm_enabled,
        usage_context=stage_usage_context,
    )
    if not have_agglom:
        return _plain()

    n_keep = min(1, num_kill)
    rest = list(pool[n_keep:])
    rest_origins = list(pool_origins[n_keep:])
    rest_conditionings = list(pool_conditionings[n_keep:])
    try:
        # Derived seed: seed=None would draw from OS entropy, bypassing DRP_SEED.
        lhs_rows = latin_hypercube_sample(
            num_kill * max(1, lhs_mult), param_constraints,
            seed=np.random.randint(0, 10000))
        rest += lhs_rows
        rest_origins += ["lhs"] * len(lhs_rows)
        first_lhs_slot = n_keep + len(rest) - len(lhs_rows)
        rest_conditionings += [
            _edge_for_candidate_slot(source_target_edges, first_lhs_slot + offset)
            for offset in range(len(lhs_rows))
        ]
    except Exception as e:
        print(f"[intra:{stage}][WARN] LHS sampling failed ({e}); pool only.", file=sys.stderr)
    # LHS points joined the pool after generate_stage_params shaped its own rows.
    # Shape the complete hybrid pool now, before X_pool/GPR construction, and use
    # these same dictionaries all the way through selection and execution.
    from search_policy import shape_stage_params
    combined, hybrid_shape_plan = shape_stage_params(
        list(pool[:n_keep]) + rest,
        stage=stage,
        objective=objective,
        platform=platform,
        design=design,
        constraints=param_constraints,
        seed=stage_shape_seed,
        policy_config=config,
    )
    kept = combined[:n_keep]
    rest = combined[n_keep:]
    kept_origins = pool_origins[:n_keep]
    kept_conditionings = pool_conditionings[:n_keep]
    if hybrid_shape_plan.get("enabled"):
        print(f"[search-policy][{stage}] hybrid pool shaped before GPR: "
              f"{hybrid_shape_plan.get('counts', {})}", file=sys.stderr)
    need = num_kill - len(kept)
    if need <= 0 or not rest:
        return _result(
            pool[:num_kill], pool_origins[:num_kill],
            pool_conditionings[:num_kill])

    try:
        X_pool = np.array([oa._vectorize(p, stage_param_names, param_constraints)
                           for p in rest], dtype=float)
        gp = create_model(X_hist, y_hist,
                          kernel_type=model_cfg.get("kernel_type", "matern"),
                          preprocessing=model_cfg.get("preprocessing", "robust"),
                          feature_weights=feature_weights)
        mu, std = predict_with_model(gp, X_pool)
        mu = np.asarray(mu, dtype=float)
        std = np.asarray(std, dtype=float)
        # EXECUTE Agent1's acquisition (mirrors the inter-iteration fix: raw mu/std
        # ranking made ei/ucb/pi a no-op). Higher = better; std handled inside.
        from modelfuncs import create_acquisition_function
        acq_fn = create_acquisition_function(acquisition)
        acq_scores = np.asarray(acq_fn(mu, std, float(np.min(y_hist))), dtype=float)

        print(f"--- [intra:{stage}] Agent2 selection (LLM, informed by scores) ---")
        sel_cfg = oa._decide_selection(llm_cfg, oa.DEFAULT_INSTRUCTIONS, mu, std,
                                       y_hist, model_cfg, len(rest),
                                       llm_enabled=llm_enabled,
                                       usage_context=stage_usage_context)
        method = sel_cfg.get("method", "hybrid")
        print(f"[intra:{stage}] selection config: {json.dumps(sel_cfg)}")
        if method == "elitist":
            quality = acq_scores
            idx_list = np.argsort(-quality)[:min(need, len(rest))].astype(int).tolist()
        else:
            # uncertainty_bonus = explicit extra exploration pressure on top of the
            # acquisition (with model_uncertainties=None it would be a silent no-op).
            quality = create_quality_scores(
                X_pool, y_hist, acq_scores, model_uncertainties=std, minimize=False,
                uncertainty_weight=sel_cfg.get("uncertainty_bonus", 0.2))
            idx = select_points(
                X_pool, quality, method=method, n_points=min(need, len(rest)),
                config={"quality_weight": sel_cfg.get("quality_weight", 0.7),
                        "uncertainty_bonus": sel_cfg.get("uncertainty_bonus", 0.2)})
            idx_list = np.atleast_1d(idx).astype(int).tolist()

        # The final CTS allocation is selected from already-shaped, already-scored
        # candidates. This retains the directed quota without mutating output after
        # Agent2 has evaluated it.
        from search_policy import policy_for_context
        stage_policy = policy_for_context(config, objective, platform, design)
        if stage == "cts":
            idx_list = _enforce_scored_cts_selection_quotas(
                idx_list, rest, np.asarray(quality, dtype=float).tolist(),
                min(need, len(rest)), kept, stage_policy)
        if not source_target_edges or len(source_target_edges) != num_kill:
            raise RuntimeError(
                "agentic stage selection requires one execution edge per output slot")
        if n_keep and _conditioning_key(kept_conditionings[0]) != _conditioning_key(
                _proposal_conditioning(source_target_edges[0])):
            raise RuntimeError("fixed Agent2 candidate is conditioned to the wrong edge")
        chosen_indices = _select_conditioned_indices(
            idx_list,
            rest_conditionings,
            source_target_edges[n_keep:],
            np.asarray(quality, dtype=float).tolist(),
        )
        chosen = [rest[index] for index in chosen_indices]
        result = kept + chosen
        result_origins = kept_origins + [
            rest_origins[index] for index in chosen_indices]
        result_conditionings = kept_conditionings + [
            rest_conditionings[index] for index in chosen_indices]
        if len(result) != num_kill:
            raise RuntimeError(
                f"conditioned Agent2 selected {len(result)}/{num_kill} rows")
        if stage == "cts" and stage_policy:
            required_local = int(round(
                num_kill * float(stage_policy.get("cts_local_window_fraction", 0.0))))
            size_window = stage_policy.get("cts_cluster_size_window", [18, 20])
            diameter_window = stage_policy.get(
                "cts_cluster_diameter_window", [90, 94])
            local_count = sum(
                float(size_window[0]) <= float(row.get("CTS_CLUSTER_SIZE", -1))
                <= float(size_window[1])
                and float(diameter_window[0])
                <= float(row.get("CTS_CLUSTER_DIAMETER", -1))
                <= float(diameter_window[1])
                for row in result
            )
            if local_count < required_local:
                raise RuntimeError(
                    "conditioned Agent2 selection cannot satisfy CTS quotas; "
                    "falling back to the pre-shaped positional batch")
        print(f"[intra:{stage}] Agent2 '{method}' selection: {len(result)} runs "
              f"from hybrid pool of {len(kept) + len(rest)}")
        return _result(
            result, result_origins, result_conditionings)
    except LLMUsageError:
        raise
    except Exception as e:
        print(f"[intra:{stage}][WARN] scoring/selection failed ({e}); plain fallback.",
              file=sys.stderr)
        return _plain()


def main():
    parser = argparse.ArgumentParser(
        description="Generate stage-specific parameters for every DRP run slot."
    )
    parser.add_argument("--stage", choices=["cts", "routing"], required=True,
                        help="Stage to generate parameters for")
    parser.add_argument("--platform", required=True)
    parser.add_argument("--design", required=True)
    parser.add_argument("--objective", choices=["wl", "ecp", "combo", "TNS_EVAL"], required=True)
    parser.add_argument("--num-runs", type=int,
                        help="Number of run slots in the stage batch")
    parser.add_argument("--num-kill", type=int,
                        help="Deprecated alias for --num-runs")
    parser.add_argument("--metrics-file", type=Path, required=True,
                        help="JSON file with sorted run metrics")
    parser.add_argument("--source-runs", type=str, required=True,
                        help="Comma-separated source run IDs")
    parser.add_argument("--target-runs", type=str, required=True,
                        help="Comma-separated target run IDs")
    parser.add_argument("--config-dir", type=Path, required=True,
                        help="Directory with config_i.mk files")
    parser.add_argument("--drp-config", type=Path,
                        default=Path(__file__).parent / "drp_config.json")
    parser.add_argument("--work-dir", type=Path, default=None,
                        help="Work dir (for backup_dir cross-iteration Bayesian history)")
    parser.add_argument("--agentic", action="store_true",
                        help="Use the Agent1(ReAct inspection/model)+Agent2(generate+"
                             "selection) framework for stage-param generation (mirrors "
                             "inter-iteration optimize_agentic; no Agent3).")
    parser.add_argument("--no-llm", action="store_true",
                        help="Keep Agentic/GPR stage generation but disable every "
                             "external LLM request (requires --agentic)")
    parser.add_argument("--output", type=Path, required=True,
                        help="Output JSON file for generated parameters")
    parser.add_argument("--frozen-runs", default="",
                        help="Comma-separated run IDs whose current stage values are preserved")

    args = parser.parse_args()
    if args.no_llm and not args.agentic:
        parser.error("--no-llm requires --agentic")
    if args.no_llm:
        os.environ["DRP_NO_LLM"] = "1"

    # Reproducibility: derive this process's RNG seed from the campaign base seed +
    # (iteration, design, stage) so the scattered np.random.randint calls below are
    # deterministic. DRP_SEED unset/"none" -> nondeterministic (previous behaviour).
    from modelfuncs import seed_everything
    derived_seed = seed_everything(
        os.environ.get("DRP_SEED"), os.environ.get("DRP_ITER", ""),
        args.platform, args.design, "agent", args.stage)

    config = load_config(args.drp_config)
    source_run_ids = [int(x) for x in args.source_runs.split(",")]
    target_run_ids = [int(x) for x in args.target_runs.split(",")]
    num_runs = args.num_runs if args.num_runs is not None else args.num_kill
    if num_runs is None or num_runs <= 0:
        parser.error("one of --num-runs or --num-kill must be a positive integer")
    if len(source_run_ids) != num_runs or len(target_run_ids) != num_runs:
        parser.error(
            "--source-runs and --target-runs must each contain exactly "
            f"{num_runs} IDs")
    frozen_run_ids = {
        int(value) for value in args.frozen_runs.split(",") if value.strip()
    }

    with open(args.metrics_file) as f:
        sorted_metrics = json.load(f)

    # Build Bayesian observations for the stage-parameter generation. Without this
    # the Bayesian branch in generate_stage_params is dead code (observed_* default
    # to None) and generation is only LLM + perturbation + LHS.
    design_cfg = get_design_config(config, args.platform, args.design)
    stage_param_constraints = get_param_constraints(config, args.stage, design_cfg)
    stage_param_names = list(stage_param_constraints.keys())
    base = design_cfg.get("baseline", {}) if design_cfg else {}
    wl_base = base.get("wl_base", 1.0)
    ecp_base = base.get("ecp_base", 1.0)

    # Power-budget constraint for TNS_EVAL (default off): |TNS| + penalty if a run's
    # CP_0 power exceeds (1+budget)*baseline power. Same semantics as the optimizer.
    from common import tns_eval_obj, _power_base
    power_budget = config.get("power_budget")
    power_base_val = _power_base(args.platform, args.design)

    def _obj_from_metrics(m):
        wl, ecp = m.get("wl"), m.get("ecp")
        if args.objective == "wl":
            return wl
        if args.objective == "ecp":
            return ecp
        if args.objective == "TNS_EVAL":
            return tns_eval_obj(m, power_budget, power_base_val)
        if wl is not None and ecp is not None:
            return 0.5 * (wl / wl_base) + 0.5 * (ecp / ecp_base)
        return None

    # Cross-iteration history is stage-specific and lineage-resolved. Do not project
    # the global clean-only history onto CTS/routing: that loses DRP children and
    # attributes an absolute full-flow result to a stage mutation without its parent.
    observed_params, observed_objectives = [], []
    stage_history = []
    all_stage_history = []
    clean_prompt_history = []
    resolved_prompt_history = []
    routing_prompt_history = []
    history_mode = "none"
    if args.work_dir is not None and stage_param_names:
        try:
            from optimize import (  # lazy: avoids circular import
                load_resolved_history,
                load_stage_history,
            )
            hist = load_stage_history(
                args.work_dir / "backup_dir", args.platform, args.design,
                1000, args.stage)
            all_stage_history = list(hist)
            resolved_prompt_history = load_resolved_history(
                args.work_dir / "backup_dir", args.platform, args.design, 1000)
            clean_prompt_history = [
                row for row in resolved_prompt_history
                if row.get("lineage_kind") == "clean"
            ]
            routing_prompt_history = (
                list(hist) if args.stage == "routing" else load_stage_history(
                    args.work_dir / "backup_dir", args.platform, args.design,
                    1000, "routing")
            )

            # Paired deltas are most transferable within the same upstream family.
            # Use a family-conditioned subset when it is large enough to fit a GP;
            # otherwise retain all trusted stage records and keep family in context.
            current_families = set()
            for source_id in source_run_ids:
                family = _source_parent_family(
                    args.config_dir / f"config_{source_id}.mk", args.stage)
                if family:
                    current_families.add(family)
            family_hist = [h for h in hist if h.get("parent_family") in current_families]
            stage_history = family_hist if len(family_hist) >= 3 else hist

            paired = []
            for h in stage_history:
                delta = _paired_delta_objective(
                    h, args.objective, wl_base, ecp_base,
                    power_budget, power_base_val)
                if delta is None or len(h.get("params", {})) != len(stage_param_names):
                    continue
                row = dict(h)
                row["paired_objective"] = delta
                paired.append(row)
            if len(paired) >= 3:
                stage_history = paired
                observed_params = [h["params"] for h in paired]
                observed_objectives = [float(h["paired_objective"]) for h in paired]
                history_mode = "paired_delta"
            else:
                for h in stage_history:
                    if len(h.get("params", {})) != len(stage_param_names):
                        continue
                    value = _obj_from_metrics(h.get("child_metrics", h.get("metrics", {})))
                    if value is not None:
                        observed_params.append(h["params"])
                        observed_objectives.append(float(value))
                history_mode = "absolute_stage_metric"
            family_note = (f", family-matched={len(family_hist)}"
                           if current_families else "")
            print(f"[agent] {len(observed_params)} trusted {args.stage} observations "
                  f"({history_mode}, objective={args.objective}{family_note})",
                  file=sys.stderr)
        except Exception as e:
            print(f"[agent][WARN] resolved stage history load failed ({e}).",
                  file=sys.stderr)

    # NOTE: no current-iteration Bayesian fallback. Pairing THIS run's not-yet-executed
    # next-stage params (e.g. CTS params) with the CURRENT pre-mutation metrics (e.g.
    # post-placement) has no causal meaning. Until there are at least three trusted
    # cross-iteration stage observations, generation falls back to LHS/perturbation.
    if not observed_params:
        print(f"[agent] no trusted {args.stage} history yet -> LHS/perturbation only "
              f"(no clean-history projection or current-stage pseudo-labels).",
              file=sys.stderr)

    optimization_state = {}
    state_path = args.config_dir / "optimization_state.json"
    if state_path.is_file():
        try:
            loaded_state = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(loaded_state, dict):
                optimization_state = loaded_state
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[agent][WARN] prompt optimization state unavailable ({exc}).",
                  file=sys.stderr)
    cp0 = None
    cp0_path = args.config_dir / "cp0.txt"
    if cp0_path.is_file():
        try:
            cp0 = float(cp0_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError) as exc:
            print(f"[agent][WARN] prompt CP_0 unavailable ({exc}).", file=sys.stderr)

    model_score_records = []
    if args.work_dir is not None:
        max_prompt_iteration = max(
            (int(row.get("iteration", 0)) for row in resolved_prompt_history),
            default=0,
        )
        model_score_records = load_model_score_evidence(
            args.work_dir / "backup_dir", args.platform, args.design,
            max_prompt_iteration,
        )
    prompt_evidence_context = build_prompt_evidence(
        args.objective,
        clean_prompt_history,
        resolved_prompt_history,
        routing_prompt_history,
        optimization_state,
        _full_prompt_constraints(config, design_cfg),
        power_base_val,
        power_budget,
        cp0,
        model_score_records=model_score_records,
    )
    prompt_evidence_context.update(build_shared_prompt_context(
        config, args.platform, args.design, args.objective,
        prompt_evidence_context))
    source_target_edges = build_stage_source_target_edges(
        args.stage,
        source_run_ids,
        target_run_ids,
        args.config_dir,
        work_dir=args.work_dir,
    )

    conditional_focus_params = None
    conditional_meta = None
    if (args.stage == "routing"
            and os.environ.get("DRP_SEARCH_MODE", "").strip().upper() == "ROUTING_FOCUS"):
        try:
            conditional_focus_params, conditional_meta = generate_source_conditioned_routing(
                config=config,
                objective=args.objective,
                platform=args.platform,
                design=args.design,
                work_dir=args.work_dir,
                config_dir=args.config_dir,
                source_run_ids=source_run_ids,
                routing_history=all_stage_history,
                constraints=stage_param_constraints,
                seed=derived_seed,
                agentic_enabled=args.agentic,
            )
            if len(conditional_focus_params) != num_runs:
                raise RuntimeError(
                    f"conditional routing returned {len(conditional_focus_params)} rows, "
                    f"expected {num_runs}")
            print("[routing-focus][routing] source-conditioned selection "
                  f"{conditional_meta.get('counts', {})}", file=sys.stderr)
        except Exception as e:
            print(f"[routing-focus][ERROR] source-conditioned routing failed ({e}); "
                  "refusing an unpaired pooled fallback.", file=sys.stderr)
            raise

    if conditional_focus_params is not None:
        params = conditional_focus_params
        modes = list((conditional_meta or {}).get("modes") or [])
        param_origins = _focus_modes_to_origins(modes)
        conditioned_families = list(
            (conditional_meta or {}).get("families") or [])
        proposal_conditionings = [
            _proposal_conditioning(edge) for edge in source_target_edges
        ]
    elif args.agentic and len(stage_history) >= 3:
        # Same Agent1(ReAct inspect/model)+Agent2(generate+selection) framework as
        # inter-iteration, on the stage-param subset (no Agent3). Falls back to the
        # plain path internally on any failure / sparse history.
        params, param_origins, proposal_conditionings = generate_stage_params_agentic(
            stage=args.stage,
            config=config,
            platform=args.platform,
            design=args.design,
            objective=args.objective,
            num_kill=num_runs,
            sorted_metrics=sorted_metrics,
            source_run_ids=source_run_ids,
            target_run_ids=target_run_ids,
            config_dir=args.config_dir,
            stage_history=stage_history,
            stage_param_names=stage_param_names,
            param_constraints=stage_param_constraints,
            wl_base=wl_base,
            ecp_base=ecp_base,
            prompt_evidence_context=prompt_evidence_context,
            source_target_edges=source_target_edges,
            stage_shape_seed=derived_seed,
            return_provenance=True,
            llm_enabled=not args.no_llm,
        )
        conditioned_families = None
    else:
        params, param_origins, proposal_conditionings = generate_stage_params(
            stage=args.stage,
            config=config,
            platform=args.platform,
            design=args.design,
            objective=args.objective,
            num_kill=num_runs,
            sorted_metrics=sorted_metrics,
            source_run_ids=source_run_ids,
            target_run_ids=target_run_ids,
            config_dir=args.config_dir,
            observed_params=observed_params or None,
            observed_objectives=observed_objectives or None,
            prompt_evidence_context=prompt_evidence_context,
            source_target_edges=source_target_edges,
            stage_shape_seed=derived_seed,
            return_provenance=True,
            llm_enabled=not args.no_llm,
        )
        conditioned_families = None

    expected_keys = set(stage_param_constraints)
    if len(params) != num_runs:
        raise RuntimeError(
            f"{args.stage} generator returned {len(params)} rows; expected {num_runs}")
    for index, row in enumerate(params):
        if not isinstance(row, dict) or set(row) != expected_keys:
            actual = sorted(row) if isinstance(row, dict) else type(row).__name__
            raise RuntimeError(
                f"{args.stage} row {index} has schema {actual}; "
                f"expected {sorted(expected_keys)}")

    # The first-iteration ORFS baseline remains a true control while still occupying
    # one aligned row in each full-run stage batch.
    for run_id in sorted(frozen_run_ids):
        if run_id not in target_run_ids:
            raise RuntimeError(f"frozen run {run_id} is absent from the stage batch")
        index = target_run_ids.index(run_id)
        params[index] = extract_current_params(
            args.config_dir / f"config_{run_id}.mk", list(stage_param_constraints))
        missing = expected_keys - set(params[index])
        if missing:
            raise RuntimeError(
                f"frozen run {run_id} is missing stage values {sorted(missing)}")
        param_origins[index] = "replay"

    params_text = json.dumps(params, indent=2, allow_nan=False) + "\n"
    params_sha256 = hashlib.sha256(params_text.encode("utf-8")).hexdigest()
    provenance = _stage_provenance_payload(
        stage=args.stage,
        params=params,
        origins=param_origins,
        edges=source_target_edges,
        proposal_conditionings=proposal_conditionings,
        params_file=args.output,
        params_sha256=params_sha256,
        conditioned_families=conditioned_families,
        llm_enabled=not args.no_llm,
    )
    provenance_path = args.output.with_name(
        f"{args.output.stem}_provenance.json")
    _atomic_write_text(args.output, params_text)
    _atomic_write_text(
        provenance_path,
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False) + "\n",
    )

    print(f"Generated {len(params)} parameter sets → {args.output}")
    print(f"Recorded aligned stage provenance → {provenance_path}")


if __name__ == "__main__":
    main()
