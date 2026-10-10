"""Shared DRP-Agent utilities.

Extracted from agent.py (config/LLM helpers) and optimize.py (constrained-objective
helpers) so both live in one dependency-light module (no numpy/sklearn). This breaks
the optimize <-> agent import cycle: optimize.py and agent.py both import these from
`common` instead of from each other. agent.py / optimize.py re-export the names so
existing `from agent import ...` / `from optimize import ...` call sites keep working.
"""
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from llm_usage import LLMUsageError
from platform_model import tracked_completion
from llm_client import create_llm_client
from prompts import SYSTEM_PROMPT


# ─── Config ──────────────────────────────────────────────────────────────────
def load_config(config_path: Path) -> dict:
    """Load DRP configuration."""
    with open(config_path) as f:
        return json.load(f)


def get_design_config(config: dict, platform: str, design: str) -> Optional[dict]:
    """Get design-specific configuration."""
    for cfg in config["configurations"]:
        if cfg["platform"] == platform and cfg["design"] == design:
            return cfg
    return None


def get_param_constraints(config: dict, stage: str,
                          design_cfg: Optional[dict] = None) -> Dict[str, dict]:
    """Parameter constraints for a stage, with optional design-specific range overrides."""
    base = config["parameter_constraints"].get(stage, {})
    constraints = {name: dict(info) for name, info in base.items()}  # copy
    if design_cfg:
        override_key = f"{stage}_range_override"
        for name, new_range in design_cfg.get(override_key, {}).items():
            if name in constraints:
                constraints[name]["range"] = new_range
    return constraints


# ─── LLM ─────────────────────────────────────────────────────────────────────
def external_llm_enabled(config_block: Optional[dict] = None) -> bool:
    """Return False when the campaign explicitly forbids external LLM requests."""
    env_value = os.environ.get("DRP_NO_LLM", "").strip().lower()
    if env_value in {"1", "true", "yes", "on"}:
        return False
    return bool((config_block or {}).get("enabled", True))


