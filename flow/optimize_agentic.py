#!/usr/bin/env python3
"""
Agentic inter-iteration optimizer for DRP-Agent.

Wraps the existing inter-iteration generation (elitism + failure penalty +
exploration annealing + LLM + Bayesian, in optimize.py) in a 3-agent framework
adapted from ORFO, WITHOUT RAG (all context is passed directly in the prompts):

  Agent1 — ReAct loop + tool-use, two stages: Inspection then Model. The Model
           stage is a ReAct loop whose Observation is the GPR held-out test-set
           error (dy/rel). Tools: configure_inspection, configure_model.
           Produces {inspection, model} configs + feature_weights.
  Agent2 — Param Set Generator. Builds a hybrid candidate pool (optimize.py's
           generator [LLM-proposed + Bayesian + elitism/penalty/annealing] UNION
           LHS), GPR-scores it, lets a Selection LLM pick the method/weights from
           the scored landscape (ORFO Agglom), then agglomeratively selects the k
           parameter sets for the next iteration.
  Agent3 — Textual Gradient Critic: a separate supervisor LLM critiques the
           iteration (the "gradient") and rewrites the agent prompt fragments via
           TextGrad; the rewritten instructions are persisted for the next iteration.

Execution order each Phase 7: Agent1 -> Agent2 (generate) -> Agent3 (critic,
which improves the NEXT iteration's prompts).

Routing-only focus is executed at post-CTS; the inter-iteration path remains a
10D upstream search and never writes final-routing knobs into its CSV.

Every agent step is best-effort: on any failure it degrades to the plain
optimize.py generation, so the pipeline never breaks.

The staged intra-iteration optimization (place -> DRP -> CTS -> DRP -> route ->
finish, in drp.py/agent.py/run_*.sh) is NOT touched by this module.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from common import (
    external_llm_enabled,
    is_feasible_objective_value,
    load_config,
    get_design_config,
    get_param_constraints,
)
from llm_usage import LLMUsageError, begin_call, fail_call, finish_call
from llm_client import create_llm_client
from candidate_tracking import (
    CANDIDATE_ID_KEY,
    CANDIDATE_ORIGIN_KEY,
    assign_batch_identity,
    bind_slots,
    lifecycle_path,
    metadata as candidate_metadata,
    record_pool_stage,
)
from agent2_candidate_selection import (
    _bounded_origin_quotas,
    _bounded_role_quotas,
    _enforce_origin_quotas,
    _enforce_selection_quotas,
    _fallback_select_with_quotas,
    _normalized_vector,
    _origin_counts,
    _probes_last,
    _quota_forced_ids,
    _rescale_between_ranges,
    _selection_event_details,
    _shape_pool_before_gpr,
    _uniform_hard_samples,
    _vectorize,
    full_probe_target_count,
)
from optimize import (
    FAILURE_PENALTY_MULT,
    build_history_summary,
    format_failed_configs,
    generate_next_iteration_params,
    load_iteration_history,
    load_resolved_history,
    load_stage_history,
    write_csv,
)
from search_policy import (
    FULL_SEARCH,
    ROUTING_PARAMETERS,
    ROUTING_FOCUS,
    persist_batch_plan,
    persist_optimization_state,
    policy_for_context,
    shape_next_batch,
    update_optimization_state,
)
from prompt_evidence import (
    budget_prompt_evidence,
    build_prompt_evidence,
    load_model_score_evidence,
)
from prompt_context import build_shared_prompt_context

# Optional ORFO helpers (hybrid agglomerative selection + GPR surrogate scoring).
try:
    from agglomfuncs import create_quality_scores, select_points
    from modelfuncs import (create_model, predict_with_model, latin_hypercube_sample,
                            create_acquisition_function)
    _HAVE_AGGLOM = True
except Exception as _imp_err:  # pragma: no cover
    print(f"[agentic][WARN] ORFO helpers unavailable ({_imp_err}); "
          f"Agent2 selection falls back to elitist truncation.", file=sys.stderr)
    _HAVE_AGGLOM = False

# Optional ORFO inspection helpers (real data-structure / distribution analysis
# feeding Agent1's observation). Best-effort.
try:
    from inspectfuncs import inspect_data_distribution, inspect_data_structure
    _HAVE_INSPECT = True
except Exception as _ie:  # pragma: no cover
    print(f"[agentic][WARN] inspectfuncs unavailable ({_ie}); Agent1 uses the "
          f"summary-stat observation only.", file=sys.stderr)
    _HAVE_INSPECT = False


# Default agent instruction fragments (the TextGrad "variables" Agent3 rewrites).
DEFAULT_INSTRUCTIONS = {
    "model": (
        "Choose a surrogate/strategy config that balances exploration and "
        "exploitation. Prefer exploitation as the campaign progresses and when "
        "many configurations have already routed successfully."
    ),
    "selection": (
        "Select the next batch to maximize feasible quality and diversity. "
        "Avoid parameter regions similar to runs that failed placement/routing."
    ),
}


# ---------------------------------------------------------------------------
# LLM plumbing (tool-use capable, OpenAI-compatible)
# ---------------------------------------------------------------------------

def _resolve_client(cfg_block: dict):
    """Build the selected client + call params from an llm/supervisor block."""
    if not external_llm_enabled(cfg_block):
        raise RuntimeError("external LLM requests disabled by --no-llm")
    model = cfg_block.get("model", "gpt-4o")
    return create_llm_client(cfg_block), model, {
        "temperature": cfg_block.get("temperature", 0.7),
        "max_tokens": cfg_block.get("max_tokens", 8192),
    }


def _usage_context(base: Optional[Mapping[str, Any]], *, agent: str,
                   operation: str, **extra: Any) -> Dict[str, Any]:
    """Add per-call labels without mutating the shared campaign context."""
    context = dict(base or {})
    context.update({"agent": agent, "operation": operation})
    context.update({key: value for key, value in extra.items()
                    if value is not None})
    return context


def _chat(client, model, messages, call_params, tools=None, *,
          usage_context: Optional[Mapping[str, Any]] = None):
    """One chat completion. Returns the message object (.content, .tool_calls)."""
    create_kwargs = dict(model=model, messages=messages, **call_params)
    if tools:
        create_kwargs["tools"] = tools
        create_kwargs["tool_choice"] = "auto"
    call = begin_call(
        model=model,
        context=usage_context,
        request_payload=create_kwargs,
        provider=str(getattr(client, "base_url", "") or ""),
    )
    try:
        resp = client.chat.completions.create(**create_kwargs)
    except Exception as exc:
        fail_call(call, exc)
        raise
    finish_call(call, resp)
    return resp.choices[0].message


# ---------------------------------------------------------------------------
# Context building (no RAG — everything goes into the prompt)
# ---------------------------------------------------------------------------

# Power-budget context for objective=TNS_EVAL, set by main() / agent.py before use.
_POWER_BUDGET = None
_POWER_BASE = None


def _objective_value(m: dict, objective: str, wl_base: float, ecp_base: float,
                     w_wl: float, w_ecp: float) -> Optional[float]:
    wl, ecp = m.get("wl"), m.get("ecp")
    if objective == "wl":
        return wl
    if objective == "ecp":
        return ecp
    if objective == "TNS_EVAL":
        from common import tns_eval_obj
        return tns_eval_obj(m, _POWER_BUDGET, _POWER_BASE)  # |TNS| + power penalty
    if wl is not None and ecp is not None:
        return w_wl * (wl / wl_base) + w_ecp * (ecp / ecp_base)
    return None


def _is_feasible_objective(value: Optional[float], objective: str) -> bool:
    return is_feasible_objective_value(value, objective)


def _penalty(objective: str, history: List[Dict], wl_base: float, ecp_base: float,
             w_wl: float, w_ecp: float) -> float:
    """Penalty (objective units) for failed runs in the surrogate's y-vector. For
    TNS_EVAL the scale is data-driven: 5x the worst feasible |TNS| in history (so a
    failed run is clearly worse than any feasible one), with a large fallback."""
    if objective == "wl":
        return FAILURE_PENALTY_MULT * wl_base
    if objective == "ecp":
        return FAILURE_PENALTY_MULT * ecp_base
    if objective == "TNS_EVAL":
        vals = [abs(h["metrics"]["tns"]) for h in history
                if h.get("metrics", {}).get("tns") is not None]
        return FAILURE_PENALTY_MULT * (max(vals) if vals else 1.0e6)
    return FAILURE_PENALTY_MULT * (w_wl + w_ecp)


def summarize_runs(history: List[Dict], objective: str, wl_base: float,
                   ecp_base: float, w_wl: float, w_ecp: float,
                   param_names: List[str]) -> Dict[str, Any]:
    """Compact, prompt-ready summary of the run history + failure modes."""
    current_iter = max((h["iteration"] for h in history), default=0)
    cur = [h for h in history if h["iteration"] == current_iter]
    feasible = [
        h for h in cur
        if _is_feasible_objective(
            _objective_value(h["metrics"], objective, wl_base, ecp_base, w_wl, w_ecp),
            objective)
    ]
    failed = [h for h in cur if h not in feasible]

    def _mean_range(entries, name):
        vals = [e["params"][name] for e in entries
                if name in e["params"] and e["params"][name] is not None]
        if not vals:
            return None
        return (float(np.mean(vals)), float(np.min(vals)), float(np.max(vals)))

    # Which params trend high in FAILED runs vs feasible (crude failure-mode hint).
    fail_hint = {}
    for name in param_names:
        f = _mean_range(failed, name)
        ok = _mean_range(feasible, name)
        if f and ok and abs(f[0] - ok[0]) > 1e-9:
            fail_hint[name] = {"failed_mean": round(f[0], 4), "feasible_mean": round(ok[0], 4)}

    objs = [_objective_value(h["metrics"], objective, wl_base, ecp_base, w_wl, w_ecp)
            for h in feasible]
    return {
        "current_iteration": current_iter,
        "n_runs": len(cur),
        "n_feasible": len(feasible),
        "n_failed": len(failed),
        "best_objective": round(min(objs), 4) if objs else None,
        "history_summary": build_history_summary(history, objective),
        "failed_configs": format_failed_configs(
            [{"run_id": h["run_id"], "params": h["params"]} for h in failed], param_names),
        "failure_mode_hint": fail_hint,
    }


def run_inspection(history: List[Dict], param_names: List[str],
                   constraints: Dict[str, dict], objective: str, wl_base: float,
                   ecp_base: float, w_wl: float, w_ecp: float,
                   inspect_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """ORFO-style inspection: build X/Y from history and run inspectfuncs
    (data distribution + structure analysis: linearity, manifold, clustering,
    correlations, surrogate-quality) into a compact numerical-results dict that
    feeds Agent1's observation. The inspect config (n_clusters,
    correlation_threshold) drives inspect_data_structure. Best-effort."""
    if not _HAVE_INSPECT:
        return {}
    penalty = _penalty(objective, history, wl_base, ecp_base, w_wl, w_ecp)
    X, Y = [], []
    for h in history:
        if not h.get("params"):
            continue
        obj = _objective_value(h["metrics"], objective, wl_base, ecp_base, w_wl, w_ecp)
        X.append(_vectorize(h["params"], param_names, constraints))
        Y.append(obj if obj is not None else penalty)
    if len(X) < 3:
        return {}
    try:
        X = np.array(X, dtype=float)
        Y = np.array(Y, dtype=float)
        dist = inspect_data_distribution(X, Y)
        struct = inspect_data_structure(X, Y, config={
            "n_clusters": int(inspect_cfg.get("n_clusters", 4)),
            "correlation_threshold": float(inspect_cfg.get("correlation_threshold", 0.3)),
            "n_neighbors": min(20, len(X) - 1),
            "perplexity": min(30, max(5, len(X) // 2)),
        })
        dist_trim = {k: v for k, v in dist.items() if not str(k).startswith("feature_")}
        # Per-feature importance weights (ORFO model_recommendations.feature_weights),
        # used to weight the GPR kernel. Keep only if well-formed (len == n_features).
        recs = struct.get("model_recommendations", {}) if isinstance(struct, dict) else {}
        fw = recs.get("feature_weights")
        try:
            fw_list = list(fw) if fw is not None else None
            fw = fw_list if (fw_list is not None and len(fw_list) == len(param_names)) else None
        except Exception:
            fw = None
        return {"feature_names": param_names, "distribution": dist_trim,
                "structure": struct, "feature_weights": fw}
    except Exception as e:
        print(f"[Inspect][WARN] inspectfuncs failed ({e}); skipping.", file=sys.stderr)
        return {}


# ---------------------------------------------------------------------------
# Agent 1: ORFO-order stages — Inspection -> Model(+ReAct GPR loop) -> Selection
# ---------------------------------------------------------------------------

_TOOL_INSPECT = {"type": "function", "function": {
    "name": "configure_inspection",
    "description": "Configure how run results are analyzed (clustering + correlation).",
    "parameters": {"type": "object", "properties": {
        "n_clusters": {"type": "integer", "description": "clusters for grouping runs (2-8)"},
        "correlation_threshold": {"type": "number", "description": "param-objective correlation cutoff (0-1)"},
    }, "required": ["n_clusters", "correlation_threshold"]}}}

_TOOL_MODEL = {"type": "function", "function": {
    "name": "configure_model",
    "description": "Configure the GPR surrogate / optimization strategy. kernel_type/"
                   "preprocessing shape the GP FIT (evaluated by the held-out dy/rel "
                   "feedback); acquisition (ei/ucb/pi) is EXECUTED downstream: it "
                   "scores the candidate pool in Agent2 and ranks the Bayesian-fill "
                   "suggestions; explore_frac steers candidate generation. "
                   "(surrogate_weight was removed: it was never consumed.)",
    "parameters": {"type": "object", "properties": {
        "kernel_type": {"type": "string", "enum": ["matern", "rbf"]},
        "preprocessing": {"type": "string", "enum": ["robust", "standard", "minmax", "none"]},
        "acquisition": {"type": "string", "enum": ["ei", "ucb", "pi"]},
        "explore_frac": {"type": "number", "description": "exploration fraction 0-1 (lower = exploit)"},
    }, "required": ["kernel_type"]}}}

_TOOL_SELECT = {"type": "function", "function": {
    "name": "configure_selection",
    "description": "Configure how the next batch is selected from candidates. "
                   "quality_weight balances model-quality vs spatial diversity in "
                   "hybrid selection. uncertainty_bonus adds EXTRA exploration "
                   "pressure (weight on GP std) on top of the acquisition's own "
                   "exploration — 0 disables it.",
    "parameters": {"type": "object", "properties": {
        "method": {"type": "string", "enum": ["elitist", "kmeans", "hybrid", "entropy", "graph"]},
        "quality_weight": {"type": "number"},
        "uncertainty_bonus": {"type": "number"},
    }, "required": ["method"]}}}

_DEFAULT_CONFIGS = {
    "inspection": {"n_clusters": 4, "correlation_threshold": 0.3},
    "model": {"kernel_type": "matern", "preprocessing": "robust", "acquisition": "ei",
              "explore_frac": None},
    "selection": {"method": "hybrid", "quality_weight": 0.7, "uncertainty_bonus": 0.2},
}


def _build_xy(history, param_names, constraints, objective, wl_base, ecp_base, w_wl, w_ecp):
    """Param matrix X and objective vector y (failed runs -> penalty value)."""
    penalty = _penalty(objective, history, wl_base, ecp_base, w_wl, w_ecp)
    X, y = [], []
    for h in history:
        if not h.get("params"):
            continue
        obj = _objective_value(h["metrics"], objective, wl_base, ecp_base, w_wl, w_ecp)
        X.append(_vectorize(h["params"], param_names, constraints))
        y.append(obj if obj is not None else penalty)
    return np.array(X, dtype=float), np.array(y, dtype=float)


def _prepare_train_test(X, y, train_ratio=0.7, seed=42):
    """70/30 split for GPR held-out test-set feedback (uses all data if too few)."""
    n = len(X)
    if n < 4:
        return X, y, X, y
    rng = np.random.RandomState(seed)
    idx = rng.permutation(n)
    k = max(1, int(round(train_ratio * n)))
    tr, te = idx[:k], idx[k:]
    if len(te) == 0:
        te = tr
    return X[tr], y[tr], X[te], y[te]


def _gpr_feedback(model_cfg, X_tr, y_tr, X_te, y_te, feature_weights=None):
    """Train a GPR with model_cfg on train, predict test -> {dy: mean abs error,
    rel: mean relative error}. This is the REAL Observation for the model ReAct loop.
    feature_weights (from inspection's model_recommendations) weight the kernel."""
    try:
        gp = create_model(X_tr, y_tr,
                          kernel_type=model_cfg.get("kernel_type", "matern"),
                          preprocessing=model_cfg.get("preprocessing", "robust"),
                          feature_weights=feature_weights)
        mu, _ = predict_with_model(gp, X_te)
        mu = np.asarray(mu, dtype=float)
        abs_err = np.abs(mu - y_te)
        denom = np.where(np.abs(y_te) > 1e-9, np.abs(y_te), 1e-9)
        return {"dy": round(float(np.mean(abs_err)), 4),
                "rel": round(float(np.mean(abs_err / denom)), 4)}
    except Exception as e:
        return {"dy": "N/A", "rel": "N/A", "error": str(e)}


def _llm_configure_audited(client, model, call_params, tool, system, user,
                           default_cfg, *, usage_context=None):
    """Run one tool-enabled completion and report what the model actually returned."""
    cfg = dict(default_cfg)
    tool_name = tool["function"]["name"]
    audit = {
        "requested": True,
        "returned_tool_calls": 0,
        "matching_tool_calls": 0,
        "tool_responded": False,
        "config_applied": False,
        "fallback_reason": None,
    }
    try:
        msg = _chat(client, model,
                    [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    call_params, tools=[tool], usage_context=usage_context)
        returned = list(getattr(msg, "tool_calls", None) or [])
        audit["returned_tool_calls"] = len(returned)
        matching = [
            tc for tc in returned
            if getattr(getattr(tc, "function", None), "name", None) == tool_name
        ]
        audit["matching_tool_calls"] = len(matching)
        if not matching:
            audit["fallback_reason"] = "no_matching_tool_response"
            return cfg, audit
        audit["tool_responded"] = True
        try:
            parsed = json.loads(matching[0].function.arguments)
        except Exception as exc:
            audit["fallback_reason"] = f"invalid_tool_arguments:{exc}"
            return cfg, audit
        if not isinstance(parsed, dict):
            audit["fallback_reason"] = "tool_arguments_not_object"
            return cfg, audit
        cfg.update(parsed)
        audit["config_applied"] = True
    except LLMUsageError:
        raise
    except Exception as e:
        audit["fallback_reason"] = f"tool_request_failed:{e}"
        print(f"[stage-llm][WARN] tool '{tool_name}' failed ({e}); "
              f"using default.", file=sys.stderr)
    return cfg, audit


def _llm_configure(client, model, call_params, tool, system, user, default_cfg,
                   *, usage_context=None):
    """Backward-compatible config-only wrapper used by the global Agent1/Agent2."""
    cfg, _ = _llm_configure_audited(
        client, model, call_params, tool, system, user, default_cfg,
        usage_context=usage_context)
    return cfg


def _react_model_stage(client, model, call_params, init_cfg, X, y, instructions,
                       max_iters, feature_weights=None, decision_context="",
                       *, usage_context=None):
    """Model-stage ReAct loop (ORFO style):
       THOUGHT  -> judge model quality / whether to reconfigure
       ACTION   -> call configure_model with a better config
       OBSERVE  -> train GPR(config) on 70% train, measure dy/rel error on 30% test
    The LLM iterates on the CONSEQUENCE of each config (real test error), not self-review.
    Returns the final model config."""
    cfg = dict(init_cfg)
    if not _HAVE_AGGLOM or len(X) < 4:
        print("[ReAct][model] skipped (no GPR helpers or <4 history points).")
        return cfg
    X_tr, y_tr, X_te, y_te = _prepare_train_test(X, y)
    system = (
        "You are an EDA optimization engineer in a ReAct loop tuning a GPR surrogate. "
        f"{instructions.get('model', '')} "
        "Each step you receive the GPR model's held-out test-set error (dy=mean abs "
        "error, rel=mean relative error). dy/rel measure ONLY the fit quality of "
        "kernel_type/preprocessing — tune those from this feedback. acquisition and "
        "explore_frac are strategy knobs executed downstream (candidate scoring/"
        "generation); they do NOT move dy/rel, so set them from the inspection "
        "context, not by chasing this error. THOUGHT: judge if the error is "
        "acceptable. ACTION: if not, call configure_model with a better config. "
        "If acceptable, reply DONE without calling tools.")
    if decision_context:
        system += f"\nAuthoritative optimization context:\n{decision_context}"
    hist = [{"role": "system", "content": system}]
    for step in range(max_iters):
        fb = _gpr_feedback(cfg, X_tr, y_tr, X_te, y_te, feature_weights)  # Observation (real)
        obs = (f"Step {step}: model config={json.dumps(cfg)}; "
               f"test-set feedback dy={fb.get('dy')}, rel={fb.get('rel')}.")
        print(f"[ReAct][model] {obs}")
        hist.append({"role": "user", "content": obs +
                     " If acceptable reply DONE; else call configure_model with a better config."})
        try:
            msg = _chat(
                client, model, hist, call_params, tools=[_TOOL_MODEL],
                usage_context=_usage_context(
                    usage_context, agent="agent1",
                    operation="configure_model_react", react_step=step),
            )
        except LLMUsageError:
            raise
        except Exception as e:
            print(f"[ReAct][model][WARN] step {step} failed ({e}); stop.", file=sys.stderr)
            break
        tcs = getattr(msg, "tool_calls", None)
        if not tcs:
            print(f"[ReAct][model] converged at step {step} (model accepted).")
            break
        for tc in tcs:
            if tc.function.name == "configure_model":
                try:
                    cfg.update(json.loads(tc.function.arguments))
                except Exception:
                    pass
        # Plain-text continuation (avoid replaying raw tool_calls; some endpoints 500).
        hist.append({"role": "assistant", "content": f"Updated model config: {json.dumps(cfg)}"})
    return cfg


_AUTHORITATIVE_EVIDENCE_KEYS = (
    "objective_contract",
    "top_successful_configs",
    "stratified_bests",
    "basin_summary",
    "run_classifications",
    "distance_info",
    "source_target_edges",
    "parameter_distributions",
)


def _authoritative_context(
    payload: Mapping[str, Any],
    candidate_examples: Sequence[Mapping[str, Any]] = (),
) -> Dict[str, Any]:
    """Place structurally budgeted evidence in an explicit priority order."""
    return budget_prompt_evidence(
        {
            key: payload.get(key) for key in _AUTHORITATIVE_EVIDENCE_KEYS
            if payload.get(key) is not None
        },
        candidate_examples=candidate_examples,
    )


def _bounded_json_text(value: Any, max_chars: int) -> str:
    """Serialize a field-budgeted object without ever slicing serialized JSON."""
    limit = max(256, int(max_chars))

    def serialize(item: Any) -> str:
        return json.dumps(item, indent=2, default=str)

    raw = serialize(value)
    if len(raw) <= limit:
        return raw
    if not isinstance(value, Mapping):
        return serialize({
            "status": "omitted_to_preserve_valid_json",
            "original_type": type(value).__name__,
            "original_serialized_chars": len(raw),
        })

    # Mapping insertion order is the priority contract. Keep whole fields while they
    # fit and replace lower-priority ones with compact, valid-JSON omission records.
    bounded: Dict[str, Any] = {}
    for key, item in value.items():
        candidate = dict(bounded)
        candidate[str(key)] = item
        if len(serialize(candidate)) <= limit:
            bounded[str(key)] = item
            continue
        if isinstance(item, Mapping):
            size = len(item)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
            size = len(item)
        else:
            size = None
        bounded[str(key)] = {
            "status": "omitted_by_serialization_budget",
            "item_count": size,
            "serialized_chars": len(serialize(item)),
        }
        if len(serialize(bounded)) > limit:
            bounded.pop(str(key), None)
    return serialize(bounded)


def agent1_stages(llm_cfg, summary, X, y, instructions, max_iters, inspect_runner,
                  *, llm_enabled: bool = True, usage_context=None):
    """Agent1 in ORFO order: Inspection -> Model(+ReAct GPR loop) -> Selection.
    Returns ({inspection, model, selection} configs, inspection numerical results)."""
    configs = {k: dict(v) for k, v in _DEFAULT_CONFIGS.items()}
    if not llm_enabled:
        print("[no-llm][Agent1] using fixed inspection/model configs.")
        return configs, inspect_runner(configs["inspection"])
    try:
        client, model, call_params = _resolve_client(llm_cfg)
    except Exception as e:
        print(f"[Agent1][WARN] LLM unavailable ({e}); default configs.", file=sys.stderr)
        return configs, inspect_runner(configs["inspection"])
    authority = _authoritative_context(summary)
    ordinary_summary = {
        key: value for key, value in summary.items()
        if key not in _AUTHORITATIVE_EVIDENCE_KEYS
    }
    authority_json = _bounded_json_text(authority, 32000)
    ordinary_json = _bounded_json_text(ordinary_summary, 5000)
    ctx = (
        "Authoritative constrained-objective evidence:\n"
        + authority_json
        + "\n\nBounded run summary:\n"
        + ordinary_json
    )

    # Stage 1: Inspection — LLM picks n_clusters / correlation_threshold.
    print("\n--- Stage 1: Inspection ---")
    configs["inspection"] = _llm_configure(
        client, model, call_params, _TOOL_INSPECT,
        "You configure the data-inspection analysis for an EDA parameter optimizer.",
        f"Run-result feedback (no RAG):\n{ctx}\n\nChoose n_clusters and correlation_threshold.",
        _DEFAULT_CONFIGS["inspection"],
        usage_context=_usage_context(
            usage_context, agent="agent1", operation="configure_inspection"))
    # Run the real inspectfuncs analysis WITH the chosen config.
    inspection = inspect_runner(configs["inspection"])
    feature_weights = inspection.get("feature_weights") if inspection else None
    insp_ctx = (_bounded_json_text(inspection, 6000)
                if inspection else "(inspection analysis unavailable)")
    decision_context = authority_json

    # Stage 2: Model — initial config, then ReAct GPR-feedback loop.
    print("\n--- Stage 2: Model (initial config + ReAct GPR loop) ---")
    init_model = _llm_configure(
        client, model, call_params, _TOOL_MODEL,
        "You configure a GPR surrogate model for Bayesian optimization. "
        f"{instructions.get('model', '')}",
        f"Authoritative objective/history context:\n{decision_context}\n\n"
        f"Inspection numerical analysis:\n{insp_ctx}\n\n"
        "Choose kernel_type, preprocessing, acquisition, explore_frac.",
        _DEFAULT_CONFIGS["model"],
        usage_context=_usage_context(
            usage_context, agent="agent1", operation="configure_model_initial"))
    configs["model"] = _react_model_stage(
        client, model, call_params, init_model, X, y, instructions, max_iters,
        feature_weights=feature_weights, decision_context=decision_context,
        usage_context=usage_context)

    # NOTE: the Selection config is NOT decided here. It is decided in Agent2
    # (ORFO Agglom stage) AFTER the candidate pool is GPR-scored, so the LLM can
    # choose method/weights informed by the real prediction landscape. The
    # 'selection' entry below stays at defaults as a placeholder.
    print(f"[Agent1] inspection + model configs: "
          f"{json.dumps({k: configs[k] for k in ('inspection', 'model')})}")
    return configs, inspection


# ---------------------------------------------------------------------------
# Agent 2: generate the next batch (reuse optimize.py + optional agglom selection)
# ---------------------------------------------------------------------------

def _decide_selection(llm_cfg, instructions, mu, std, y_hist, model_cfg,
                      n_candidates, candidate_audit=None, evidence=None, *,
                      llm_enabled: bool = True, usage_context=None):
    """Selection LLM (ORFO Agglom stage): picks method / quality_weight /
    uncertainty_bonus INFORMED by the GPR-scored candidate prediction landscape
    (mu/std distribution), not blind. Returns the selection config."""
    default = dict(_DEFAULT_CONFIGS["selection"])
    if not llm_enabled:
        print("[no-llm][Agent2] using fixed selection config.")
        return default
    if not llm_cfg:
        return default
    try:
        client, model, call_params = _resolve_client(llm_cfg)
    except Exception as e:
        print(f"[Agent2][WARN] selection LLM unavailable ({e}); default selection.", file=sys.stderr)
        return default

    def _stats(a):
        a = np.asarray(a, dtype=float)
        return {"min": round(float(np.min(a)), 4), "mean": round(float(np.mean(a)), 4),
                "max": round(float(np.max(a)), 4)}

    landscape = {
        "n_candidates": int(n_candidates),
        "predicted_objective": _stats(mu),   # lower is better
        "uncertainty_std": _stats(std),
        "history_best_objective": round(float(np.min(y_hist)), 4) if len(y_hist) else None,
    }
    audit_rows = list(candidate_audit or [])
    top_quality = sorted(
        audit_rows, key=lambda row: float(row.get("acquisition", float("-inf"))),
        reverse=True)[:12]
    top_novel = sorted(
        audit_rows,
        key=lambda row: float(row.get("distance_to_nearest_history") or -1.0),
        reverse=True)[:8]
    examples = []
    seen_ids = set()
    for row in top_quality + top_novel:
        if row.get("candidate_id") in seen_ids:
            continue
        seen_ids.add(row.get("candidate_id"))
        examples.append(row)
    authority = _authoritative_context(evidence or {}, examples)
    selection_context: Dict[str, Any] = {}
    if "objective_contract" in authority:
        selection_context["objective_contract"] = authority.pop("objective_contract")
    selection_context["prediction_landscape"] = landscape
    selection_context.update(authority)
    selection_json = _bounded_json_text(selection_context, 32000)
    instr = (instructions or {}).get("selection", "")
    return _llm_configure(
        client, model, call_params, _TOOL_SELECT,
        "You configure the batch-selection step for an EDA parameter optimizer. " + instr,
        "Below is the GPR-scored candidate pool's prediction landscape. Choose the "
        "selection method and weights that best balance feasible quality and diversity "
        "for THIS landscape (high uncertainty -> raise uncertainty_bonus; low diversity "
        "or clustered predictions -> hybrid/graph; clear good region -> kmeans/raise "
        "quality_weight; very sparse feasible data -> elitist).\n"
        f"Candidate prediction landscape (distances are normalized by parameter "
        f"bounds):\n{selection_json}\n"
        f"Model config: {json.dumps(model_cfg)}\n\n"
        "Choose method (elitist/kmeans/hybrid/entropy/graph), quality_weight, uncertainty_bonus.",
        default,
        usage_context=_usage_context(
            usage_context, agent="agent2", operation="configure_selection"))


_TOOL_ROUTING_SELECT = {"type": "function", "function": {
    "name": "configure_selection",
    "description": "Configure one cross-family selection for parent-conditioned "
                   "two-dimensional routing candidates.",
    "parameters": {"type": "object", "properties": {
        "family_allocation": {
            "type": "string", "enum": ["balanced", "confidence", "quality"],
            "description": "How Agent2 budget is shared across parent families."},
        "quality_weight": {"type": "number", "description": "Acquisition-score weight 0-1."},
        "uncertainty_bonus": {"type": "number", "description": "Extra GP-uncertainty weight 0-1."},
        "diversity_weight": {"type": "number", "description": "Within-family novelty weight 0-1."},
        "family_cap": {"type": "number", "description": "Maximum fraction for one family 0-1."},
    }, "required": ["family_allocation"]}}}


class RoutingFocusAgenticController:
    """Exactly one Inspect, one Model, and one cross-family Selection tool call."""

    def __init__(self, llm_cfg: Optional[Dict[str, Any]],
                 instructions: Optional[Dict[str, str]] = None,
                 evidence: Optional[Mapping[str, Any]] = None,
                 *, llm_enabled: bool = True, usage_context=None):
        self.llm_cfg = llm_cfg or {}
        self.llm_enabled = bool(llm_enabled)
        self.instructions = instructions or DEFAULT_INSTRUCTIONS
        self.evidence = dict(evidence or {})
        self.usage_context = (None if usage_context is None
                              else dict(usage_context))
        self._client_bundle = None
        self._client_error = None
        self.tool_requests = {"inspect": 0, "model": 0, "selection": 0}
        self.tool_calls = {"inspect": 0, "model": 0, "selection": 0}
        self.tool_configs_applied = {"inspect": 0, "model": 0, "selection": 0}

    def _client(self):
        if not self.llm_enabled:
            self._client_error = "disabled_by_no_llm"
            return None
        if self._client_bundle is None and self._client_error is None:
            try:
                self._client_bundle = _resolve_client(self.llm_cfg)
            except Exception as exc:
                self._client_error = str(exc)
        return self._client_bundle

    def configure(self, *, summary, inspection_runner, policy):
        inspect_default = dict(_DEFAULT_CONFIGS["inspection"])
        model_default = {
            "kernel_type": "matern",
            "preprocessing": "none",
            "acquisition": str(policy.get("routing_acquisition", "ei")),
            "explore_frac": None,
        }
        bundle = self._client()
        if bundle is None:
            inspection = inspection_runner(inspect_default)
            return {
                "inspection_config": inspect_default,
                "inspection": inspection,
                "model": model_default,
                "tool_requests": dict(self.tool_requests),
                "tool_calls": dict(self.tool_calls),
                "tool_configs_applied": dict(self.tool_configs_applied),
                "fallback_reason": self._client_error or "LLM unavailable",
            }

        client, model, call_params = bundle
        authority = _authoritative_context(self.evidence)
        authority_json = _bounded_json_text(authority, 24000)
        family_json = _bounded_json_text(summary, 8000)
        context = (
            "Authoritative constrained-objective evidence:\n"
            f"{authority_json}\n\nRouting parent-family summary:\n{family_json}"
        )
        self.tool_requests["inspect"] += 1
        inspect_usage = ({"usage_context": _usage_context(
            self.usage_context, agent="agent1", operation="configure_inspection")}
            if self.usage_context is not None else {})
        inspect_config, inspect_audit = _llm_configure_audited(
            client, model, call_params, _TOOL_INSPECT,
            "You configure one joint inspection across all active routing parent "
            "families. The only modeled features are PIN_LAYER_ADJUST and "
            "ABOVE_LAYER_ADJUST; family identity is contextual, not a pooled feature.",
            f"{context}\n\n"
            "Choose one n_clusters and correlation_threshold shared by this focus batch.",
            inspect_default,
            **inspect_usage,
        )
        self.tool_calls["inspect"] += int(inspect_audit.get(
            "matching_tool_calls", int(inspect_audit["tool_responded"])))
        self.tool_configs_applied["inspect"] += int(inspect_audit["config_applied"])
        inspection = inspection_runner(inspect_config)
        inspection_context = _bounded_json_text(inspection, 6000)
        self.tool_requests["model"] += 1
        model_usage = ({"usage_context": _usage_context(
            self.usage_context, agent="agent1", operation="configure_model")}
            if self.usage_context is not None else {})
        model_config, model_audit = _llm_configure_audited(
            client, model, call_params, _TOOL_MODEL,
            "You configure one shared two-dimensional GPR strategy for several "
            "parent families. Each family will fit its own GP and pass an independent "
            "LOO-CV gate. explore_frac reserves deterministic novelty; acquisition "
            "scores only models that pass the gate. " + self.instructions.get("model", ""),
            f"Joint inspection:\n{inspection_context}\n\n"
            f"{context}\n\nChoose one shared kernel, preprocessing, "
            "acquisition, and explore_frac.",
            model_default,
            **model_usage,
        )
        self.tool_calls["model"] += int(model_audit.get(
            "matching_tool_calls", int(model_audit["tool_responded"])))
        self.tool_configs_applied["model"] += int(model_audit["config_applied"])
        return {
            "inspection_config": inspect_config,
            "inspection": inspection,
            "model": model_config,
            "tool_requests": dict(self.tool_requests),
            "tool_calls": dict(self.tool_calls),
            "tool_configs_applied": dict(self.tool_configs_applied),
            "tool_audit": {
                "inspect": inspect_audit,
                "model": model_audit,
            },
        }

    def select(self, *, landscape, model_config, policy):
        default = {
            "family_allocation": "confidence",
            "quality_weight": 1.0,
            "uncertainty_bonus": 0.0,
            "diversity_weight": float(policy["routing_agentic_diversity_weight"]),
            "family_cap": float(policy["routing_agentic_family_cap"]),
        }
        bundle = self._client()
        if bundle is None:
            return {
                **default,
                "_tool_requested": False,
                "_tool_called": False,
                "_tool_call_count": 0,
                "_tool_config_applied": False,
            }
        client, model, call_params = bundle
        self.tool_requests["selection"] += 1
        authority_json = _bounded_json_text(
            _authoritative_context(self.evidence), 24000)
        landscape_json = _bounded_json_text(landscape, 8000)
        context = (
            "Authoritative constrained-objective evidence:\n"
            f"{authority_json}\n\nScored family landscape:\n{landscape_json}"
        )
        selection_usage = ({"usage_context": _usage_context(
            self.usage_context, agent="agent2", operation="configure_selection")}
            if self.usage_context is not None else {})
        configured, audit = _llm_configure_audited(
            client, model, call_params, _TOOL_ROUTING_SELECT,
            "You make one cross-family routing batch-selection decision. Parent "
            "families are causally distinct, so diversity is measured within family; "
            "family_allocation controls coverage across basins. "
            + self.instructions.get("selection", ""),
            f"Shared model config:\n{json.dumps(model_config)}\n\n"
            f"{context}\n\nChoose allocation and weights.",
            default,
            **selection_usage,
        )
        self.tool_calls["selection"] += int(audit.get(
            "matching_tool_calls", int(audit["tool_responded"])))
        self.tool_configs_applied["selection"] += int(audit["config_applied"])
        return {
            **configured,
            "_tool_requested": True,
            "_tool_called": bool(audit["tool_responded"]),
            "_tool_call_count": int(audit.get(
                "matching_tool_calls", int(audit["tool_responded"]))),
            "_tool_config_applied": bool(audit["config_applied"]),
            "_tool_audit": audit,
        }


def agent2_generate(config: dict, platform: str, design: str, objective: str,
                    num_runs: int, history: List[Dict], weight_wl: float,
                    weight_ecp: float, total_iters: int, agent1_cfg: Dict[str, Any],
                    all_constraints: Dict[str, dict], param_names: List[str],
                    wl_base: float, ecp_base: float, pool_mult: int,
                    lhs_mult: int = 8, feature_weights=None, llm_cfg=None,
                    instructions=None, *,
                    llm_enabled: bool = True,
                    resolved_history: Optional[List[Dict]] = None,
                    routing_history: Optional[List[Dict]] = None,
                    optimization_state: Optional[Dict[str, Any]] = None,
                    policy_seed: Any = None,
                    candidate_campaign_id: Optional[str] = None,
                    candidate_iteration: Optional[int] = None,
                    candidate_lifecycle_path: Optional[Path] = None,
                    prompt_evidence: Optional[Dict[str, Any]] = None,
                    usage_context: Optional[Mapping[str, Any]] = None,
                    ) -> Tuple[List[Dict], Dict[str, Any]]:
    """Agent2: build a hybrid candidate pool (DRP generator UNION LHS), GPR-score it,
    let the Selection LLM choose method/weights INFORMED by the scores (ORFO Agglom),
    then agglomeratively select. DRP elites are always kept. Also generates parameters
    directly via the LLM (inside generate_next_iteration_params). Returns
    (params, selection_config)."""
    model_cfg = agent1_cfg.get("model", {})
    explore_override = model_cfg.get("explore_frac")
    acquisition = model_cfg.get("acquisition", "ei")

    pool_size = max(num_runs, num_runs * max(1, pool_mult))
    target_iteration = int(candidate_iteration or (
        max((h.get("iteration", 0) for h in history), default=0) + 1))
    campaign_id = str(candidate_campaign_id or f"adhoc:{platform}:{design}")
    pool = generate_next_iteration_params(   # DRP: LLM-proposed + Bayesian + elitism/penalty/annealing
        config=config, platform=platform, design=design, objective=objective,
        num_runs=pool_size, history=history, weight_wl=weight_wl,
        weight_ecp=weight_ecp, total_iters=total_iters,
        explore_frac_override=explore_override,
        acquisition_override=acquisition,     # Agent1's acquisition ranks the Bayesian fill too
        candidate_campaign_id=campaign_id,
        candidate_iteration=target_iteration,
        candidate_lifecycle_path=candidate_lifecycle_path,
        prompt_evidence=prompt_evidence,
        llm_enabled=llm_enabled,
        usage_context=usage_context,
    )

    # Hybrid candidate pool: DRP UNION LHS. Reserve explicit whole-row probes now,
    # before scoring; these exact configurations later occupy the protected probe slots.
    hybrid_lhs: List[Dict[str, Any]] = []
    try:
        # Derived seed: seed=None would draw from OS entropy, bypassing DRP_SEED.
        lhs_count = num_runs * max(1, lhs_mult)
        lhs_seed = int(np.random.randint(0, 10000))
        try:
            sampler = latin_hypercube_sample
        except NameError:
            sampler = None
        if sampler is None:
            raw_lhs = _uniform_hard_samples(
                lhs_count, all_constraints, lhs_seed)
        else:
            try:
                raw_lhs = sampler(
                    lhs_count, all_constraints, seed=lhs_seed)
            except Exception as exc:
                print(f"[Agent2][WARN] LHS helper failed ({exc}); using "
                      "deterministic hard-space samples.", file=sys.stderr)
                raw_lhs = _uniform_hard_samples(
                    lhs_count, all_constraints, lhs_seed)
        policy = policy_for_context(config, objective, platform, design) or {}
        probe_count = full_probe_target_count(num_runs, policy)
        if probe_count > len(raw_lhs):
            raise RuntimeError(
                "Agent2 LHS pool is smaller than the required full-probe quota: "
                f"need {probe_count}, have {len(raw_lhs)}")
        lhs_origins = ["full_probe" if index < probe_count else "lhs"
                       for index in range(len(raw_lhs))]
        hybrid_lhs = assign_batch_identity(
            raw_lhs,
            campaign_id,
            target_iteration,
            origins=lhs_origins,
            proposal_keys=[f"agent2-hybrid-lhs:{index + 1}"
                           for index in range(len(raw_lhs))],
        )
    except Exception as e:
        print(f"[Agent2][WARN] LHS sampling failed ({e}); DRP pool only.", file=sys.stderr)
    combined_pool = list(pool) + hybrid_lhs
    if candidate_lifecycle_path is not None:
        record_pool_stage(
            candidate_lifecycle_path,
            combined_pool,
            "agent2_candidate_pool",
            details={
                "drp_pool_size": len(pool),
                "hybrid_lhs_size": len(hybrid_lhs),
                "full_probe_count": sum(
                    item.get(CANDIDATE_ORIGIN_KEY) == "full_probe"
                    for item in hybrid_lhs),
            },
        )
    combined_pool = _shape_pool_before_gpr(
        combined_pool,
        history=history,
        resolved_history=list(resolved_history or ()),
        routing_history=list(routing_history or ()),
        optimization_state=optimization_state,
        constraints=all_constraints,
        policy_config=config,
    )
    if candidate_lifecycle_path is not None:
        record_pool_stage(
            candidate_lifecycle_path,
            combined_pool,
            "pre_gpr_shaped",
            details={"pool_size": len(combined_pool),
                     "scoring_contract": "effective_config"},
        )

    n_keep = min(2, num_runs)
    kept = combined_pool[:n_keep]
    rest = list(combined_pool[n_keep:])
    need = num_runs - len(kept)
    resolved_policy = policy_for_context(config, objective, platform, design)
    policy = resolved_policy or {}
    front_ids = {
        item.get(CANDIDATE_ID_KEY) for item in kept
        if item.get(CANDIDATE_ID_KEY) is not None
    }
    quotas = _bounded_origin_quotas(num_runs, need, policy, kept)
    shaping_active = bool(
        resolved_policy is not None
        and optimization_state
        and optimization_state.get("enabled", False)
        and optimization_state.get("mode") == FULL_SEARCH
    )
    role_quotas = (
        _bounded_role_quotas(num_runs, need, policy, quotas, kept)
        if shaping_active else {}
    )

    if not _HAVE_AGGLOM:
        unforced = kept + rest[:need]
        selected = _fallback_select_with_quotas(
            kept, rest, num_runs, policy, quotas, role_quotas)
        quota_forced_ids = _quota_forced_ids(selected, unforced, quotas)
        origin_counts = _origin_counts(selected)
        if candidate_lifecycle_path is not None:
            record_pool_stage(
                candidate_lifecycle_path, selected, "agent2_selected",
                status="fallback", details=[{
                    **details, "reason": "no GPR helpers",
                } for details in _selection_event_details(
                    selected, "elitist", quota_forced_ids=quota_forced_ids,
                    front_ids=front_ids)])
        return selected[:num_runs], {
            "method": "elitist", "note": "no GPR helpers",
            "selected_origin_counts": origin_counts,
            "quota_forced_candidate_ids": sorted(quota_forced_ids),
            "selected_candidate_ids": [
                item.get(CANDIDATE_ID_KEY) for item in selected[:num_runs]],
        }

    candidate_audit: List[Dict[str, Any]] = []
    audit_by_id: Dict[str, Dict[str, Any]] = {}
    unforced_selection = kept + rest[:need]
    try:
        # Surrogate trained on history (feasible + penalty points).
        penalty = _penalty(objective, history, wl_base, ecp_base, weight_wl, weight_ecp)
        X_hist, y_hist = [], []
        for h in history:
            if not h.get("params"):
                continue
            obj = _objective_value(h["metrics"], objective, wl_base, ecp_base, weight_wl, weight_ecp)
            X_hist.append(_vectorize(h["params"], param_names, all_constraints))
            y_hist.append(obj if obj is not None else penalty)
        X_hist = np.array(X_hist, dtype=float)
        y_hist = np.array(y_hist, dtype=float)
        incumbent = _best_feasible_params(
            history, objective, wl_base, ecp_base, weight_wl, weight_ecp)
        try:
            from prompt_evidence import annotate_candidate_distances

            rest = annotate_candidate_distances(
                rest, history, all_constraints, incumbent)
        except Exception as exc:
            print(f"[Agent2][WARN] candidate distance audit unavailable ({exc}).",
                  file=sys.stderr)
        X_pool = np.array(
            [_vectorize(p, param_names, all_constraints) for p in rest], dtype=float)
        X_pool_normalized = np.array(
            [_normalized_vector(p, param_names, all_constraints) for p in rest],
            dtype=float)

        # Always GPR-score the pool first, so the Selection LLM decides from real scores.
        gp = create_model(X_hist, y_hist,
                          kernel_type=model_cfg.get("kernel_type", "matern"),
                          preprocessing=model_cfg.get("preprocessing", "robust"),
                          feature_weights=feature_weights)
        mu, std = predict_with_model(gp, X_pool)
        mu = np.asarray(mu, dtype=float)
        std = np.asarray(std, dtype=float)
        # EXECUTE Agent1's acquisition (previously a no-op: raw mu/std went straight
        # into quality scoring, so ei/ucb/pi never changed the ranking). Acquisition
        # scores are higher-is-better and already blend mean vs uncertainty, so they
        # enter create_quality_scores with minimize=False and no separate std term.
        acq_fn = create_acquisition_function(acquisition)
        acq_scores = np.asarray(acq_fn(mu, std, float(np.min(y_hist))), dtype=float)

        # Selection decision (ORFO Agglom): LLM picks method/weights from the landscape.
        print("\n--- Agent2 selection (LLM, informed by candidate scores) ---")
        candidate_audit = [
            {
                "candidate_id": candidate.get(CANDIDATE_ID_KEY),
                "origin": candidate.get(CANDIDATE_ORIGIN_KEY),
                "predicted_objective": round(float(mu[index]), 6),
                "uncertainty": round(float(std[index]), 6),
                "acquisition": round(float(acq_scores[index]), 6),
                **dict(candidate.get("_distance_info") or {}),
            }
            for index, candidate in enumerate(rest)
        ]
        audit_by_id = {
            str(item["candidate_id"]): item for item in candidate_audit
            if item.get("candidate_id") is not None
        }
        sel_cfg = _decide_selection(
            llm_cfg, instructions, mu, std, y_hist, model_cfg, len(rest),
            candidate_audit=candidate_audit, evidence=prompt_evidence,
            llm_enabled=llm_enabled, usage_context=usage_context)
        method = sel_cfg.get("method", "hybrid")
        print(f"[Agent2] selection config: {json.dumps(sel_cfg)}")

        # uncertainty_bonus = EXPLICIT extra exploration pressure ON TOP of the
        # acquisition (which already internalizes its own mean/std tradeoff). Passing
        # std again is deliberate and separately tunable: the Selection LLM's lever,
        # 0 disables it. (With model_uncertainties=None the weight was a silent no-op
        # — create_quality_scores' no-uncertainty branch ignores it.)
        quality = create_quality_scores(
            X_pool_normalized, y_hist, acq_scores, model_uncertainties=std, minimize=False,
            uncertainty_weight=sel_cfg.get("uncertainty_bonus", 0.2))
        for quality_rank, index in enumerate(
                np.argsort(quality)[::-1].astype(int).tolist(), start=1):
            candidate_audit[index]["selection_quality"] = round(
                float(quality[index]), 6)
            candidate_audit[index]["pool_quality_rank"] = quality_rank
        if method == "elitist":
            idx_list = np.argsort(quality)[::-1][:min(need, len(rest))].tolist()
        else:
            idx = select_points(
                X_pool_normalized, quality, method=method,
                n_points=min(need, len(rest)),
                config={"quality_weight": sel_cfg.get("quality_weight", 0.7),
                        "uncertainty_bonus": sel_cfg.get("uncertainty_bonus", 0.2)})
            idx_list = np.atleast_1d(idx).astype(int).tolist()
        unforced_indices = list(dict.fromkeys(idx_list))[:need]
        unforced_selection = kept + [rest[index] for index in unforced_indices]
        idx_list = _enforce_selection_quotas(
            idx_list, rest, quality, need, quotas, role_quotas)
        chosen = [rest[i] for i in idx_list][:need]
        # The search policy owns protected whole-row probes at the tail. Arrange the
        # already-scored probes there so final shaping does not replace another point.
        result = _probes_last(kept + chosen)
        if len(result) < num_runs:  # pad if selection returned few
            result += [p for p in rest if p not in chosen][:num_runs - len(result)]
            result = _probes_last(result)
        quota_forced_ids = _quota_forced_ids(
            result, unforced_selection, quotas)
        origin_counts = _origin_counts(result)
        sel_cfg["selected_origin_counts"] = origin_counts
        sel_cfg["quota_forced_candidate_ids"] = sorted(quota_forced_ids)
        sel_cfg["selected_candidate_ids"] = [
            item.get(CANDIDATE_ID_KEY) for item in result[:num_runs]]
        if candidate_lifecycle_path is not None:
            record_pool_stage(
                candidate_lifecycle_path, result[:num_runs], "agent2_selected",
                details=_selection_event_details(
                    result[:num_runs], method,
                    audit_by_id=audit_by_id,
                    quota_forced_ids=quota_forced_ids,
                    front_ids=front_ids,
                ),
            )
        print(f"[Agent2] Agglomerative '{method}' selection ({acquisition}-scored): "
              f"{len(result)} runs from hybrid pool of {len(kept) + len(rest)} "
              f"(DRP {len(pool)} + LHS {len(hybrid_lhs)}; origins={origin_counts})")
        return result[:num_runs], sel_cfg
    except LLMUsageError:
        raise
    except Exception as e:
        print(f"[Agent2][WARN] scoring/selection failed ({e}); elitist truncation.", file=sys.stderr)
        fallback = _fallback_select_with_quotas(
            kept, rest, num_runs, policy, quotas, role_quotas)
        quota_forced_ids = _quota_forced_ids(
            fallback, unforced_selection, quotas)
        origin_counts = _origin_counts(fallback)
        if candidate_lifecycle_path is not None:
            record_pool_stage(
                candidate_lifecycle_path, fallback, "agent2_selected",
                status="fallback", details=[{
                    **details, "reason": str(e),
                } for details in _selection_event_details(
                    fallback, "elitist",
                    audit_by_id=audit_by_id,
                    quota_forced_ids=quota_forced_ids,
                    front_ids=front_ids)])
        return fallback, {
            "method": "elitist", "note": f"fallback: {e}",
            "selected_origin_counts": origin_counts,
            "quota_forced_candidate_ids": sorted(quota_forced_ids),
            "selected_candidate_ids": [
                item.get(CANDIDATE_ID_KEY) for item in fallback],
        }


# ---------------------------------------------------------------------------
# Agent 3: Textual Gradient Critic (separate supervisor model)
# ---------------------------------------------------------------------------

def agent3_critic(sup_cfg: dict, summary: Dict[str, Any], agent1_cfg: Dict[str, Any],
                  instructions: Dict[str, str], *,
                  llm_enabled: bool = True,
                  usage_context=None) -> Tuple[str, Dict[str, str]]:
    """Agent3: supervisor critiques the iteration (gradient) and TextGrad-rewrites
    the instruction fragments. Returns (feedback, new_instructions)."""
    new_instr = dict(instructions)
    if not llm_enabled:
        print("[no-llm][Agent3] critic/TextGrad disabled; instructions unchanged.")
        return "", new_instr
    try:
        client, model, call_params = _resolve_client(sup_cfg)
    except Exception as e:
        print(f"[Agent3][WARN] supervisor unavailable ({e}); skipping critique.", file=sys.stderr)
        return "", new_instr

    authority = _authoritative_context(summary)
    ordinary_summary = {
        key: value for key, value in summary.items()
        if key not in _AUTHORITATIVE_EVIDENCE_KEYS
    }
    authority_json = _bounded_json_text(authority, 32000)
    ordinary_json = _bounded_json_text(ordinary_summary, 5000)
    critic_prompt = (
        "You are a critical reviewer of an LLM+Bayesian optimizer for the OpenROAD "
        "flow. Review the last iteration and produce a concise critique (the gradient) "
        "of how the agent should improve next time. Focus on feasibility (failed "
        "placement/routing), exploration vs exploitation balance, and whether the "
        "chosen configs match the data.\n\n"
        "Authoritative constrained-objective evidence (use this before judging "
        "quality or feasibility):\n"
        f"{authority_json}\n\n"
        "Bounded iteration summary:\n"
        f"{ordinary_json}\n\n"
        f"Agent1 chose configs:\n{json.dumps(agent1_cfg, indent=2)}\n\n"
        "Return 3-5 sentences of actionable critique."
    )
    try:
        msg = _chat(
            client, model, [{"role": "user", "content": critic_prompt}],
            call_params,
            usage_context=_usage_context(
                usage_context, agent="agent3", operation="critic"),
        )
        feedback = (msg.content or "").strip()
    except LLMUsageError:
        raise
    except Exception as e:
        print(f"[Agent3][WARN] critic call failed ({e}).", file=sys.stderr)
        return "", new_instr
    if not feedback:
        return "", new_instr
    print(f"[Agent3] Critique (gradient):\n{feedback}")

    # TextGrad: rewrite each instruction fragment using the critique as the gradient.
    for stage in ("model", "selection"):
        meta = (
            "You optimize a system instruction for an EDA optimization agent.\n"
            f"Current instruction: {instructions.get(stage, '')}\n"
            f"Critique (gradient): {feedback}\n"
            "Rewrite the instruction to address the critique. Keep it under 50 words. "
            "Return ONLY the new instruction text."
        )
        try:
            m = _chat(
                client, model, [{"role": "user", "content": meta}], call_params,
                usage_context=_usage_context(
                    usage_context, agent="agent3",
                    operation=f"textgrad_{stage}"),
            )
            txt = (m.content or "").strip()
            if txt:
                new_instr[stage] = txt
                print(f"[Agent3][TextGrad] updated '{stage}' instruction.")
        except LLMUsageError:
            raise
        except Exception as e:
            print(f"[Agent3][WARN] TextGrad rewrite of '{stage}' failed ({e}).", file=sys.stderr)
    return feedback, new_instr


def _best_feasible_params(history, objective, wl_base, ecp_base, w_wl, w_ecp):
    """Params of the best feasible run in history (None if none). Power-infeasible
    TNS_EVAL runs carry the 1e9 penalty and thus never win."""
    best_obj, best_params = None, None
    for h in history:
        if not h.get("params"):
            continue
        o = _objective_value(h["metrics"], objective, wl_base, ecp_base, w_wl, w_ecp)
        if (_is_feasible_objective(o, objective)
                and (best_obj is None or o < best_obj)):
            best_obj, best_params = o, h["params"]
    return best_params


def _instructions_path(work_dir: Path, platform: str, design: str) -> Path:
    return work_dir / "tmp" / f"agentic_prompts_{platform}_{design}.json"


def load_instructions(work_dir: Path, platform: str, design: str) -> Dict[str, str]:
    p = _instructions_path(work_dir, platform, design)
    if p.exists():
        try:
            d = json.loads(p.read_text())
            return {**DEFAULT_INSTRUCTIONS, **d}
        except Exception:
            pass
    return dict(DEFAULT_INSTRUCTIONS)


def save_instructions(work_dir: Path, platform: str, design: str, instr: Dict[str, str]):
    p = _instructions_path(work_dir, platform, design)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(instr, indent=2))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_agentic(config: dict, platform: str, design: str, objective: str,
                num_runs: int, history: List[Dict], weight_wl: float, weight_ecp: float,
                total_iters: int, work_dir: Path, *,
                resolved_history: Optional[List[Dict]] = None,
                routing_history: Optional[List[Dict]] = None,
                optimization_state: Optional[Dict[str, Any]] = None,
                optimization_state_path: Optional[Path] = None,
                policy_seed: Any = None,
                policy_plan_out: Optional[Dict[str, Any]] = None,
                llm_enabled: bool = True,
                usage_context: Optional[Mapping[str, Any]] = None) -> List[Dict]:
    design_cfg = get_design_config(config, platform, design)
    cons = {}
    for stage in ("synthesis", "placement"):
        cons.update(get_param_constraints(config, stage, design_cfg))
    clk_range = design_cfg["clock_period_range"] if design_cfg else [1.0, 10.0]
    cons["clk_period"] = {"type": "float", "range": clk_range, "description": "Clock period"}
    param_names = list(cons.keys())
    wl_base = design_cfg["baseline"]["wl_base"] if design_cfg else 1.0
    ecp_base = design_cfg["baseline"]["ecp_base"] if design_cfg else 1.0
    target_iteration = int((optimization_state or {}).get(
        "current_iteration",
        max((h.get("iteration", 0) for h in history), default=0))) + 1
    campaign_usage_context = dict(usage_context or {})
    campaign_usage_context.setdefault("scope", "inter_iteration")
    campaign_usage_context.setdefault("stage", "next_batch")
    campaign_usage_context.setdefault("iteration", target_iteration - 1)
    campaign_usage_context.setdefault("source_iteration", target_iteration - 1)
    campaign_usage_context.setdefault("target_iteration", target_iteration)
    campaign_id = str((optimization_state or {}).get("campaign_id")
                      or f"adhoc:{platform}:{design}")
    tracking_path = lifecycle_path(work_dir, target_iteration)
    cp0 = None
    try:
        cp0 = float((work_dir / "designs" / platform / design / "cp0.txt")
                    .read_text().strip())
    except (OSError, TypeError, ValueError):
        pass
    try:
        from common import _power_base

        model_score_records = load_model_score_evidence(
            work_dir / "backup_dir", platform, design,
            max(0, target_iteration - 1),
        )

        evidence = build_prompt_evidence(
            objective,
            history,
            resolved_history=resolved_history or (),
            routing_history=routing_history or (),
            optimization_state=optimization_state,
            constraints=cons,
            power_base=_power_base(platform, design),
            power_budget=config.get("power_budget"),
            cp0=cp0,
            model_score_records=model_score_records,
        )
        evidence.update(build_shared_prompt_context(
            config, platform, design, objective, evidence))
    except Exception as exc:
        print(f"[agentic][WARN] structured prompt evidence unavailable ({exc}).",
              file=sys.stderr)
        evidence = {}

    if optimization_state is not None and optimization_state.get("stop_requested"):
        print("[search-policy] stop requested; skipping Agent1/Agent2/Agent3.")
        return []

    routing_focus_controller = None

    def finalize_batch(candidate_batch: List[Dict]) -> List[Dict]:
        """Apply the shared policy after Agent2 selection and exploitation."""
        if optimization_state is None:
            shaped = candidate_batch[:num_runs]
            if not tracking_path.is_file():
                record_pool_stage(
                    tracking_path, shaped, "candidate_pool",
                    campaign_id=campaign_id, iteration=target_iteration)
            bind_slots(tracking_path, shaped, stage="search_policy_shaped")
            return shaped
        shaped, plan = shape_next_batch(
            candidate_batch,
            clean_history=history,
            resolved_history=resolved_history or (),
            routing_history=routing_history or (),
            state=optimization_state,
            full_constraints=cons,
            num_runs=num_runs,
            seed=policy_seed,
            policy_config=config,
            routing_agentic=True,
            routing_agentic_controller=routing_focus_controller,
        )
        plan["llm_enabled"] = bool(llm_enabled)
        if policy_plan_out is not None:
            policy_plan_out.clear()
            policy_plan_out.update(plan)
        elif optimization_state.get("enabled") and optimization_state_path is not None:
            # Backward-compatible direct run_agentic callers have no CSV commit step.
            persist_batch_plan(optimization_state_path, optimization_state, plan)
        print(
            f"[search-policy] final batch mode={plan.get('mode')}, "
            f"counts={plan.get('counts', {})}, "
            f"protected_replay_slots={plan.get('protected_replay_slots', [])}, "
            f"protected_probe_slots={plan.get('protected_probe_slots', [])}, "
            f"protected_focus_control_slots="
            f"{plan.get('protected_focus_control_slots', [])}"
        )
        if not tracking_path.is_file():
            record_pool_stage(
                tracking_path, candidate_batch, "candidate_pool",
                campaign_id=campaign_id, iteration=target_iteration)
        if plan.get("mode") == ROUTING_FOCUS:
            # Focus selection happens inside shape_next_batch. Record the resulting
            # proposals rather than the placeholder seed rows, then record the
            # deliberately skipped global exploitation pass before slot binding.
            record_pool_stage(
                tracking_path, shaped[:num_runs], "agent2_selected",
                details={
                    "mode": ROUTING_FOCUS,
                    "selection": "parent_conditioned_focus",
                    "protected_candidate_slots": plan.get(
                        "protected_candidate_slots", []),
                },
            )
            record_pool_stage(
                tracking_path, shaped[:num_runs], "exploit_quota",
                details={
                    "mode": ROUTING_FOCUS,
                    "quota_applied": 0,
                    "no_op_reason": "focus_policy_owns_final_proposals",
                },
            )
        bind_slots(
            tracking_path,
            shaped[:num_runs],
            stage="search_policy_shaped",
            details=plan.get("candidate_slots", {}),
        )
        return shaped[:num_runs]

    if not history:
        print("[agentic] No history; falling back to plain generation.")
        params = generate_next_iteration_params(
            config, platform, design, objective, num_runs, history,
            weight_wl, weight_ecp, total_iters,
            candidate_campaign_id=campaign_id,
            candidate_iteration=target_iteration,
            candidate_lifecycle_path=tracking_path,
            prompt_evidence=evidence,
            llm_enabled=llm_enabled,
            usage_context=campaign_usage_context)
        return finalize_batch(params)

    llm_cfg = dict(config.get("llm", {}))
    sup_cfg = dict(config.get("supervisor", llm_cfg))
    if not llm_enabled:
        llm_cfg["enabled"] = False
        sup_cfg["enabled"] = False
    ag_cfg = config.get("agentic", {})
    max_iters = ag_cfg.get("react_max_iters", 2)
    pool_mult = ag_cfg.get("candidate_pool_mult", 2)
    lhs_mult = ag_cfg.get("lhs_pool_mult", 8)

    instructions = (load_instructions(work_dir, platform, design)
                    if llm_enabled else dict(DEFAULT_INSTRUCTIONS))
    # Sanitize persisted directives against the data: any clk_period range claim that
    # excludes the best-known feasible config is dropped (observed 'clk_period>=500'
    # drove the population away from the 225-380 ps region where every winner lives).
    from common import sanitize_instructions
    best_p = _best_feasible_params(history, objective, wl_base, ecp_base,
                                   weight_wl, weight_ecp)
    instructions = sanitize_instructions(instructions, best_p)
    if (optimization_state is not None
            and optimization_state.get("mode") == "ROUTING_FOCUS"
            and any(name in cons for name in ROUTING_PARAMETERS)):
        routing_focus_controller = RoutingFocusAgenticController(
            llm_cfg, instructions, evidence=evidence,
            llm_enabled=llm_enabled,
            usage_context={**campaign_usage_context, "stage": "routing_focus"})
    summary = summarize_runs(history, objective, wl_base, ecp_base,
                             weight_wl, weight_ecp, param_names)
    summary.update(evidence)
    print(f"[agentic] iter {summary['current_iteration']}: "
          f"{summary['n_feasible']}/{summary['n_runs']} feasible, "
          f"best={summary['best_objective']}")

    if (optimization_state is not None
            and optimization_state.get("mode") == "ROUTING_FOCUS"
            and any(name in cons for name in ROUTING_PARAMETERS)):
        # The policy will replace every non-reserved row with an exact control,
        # parent-conditioned 2D proposal, or full-space probe. Running the global
        # global Agent1/Agent2 first would therefore spend LLM/GP work on points that do
        # not reach the CSV. A complete incumbent-shaped seed batch is sufficient.
        from modelfuncs import clip_params
        seed_params = (
            dict((optimization_state.get("best_clean_replay") or {}).get("params") or {})
            or dict(best_p or {}))
        for name, spec in cons.items():
            if seed_params.get(name) is None:
                low, high = spec["range"]
                seed_params[name] = (float(low) + float(high)) / 2.0
        seed_params = clip_params(seed_params, cons)
        seed_params = assign_batch_identity(
            [dict(seed_params) for _ in range(num_runs)],
            campaign_id,
            target_iteration,
            origin="replay",
            proposal_keys=[f"routing-focus-seed:{index + 1}"
                           for index in range(num_runs)],
        )
        record_pool_stage(
            tracking_path, seed_params, "candidate_pool",
            campaign_id=campaign_id, iteration=target_iteration,
            details={"mode": "ROUTING_FOCUS", "placeholder_only": True})
        print("\n=== ROUTING_FOCUS: shared Inspect -> Model -> family GPs -> Selection ===")
        params = finalize_batch(seed_params)

        focus_meta = ((policy_plan_out or {}).get("routing_focus_model", {})
                      if policy_plan_out is not None else {})
        tools_meta = (focus_meta.get("agentic_tools", {})
                      if isinstance(focus_meta, dict) else {})
        critic_cfg = {
            "inspection": tools_meta.get("inspection_config", {}),
            "model": tools_meta.get("model_config", {}),
            "selection": tools_meta.get("selection_config", {}),
        }
        summary["routing_focus_agentic"] = tools_meta
        print("\n=== Agent3: Textual Gradient Critic ===")
        _, new_instr = agent3_critic(
            sup_cfg, summary, critic_cfg, instructions,
            llm_enabled=llm_enabled,
            usage_context={**campaign_usage_context, "stage": "routing_focus"})
        if llm_enabled:
            save_instructions(work_dir, platform, design, new_instr)
        return params[:num_runs]

    # Build param matrix X / objective y for the model-stage GPR ReAct loop, and a
    # runner that executes the real inspectfuncs analysis with a chosen config.
    X, y = _build_xy(history, param_names, cons, objective, wl_base, ecp_base,
                     weight_wl, weight_ecp)
    inspect_runner = lambda cfg: run_inspection(
        history, param_names, cons, objective, wl_base, ecp_base,
        weight_wl, weight_ecp, cfg)

    # Agent 1: ORFO-order stages (Inspection -> Model[+ReAct GPR loop] -> Selection)
    print("\n=== Agent1: Inspection -> Model(+ReAct GPR) ===")
    agent1_cfg, inspection = agent1_stages(
        llm_cfg, summary, X, y, instructions, max_iters, inspect_runner,
        llm_enabled=llm_enabled, usage_context=campaign_usage_context)
    feature_weights = inspection.get("feature_weights") if inspection else None
    if inspection:
        summary["inspection_analysis"] = inspection  # context for Agent3 critic

    # Agent 3: generate next batch (and decide the selection config from scores)
    print("\n=== Agent2: Param Set Generator (generate + selection) ===")
    params, sel_cfg = agent2_generate(
        config, platform, design, objective, num_runs, history,
        weight_wl, weight_ecp, total_iters, agent1_cfg, cons, param_names,
        wl_base, ecp_base, pool_mult, lhs_mult, feature_weights,
        llm_cfg=llm_cfg, instructions=instructions,
        resolved_history=resolved_history,
        routing_history=routing_history,
        optimization_state=optimization_state,
        policy_seed=policy_seed,
        candidate_campaign_id=campaign_id,
        candidate_iteration=target_iteration,
        candidate_lifecycle_path=tracking_path,
        prompt_evidence=evidence,
        llm_enabled=llm_enabled,
        usage_context=campaign_usage_context)
    agent1_cfg["selection"] = sel_cfg  # record Agent2's selection for the critic

    # Agent2 enforces exploit/full-probe quotas while points still have GPR scores.
    # Do not overwrite selected points here: doing so was the scored-vs-executed bug.
    params = params[:num_runs]
    record_pool_stage(
        tracking_path, params, "exploit_quota",
        details={"post_selection_overwrite": False,
                 "selected_origin_counts": sel_cfg.get("selected_origin_counts", {})})

    # The shared campaign policy owns the final slots. Apply it only after Agent2's
    # diversity selection and the unconditional exploitation quota, otherwise either
    # layer could discard the clean incumbent or an exact-replay slot.
    params = finalize_batch(params)

    # Agent 2: critic + TextGrad (improves NEXT iteration's prompts)
    print("\n=== Agent3: Textual Gradient Critic ===")
    _, new_instr = agent3_critic(
        sup_cfg, summary, agent1_cfg, instructions,
        llm_enabled=llm_enabled, usage_context=campaign_usage_context)
    if llm_enabled:
        save_instructions(work_dir, platform, design, new_instr)

    return params[:num_runs]


def _csv_lifecycle_details(csv_path: Path, row_count: int,
                           candidate_slots: Any) -> List[Dict[str, Any]]:
    """Bind every csv_written event to the exact immutable CSV artifact."""
    artifact = Path(csv_path)
    csv_sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
    planned_slots = candidate_slots if isinstance(candidate_slots, list) else []
    details = []
    for run_id in range(1, int(row_count) + 1):
        slot_detail = (
            planned_slots[run_id - 1]
            if run_id <= len(planned_slots)
            and isinstance(planned_slots[run_id - 1], Mapping)
            else {}
        )
        details.append({
            **dict(slot_detail),
            "csv_path": str(artifact.resolve()),
            "csv_sha256": csv_sha256,
            "row_number": run_id,
        })
    return details


def main():
    parser = argparse.ArgumentParser(
        description="Agentic (ReAct + TextGrad Critic + generate) inter-iteration optimizer.")
    parser.add_argument("platform")
    parser.add_argument("design")
    parser.add_argument("objective", choices=["wl", "ecp", "combo", "TNS_EVAL"])
    parser.add_argument("num_runs", type=int)
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--total-iterations", type=int, default=6)
    parser.add_argument("--weight-wl", type=float, default=0.5)
    parser.add_argument("--weight-ecp", type=float, default=0.5)
    parser.add_argument("--drp-config", type=Path,
                        default=Path(__file__).parent / "drp_config.json")
    parser.add_argument("--work-dir", type=Path, default=Path(__file__).parent)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--state-only", action="store_true",
                        help="Update campaign best/state without running Agent1/2/3")
    parser.add_argument("--no-llm", action="store_true",
                        help="Keep the agentic numerical pipeline but disable every "
                             "external LLM request")
    args = parser.parse_args()

    if args.no_llm:
        os.environ["DRP_NO_LLM"] = "1"
        print("[no-llm] external LLM guidance disabled; numerical Agentic/BO "
              "components remain active.")

    from modelfuncs import seed_everything   # reproducible RNG (see agent.py)
    derived_seed = seed_everything(
        os.environ.get("DRP_SEED"), os.environ.get("DRP_ITER", ""),
        args.platform, args.design, "optimize_agentic")

    config = load_config(args.drp_config)
    # Activate the TNS_EVAL power-budget constraint (default off) for _objective_value.
    global _POWER_BUDGET, _POWER_BASE
    from common import _power_base
    _POWER_BUDGET = config.get("power_budget")
    _POWER_BASE = _power_base(args.platform, args.design)
    backup_dir = args.work_dir / "backup_dir"
    history = load_iteration_history(backup_dir, args.platform, args.design, args.iteration)
    resolved_history = load_resolved_history(
        backup_dir, args.platform, args.design, args.iteration)
    routing_history = load_stage_history(
        backup_dir, args.platform, args.design, args.iteration, "routing")
    print(
        f"Loaded {len(history)} clean, {len(resolved_history)} resolved, and "
        f"{len(routing_history)} routing-history entries from "
        f"{args.iteration} iterations"
    )

    design_cfg = get_design_config(config, args.platform, args.design)
    wl_base = design_cfg["baseline"]["wl_base"] if design_cfg else 1.0
    ecp_base = design_cfg["baseline"]["ecp_base"] if design_cfg else 1.0
    state_path = (args.work_dir / "designs" / args.platform / args.design
                  / "optimization_state.json")
    campaign_id = None
    try:
        campaign_id = json.loads(
            (backup_dir / args.platform / args.design
             / "campaign_manifest.json").read_text()).get("campaign_id")
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    optimization_state = update_optimization_state(
        state_path,
        current_iteration=args.iteration,
        objective=args.objective,
        clean_history=history,
        resolved_history=resolved_history,
        routing_history=routing_history,
        policy_config=config,
        power_budget=_POWER_BUDGET,
        power_base=_POWER_BASE,
        wl_base=wl_base,
        ecp_base=ecp_base,
        weight_wl=args.weight_wl,
        weight_ecp=args.weight_ecp,
        num_runs=args.num_runs,
        platform=args.platform,
        design=args.design,
        campaign_id=campaign_id,
        persist=False,
    )

    def best_label(key: str) -> str:
        best = optimization_state.get(key)
        if not isinstance(best, dict) or best.get("objective") is None:
            return "none"
        return (f"{float(best['objective']):.6g}@iter{best.get('iteration')}"
                f"/run{best.get('run_id')}")

    print(
        f"[search-policy] mode={optimization_state.get('mode')}, "
        f"clean_best={best_label('best_clean_replay')}, "
        f"observed_best={best_label('best_observed_effective')}, "
        f"routing_best={best_label('best_routing_child')}, "
        f"config_reproducible_best={best_label('best_config_reproducible')}, "
        f"pending_replays={len(optimization_state.get('pending_replays', []))}, "
        f"stop_requested={optimization_state.get('stop_requested', False)}"
    )
    if args.state_only:
        persist_optimization_state(state_path, optimization_state)
        print("[search-policy] state-only update complete; Agent1/Agent2/Agent3 skipped.")
        return
    if optimization_state.get("stop_requested"):
        persist_optimization_state(state_path, optimization_state)
        print("[search-policy] campaign stop requested; no next batch is generated.")
        return

    batch_plan: Dict[str, Any] = {}
    params_list = run_agentic(
        config=config, platform=args.platform, design=args.design,
        objective=args.objective, num_runs=args.num_runs, history=history,
        weight_wl=args.weight_wl, weight_ecp=args.weight_ecp,
        total_iters=args.total_iterations, work_dir=args.work_dir,
        resolved_history=resolved_history, routing_history=routing_history,
        optimization_state=optimization_state,
        optimization_state_path=state_path, policy_seed=derived_seed,
        policy_plan_out=batch_plan,
        llm_enabled=not args.no_llm)

    if args.output:
        csv_path = args.output
    else:
        csv_path = (args.work_dir / "designs" / args.platform / args.design
                    / f"{args.platform}_{args.design}.csv")

    order = []
    for stage in ("synthesis", "placement"):
        order += list(get_param_constraints(config, stage, design_cfg).keys())
    order += ["clk_period"]
    write_csv(params_list, csv_path, order)
    csv_event_details = _csv_lifecycle_details(
        csv_path, len(params_list), batch_plan.get("candidate_slots", []))
    bind_slots(
        lifecycle_path(args.work_dir, args.iteration + 1),
        params_list,
        stage="csv_written",
        details=csv_event_details,
    )
    optimization_state = persist_batch_plan(
        state_path, optimization_state, batch_plan,
        csv_path=csv_path,
        target_iteration=args.iteration + 1,
        expected_rows=args.num_runs,
    )
    print(f"[search-policy] committed CSV contract: "
          f"{optimization_state.get('next_batch_contract', {})}")


if __name__ == "__main__":
    main()