def call_llm(prompt: str, config: dict, *,
             usage_context: Optional[Mapping[str, Any]] = None) -> Optional[str]:
    """Call the selected LLM transport for parameter suggestions."""
    llm_config = config.get("llm", {})
    if not external_llm_enabled(llm_config):
        print("[LLM] external API disabled; using numerical fallback.",
              file=sys.stderr)
        return None
    model = llm_config.get("model", "gpt-4o")
    temperature = llm_config.get("temperature", 0.7)
    max_tokens = llm_config.get("max_tokens", 4096)

    try:
        client = create_llm_client(llm_config)
        create_kwargs = dict(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        response = tracked_completion(client, create_kwargs, usage_context)
        return response.choices[0].message.content
    except ImportError:
        print("[WARN] openai package not installed. Falling back to sampling.",
              file=sys.stderr)
        return None
    except LLMUsageError:
        # Usage accounting is an experiment artifact contract. Do not silently make
        # an external request whose token cost cannot be reconciled later.
        raise
    except Exception as e:
        print(f"[WARN] LLM call failed: {e}. Falling back to sampling.", file=sys.stderr)
        return None


def parse_llm_json(response: str) -> Optional[List[Dict]]:
    """Extract a JSON array from LLM response text."""
    if response is None:
        return None
    json_block = re.search(r'```(?:json)?\s*\n?(.*?)```', response, re.DOTALL)
    if json_block:
        text = json_block.group(1).strip()
    else:
        array_match = re.search(r'\[.*\]', response, re.DOTALL)
        if array_match:
            text = array_match.group(0)
        else:
            return None
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return None


# ─── Constrained-objective helpers (TNS_EVAL + power budget) ─────────────────
# A run with no valid final metric (route/placement failed) becomes a large-penalty
# observation instead of being dropped, so the surrogate/LLM steer away from that
# infeasible region. Expressed as a multiple of the design baseline (or ~1.0 combo).
FAILURE_PENALTY_MULT = 5.0

# Additive penalty for TNS_EVAL runs that violate the power budget: large enough to
# rank any power-infeasible run below any feasible one while keeping a |TNS| gradient
# within the infeasible set. GPR normalizes y, so the magnitude doesn't distort the fit.
POWER_VIOLATION_PENALTY = 1.0e9


def _finite_float(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def is_feasible_objective_value(value, objective):
    """Whether an objective value represents a completed, constraint-feasible run."""
    number = _finite_float(value)
    return number is not None and (
        objective != "TNS_EVAL" or number < POWER_VIOLATION_PENALTY)


def _tns_base(design_cfg, platform, design):
    """Baseline |TNS| (written by eval_tns.sh to designs/<p>/<d>/tns_base.txt) used as
    the TNS_EVAL penalty scale. Large fallback if not available yet."""
    try:
        p = Path(__file__).parent / "designs" / platform / design / "tns_base.txt"
        if p.exists():
            v = _finite_float(p.read_text().strip())
            if v is not None and v > 0:
                return v
    except Exception:
        pass
    return 1.0e6


def _power_base(platform, design):
    """Baseline (run_1) power at CP_0 (W) from designs/<p>/<d>/power_base.txt. None if
    unavailable (constraint then inactive)."""
    try:
        p = Path(__file__).parent / "designs" / platform / design / "power_base.txt"
        if p.exists():
            v = _finite_float(p.read_text().strip())
            if v is not None and v > 0:
                return v
    except Exception:
        pass
    return None


# Numeric clk_period directives inside free-text agent instructions, e.g.
# "clk_period>=500" / "clk_period ≤ 300".
_CLK_DIRECTIVE = re.compile(
    r'[*_`]*clk_period[*_`]*\s*(>=|<=|≥|≤|>|<)\s*([0-9]+(?:\.[0-9]+)?)')


def sanitize_instructions(instructions: Dict[str, str],
                          best_params: Optional[Dict[str, float]]) -> Dict[str, str]:
    """Drop numeric clk_period directives from persisted agent instructions when they
    would EXCLUDE the best-known feasible config. TextGrad persists free-text advice
    across iterations; an observed 'clk_period>=500' directive (while every
    baseline-beating config used 225-380 ps) steered 54-74% of the population into the
    degenerate slow-clock region for 10 straight iterations. Data beats prose: any
    range claim that contradicts the current best is removed (with a warning)."""
    best_clk = (best_params or {}).get("clk_period")
    if best_clk is None or not instructions:
        return instructions
    out = {}
    for key, text in instructions.items():
        if not isinstance(text, str):
            out[key] = text
            continue
        new_text = text
        for m in list(_CLK_DIRECTIVE.finditer(text)):
            op, bound = m.group(1), float(m.group(2))
            excludes = ((op in (">=", ">", "≥") and best_clk < bound) or
                        (op in ("<=", "<", "≤") and best_clk > bound))
            if excludes:
                print(f"[instructions][WARN] dropping persisted directive "
                      f"'{m.group(0)}' from '{key}': it excludes the best-known "
                      f"config (clk_period={best_clk:.2f}).", file=sys.stderr)
                new_text = new_text.replace(m.group(0), "clk_period (see data)")
        out[key] = new_text
    return out


def tns_eval_obj(m, power_budget=None, power_base=None):
    """Constrained TNS_EVAL objective for one run's metrics dict.

    Base = |TNS| at CP_0 (minimize). With an active power budget, a run whose CP_0
    power exceeds (1 + power_budget) * power_base gets POWER_VIOLATION_PENALTY added, so
    it ranks below every feasible run but still orders by |TNS| internally. Returns
    None if TNS is missing (failed run -> penalty handled upstream).

    tns_source guard: this helper only sees FINAL metrics, and CP_0 exists from
    iter-1 final onward — so a 'native' (own-clock) TNS here means that run's CP_0
    eval FAILED. Own-clock TNS is not comparable to the CP_0 objective (typically far
    smaller under a relaxed clock), so treat it as missing rather than let it
    masquerade as a great objective value."""
    if m.get("tns_source") == "native":
        return None
    tns = _finite_float(m.get("tns"))
    if tns is None:
        return None
    obj = abs(tns)
    finite_power_base = _finite_float(power_base)
    if power_budget is not None and finite_power_base is not None and finite_power_base > 0:
        budget = _finite_float(power_budget)
        p = _finite_float(m.get("power"))
        # Under an active budget a MISSING power means feasibility is UNKNOWN — treat it
        # as infeasible (penalize) rather than feasible, so a run whose CP_0 power wasn't
        # measured (extraction failed) cannot slip past the hard constraint and win the
        # objective / predictor baseline.
        if budget is None or p is None or p > (1.0 + budget) * finite_power_base:
            obj += POWER_VIOLATION_PENALTY
    return obj
