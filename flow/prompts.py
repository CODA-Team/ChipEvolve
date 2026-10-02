"""
LLM prompt templates for DRP-Agent parameter generation.

Provides stage-specific prompts for CTS and routing parameter optimization.
"""

import json

SYSTEM_PROMPT = """You are an expert EDA (Electronic Design Automation) engineer \
specializing in OpenROAD physical design optimization. You have deep knowledge of:
- Clock Tree Synthesis (CTS) parameter tuning
- Global and detailed routing optimization
- The relationship between placement quality and downstream stages
- How different parameters affect wirelength, timing, and overall QoR

When recommending parameters, consider:
1. The current metrics of surviving runs (including TNS, power, and predictor scores when present)
2. The parameter ranges and constraints
3. Domain knowledge about parameter interactions
4. The optimization objective (minimize wl, ecp, combo, or constrained TNS_EVAL)

Always return parameters as valid JSON."""

CTS_PARAM_PROMPT = """## Task: Generate CTS Parameters for All Run Slots

### Context
After the placement stage, we performed Doomed Run Prediction (DRP). Victim slots
have inherited their selected survivor checkpoint/config; survivor slots keep their
own state. Generate one CTS row for every resulting slot. With a learned predictor,
the clone selection order can differ from the raw optimization objective.

### Platform & Design
- Platform: {platform}
- Design: {design}
- Optimization Objective: {objective}

### Active Optimization Context
This shared context defines the current goal and reference point. The exact
objective contract below remains authoritative if any descriptive text conflicts.
{optimization_context}

### PDK Profile
Use these technology facts when judging density, pin access, CTS, and routing risk.
Do not invent PDK properties that are not present here.
{pdk_context}

### Design Profile
Use these workload and implementation characteristics to interpret the run metrics.
{design_context}

### Exact Objective Contract (authoritative)
{objective_contract}

### Outcome Classification
Runs are separated into feasible, power_infeasible, and flow_failed. Do not treat
a completed power-infeasible run as a placement/routing failure.
{run_classifications}

### Best Known Feasible Configurations
{top_successful_configs}

### Stratified Best Records
{stratified_bests}

### Basin / Coverage Summary
{basin_summary}

### Parameter Distributions
{parameter_distributions}

### Distance / Novelty Information
Distances are normalized to the configured parameter ranges unless stated otherwise.
{distance_info}

### Current Metrics (in effective DRP ranking order, first = most promising)
{metrics_table}

### Conditioning Source for Each Run Slot
{source_runs_info}

### Source -> Target Execution Map
When edge records are supplied, output object i MUST correspond to edge_index i.
Use the edge's upstream context when choosing CTS parameters. A self mapping retains
the existing candidate identity; a clone mapping has a planned lineage child and a
displaced target identity. Never
infer a missing candidate ID or parent family. Respect mapping_scope: a
candidate_pool_conditioning edge conditions a proposal but is not yet a final slot.
{source_target_edges}

### CTS Parameters to Generate
For each of the {num_params_to_generate} run slots, suggest CTS parameters:
{param_ranges}

### Guidelines
- The {objective} metric should be minimized
- Consider that good placement (low wl/ecp after placement) often benefits from \
moderate CTS clustering
- CTS_CLUSTER_SIZE: larger values create fewer, bigger clusters (can reduce skew \
but increase wirelength)
- CTS_CLUSTER_DIAMETER: larger diameter allows more spatial flexibility in clustering
- For wl objective: favor moderate cluster sizes and diameters
- For ecp objective: favor clustering choices that preserve timing and clock quality
- For combo: balance both considerations
- For TNS_EVAL: reduce absolute TNS while avoiding choices likely to worsen power;
  use the displayed predictor probabilities as relative evidence, not ground truth
- The exact objective contract above overrides generic guidance. Compare TNS only at
  the same CP_0 and never improve TNS by violating the stated power limit
- Use successful basins as multiple centers; do not collapse every proposal onto the
  single current incumbent. Prefer novel, feasible-distance proposals when available

### Output Format
Return a JSON array of {num_params_to_generate} objects, each with keys: \
{param_keys}

Example:
```json
[
  {{"CTS_CLUSTER_SIZE": 25, "CTS_CLUSTER_DIAMETER": 100}},
  ...
]
```"""

ROUTING_PARAM_PROMPT = """## Task: Generate Routing Parameters for All Run Slots

### Context
After the CTS stage, we performed Doomed Run Prediction (DRP). Victim slots have
inherited their selected survivor checkpoint/config; survivor slots keep their own
state. Generate one routing row for every resulting slot. With a learned predictor,
clone selection can differ from the raw optimization objective.

### Platform & Design
- Platform: {platform}
- Design: {design}
- Optimization Objective: {objective}

### Active Optimization Context
This shared context defines the current goal and reference point. The exact
objective contract below remains authoritative if any descriptive text conflicts.
{optimization_context}

### PDK Profile
Use these technology facts when judging layer capacity, pin access, congestion,
and detour risk. Do not invent PDK properties that are not present here.
{pdk_context}

### Design Profile
Use these workload and implementation characteristics to interpret the run metrics.
{design_context}

### Exact Objective Contract (authoritative)
{objective_contract}

### Outcome Classification
Runs are separated into feasible, power_infeasible, and flow_failed. Do not treat
a completed power-infeasible run as a placement/routing failure.
{run_classifications}

### Best Known Feasible Configurations
{top_successful_configs}

### Stratified Best Records
{stratified_bests}

### Basin / Coverage Summary
{basin_summary}

### Parameter Distributions
{parameter_distributions}

### Distance / Novelty Information
Distances are normalized to the configured parameter ranges unless stated otherwise.
{distance_info}

### Current Metrics (in effective DRP ranking order, first = most promising)
{metrics_table}

### Conditioning Source for Each Run Slot
{source_runs_info}

### Source -> Target Execution Map
When edge records are supplied, output object i MUST correspond to edge_index i.
Use the edge's upstream context when choosing routing parameters. A self mapping
retains the existing candidate identity; a clone mapping has a planned lineage child
and a displaced target identity. Never
infer a missing candidate ID or parent family. Respect mapping_scope: a
candidate_pool_conditioning edge conditions a proposal but is not yet a final slot.
{source_target_edges}

### Routing Parameters to Generate
For each of the {num_params_to_generate} run slots, suggest routing parameters:
{param_ranges}

### Guidelines
- The {objective} metric should be minimized
- PIN_LAYER_ADJUST: routing resource adjustment for the pin layers (metal2/3)
  - Lower values free up capacity on lower layers, easing pin-access congestion
  - Higher values reserve more of those layers, which can push congestion upward
- ABOVE_LAYER_ADJUST: routing resource adjustment for metal4 and above
  - Lower values increase available capacity on upper layers for global routing
  - Higher values reduce upper-layer resources, increasing congestion risk
- For wl objective: keep enough capacity to avoid detours that inflate wirelength
- For ecp objective: ensure enough routing resources for timing-critical nets
- For combo: balance congestion and timing
- For TNS_EVAL: reduce absolute TNS without trading it for a power regression;
  use the displayed predictor probabilities as relative evidence, not ground truth
- The exact objective contract above overrides generic guidance. Compare TNS only at
  the same CP_0 and never improve TNS by violating the stated power limit
- Use successful basins as multiple centers; do not collapse every proposal onto the
  single current incumbent. Prefer novel, feasible-distance proposals when available

### Output Format
Return a JSON array of {num_params_to_generate} objects, each with keys: \
{param_keys}

Example:
```json
[
  {{"PIN_LAYER_ADJUST": 0.5, "ABOVE_LAYER_ADJUST": 0.5}},
  ...
]
```"""

OPTIMIZE_PROMPT = """## Task: Generate Parameters for Next Iteration

### Context
Iteration {iteration} has completed. You need to generate {num_runs} parameter sets \
for the next iteration based on the observed results.

### Platform & Design
- Platform: {platform}
- Design: {design}
- Optimization Objective: {objective}

### Active Optimization Context
This shared context defines the current goal, baseline, and feasible incumbent. The
exact objective contract below remains authoritative if descriptive text conflicts.
{optimization_context}

### PDK Profile
Use these technology facts when judging legal ranges and physical-design risk. Do
not invent PDK properties that are not present here.
{pdk_context}

### Design Profile
Use these workload and implementation characteristics to interpret historical QoR.
{design_context}

### Exact Objective Contract (authoritative)
{objective_contract}

### Outcome Classification
Runs are separated into feasible, power_infeasible, and flow_failed. A
power_infeasible run completed the flow and must not be described as a routing or
placement failure.
{run_classifications}

### Top Successful Configurations
These records preserve the successful parameter-to-objective mapping.
{top_successful_configs}

### Stratified Best Records
Keep clean/replay, observed/effective, routing-child, and reproducible bests distinct.
{stratified_bests}

### Basin / Coverage Summary
{basin_summary}

### Parameter Distributions
{parameter_distributions}

### Distance / Novelty Information
Distances are normalized to the configured parameter ranges unless stated otherwise.
{distance_info}

### Source -> Target / Replay Edges
When edge records are supplied, preserve their upstream context and do not attribute
a child's final metric to the wrong parent configuration.
{source_target_edges}

### Results from Current Iteration
{results_table}

### Parameter History (all iterations so far)
{history_summary}

### Configurations Requiring Caution
Use Outcome Classification above to distinguish true flow failures from completed
but power-infeasible runs. Avoid repeated, evidenced flow-failure neighborhoods;
do not turn one failure or a small power violation into an unsupported hard exclusion.
{failed_configs}

### Parameters to Generate
Generate {num_runs} complete upstream parameter sets. These values are fixed before
placement; CTS and post-CTS routing parameters will be generated later from stage
metrics and MUST NOT appear in this response.

Synthesis parameters:
{synthesis_ranges}

Placement parameters:
{placement_ranges}

Clock period range: {clk_period_range}

### Guidelines
- Analyze which parameter combinations performed well and why
- Balance exploration (trying new regions) with exploitation (refining good regions)
- Treat the objective contract as authoritative. For TNS_EVAL, compare absolute TNS
  only at the shared CP_0 and enforce power <= power_limit before comparing TNS
- Use top successful configurations and stratified bests as multiple exploitation
  centers. Preserve some candidates in distinct or under-sampled basins instead of
  collapsing the batch onto one incumbent
- Use normalized distance and coverage information to distinguish genuinely novel
  candidates from duplicates or tiny perturbations
- Exploration is annealed over the campaign: aim for ~{exploit_pct}% exploitation
  (refine / stay close to the best known feasible configurations) and only
  ~{explore_pct}% exploration (undersampled regions). In late iterations, when the
  exploration share is small, do NOT propose aggressive full-range values — keep
  proposals near the feasible configs that have routed successfully.
- Consider parameter interactions (e.g., high core utilization may need more padding)
- Do NOT repeat parameter sets in evidenced flow-failure neighborhoods above.
  A config that minimizes wirelength but fails to route is worthless — feasibility
  (completing place+route) takes priority over a marginally shorter wirelength. Treat
  power-infeasible completed runs separately: improve their power margin instead of
  assuming the surrounding region cannot route.
  When in doubt, relax density/routing pressure: lower CORE_UTILIZATION or
  PLACE_DENSITY_LB_ADDON, add CELL_PAD, and avoid aggressive
  FLOORPLAN_PIN/FLOORPLAN_ABOVE_LAYER_ADJUST values.
- The {objective} metric should be minimized

### Output Format
Return ONLY a JSON array of {num_runs} objects, each with ALL parameter keys:
{all_param_keys}

Include "clk_period" as a key for each set.
"""


def _metric_value(row: dict, key: str):
    """Read prompt metrics from either flat rows or nested history records."""
    metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else row
    aliases = {
        "TNS_EVAL": ("TNS_EVAL", "tns", "setup_tns_ns"),
        "power": ("power", "power_total_w"),
        "classification": ("classification", "outcome_class"),
    }
    for candidate in aliases.get(key, (key,)):
        value = metrics.get(candidate)
        if value is None and metrics is not row:
            value = row.get(candidate)
        if value is not None:
            if key == "TNS_EVAL":
                numeric = _number(value)
                return abs(numeric) if numeric is not None else None
            return value
    return None


def _json_context(value, unavailable: str) -> str:
    """Serialize optional structured context without inviting the LLM to invent it."""
    if value is None or value == {} or value == [] or value == "":
        value = {"status": "not_provided", "note": unavailable}
    return json.dumps(value, indent=2, default=str)


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _objective_contract(objective: str, supplied=None) -> dict:
    """Normalize the exact objective/power semantics embedded in every prompt."""
    supplied = dict(supplied or {})
    contract = {
        "objective": objective,
        "direction": "minimize",
    }
    if objective == "TNS_EVAL":
        contract.update({
            "metric": "abs(setup TNS evaluated at the shared CP_0)",
            "comparison_clock": "CP_0",
            "same_cp0_required": True,
            "power_base": None,
            "power_budget_fraction": None,
            "power_limit": None,
            "feasibility_rule": (
                "comparable CP_0 TNS is present and power <= power_limit"
            ),
            "missing_power_with_active_budget": "power_infeasible",
            "ordering": (
                "first enforce power feasibility, then minimize abs(TNS)"
            ),
        })
    contract.update(supplied)
    if "power_budget" in contract and contract.get("power_budget_fraction") is None:
        contract["power_budget_fraction"] = contract.get("power_budget")
    base = _number(contract.get("power_base"))
    budget = _number(contract.get("power_budget_fraction"))
    limit = _number(contract.get("power_limit"))
    if limit is None and base is not None and budget is not None:
        limit = base * (1.0 + budget)
    if objective == "TNS_EVAL":
        contract["power_limit"] = limit
        contract["power_constraint_active"] = limit is not None
        if limit is None:
            contract["missing_contract_fields"] = [
                "power_limit or (power_base and power_budget_fraction)"
            ]
    return contract


def _objective_metric(row: dict, objective: str):
    if objective == "TNS_EVAL":
        return _metric_value(row, "TNS_EVAL")
    if objective in ("wl", "ecp"):
        return _metric_value(row, objective)
    combo = _metric_value(row, "combo")
    return combo


def _classify_results(results: list, objective: str, contract: dict) -> dict:
    """Build the three-way outcome contract when callers do not supply one."""
    groups = {"feasible": [], "power_infeasible": [], "flow_failed": []}
    power_limit = _number(contract.get("power_limit"))
    for row in results or []:
        run_id = row.get("run_id")
        explicit = row.get("classification", row.get("outcome_class"))
        if explicit not in groups:
            explicit = None
        objective_value = _objective_metric(row, objective)
        power = _number(_metric_value(row, "power"))
        tns_source = _metric_value(row, "tns_source")
        forced_failure = (row.get("flow_failed") is True
                          or row.get("completed") is False)
        reason = None
        if explicit is not None:
            classification = explicit
            reason = "caller_supplied"
        elif forced_failure or objective_value is None or (
                objective == "TNS_EVAL" and tns_source == "native"):
            classification = "flow_failed"
            reason = "missing_comparable_objective"
        elif objective == "TNS_EVAL" and power_limit is not None and (
                power is None or power > power_limit):
            classification = "power_infeasible"
            reason = "missing_power" if power is None else "power_above_limit"
        else:
            classification = "feasible"
            reason = "objective_contract_satisfied"
        item = {
            "run_id": run_id,
            "objective_value": objective_value,
            "power": power,
            "reason": reason,
        }
        if power_limit is not None and power is not None:
            item["power_margin"] = power_limit - power
        groups[classification].append(item)
    return {
        "counts": {name: len(rows) for name, rows in groups.items()},
        "runs": groups,
    }


def _classification_payload(results: list, objective: str, contract: dict,
                            supplied=None):
    """Return (prompt payload, canonical payload used for local derivations)."""
    derived = _classify_results(results, objective, contract)
    if supplied is None:
        return derived, derived
    if isinstance(supplied, dict) and isinstance(supplied.get("runs"), dict):
        return supplied, supplied
    return supplied, derived


def _top_successful(results: list, objective: str, classifications: dict,
                    limit: int = 5) -> list:
    feasible_ids = {
        row.get("run_id")
        for row in classifications.get("runs", {}).get("feasible", [])
    }
    ranked = []
    for row in results or []:
        params = row.get("params")
        value = _objective_metric(row, objective)
        if row.get("run_id") in feasible_ids and isinstance(params, dict) and value is not None:
            ranked.append((float(value), row))
    ranked.sort(key=lambda item: item[0])
    return [
        {
            "rank": rank,
            "run_id": row.get("run_id"),
            "objective_value": value,
            "power": _metric_value(row, "power"),
            "params": row.get("params"),
        }
        for rank, (value, row) in enumerate(ranked[:limit], 1)
    ]


def _parameter_distribution(results: list, classifications: dict) -> dict:
    class_by_id = {}
    for classification, rows in classifications.get("runs", {}).items():
        for row in rows:
            class_by_id[row.get("run_id")] = classification
    values = {}
    for row in results or []:
        if not isinstance(row.get("params"), dict):
            continue
        classification = class_by_id.get(row.get("run_id"), "unknown")
        for name, raw in row["params"].items():
            value = _number(raw)
            if value is not None:
                values.setdefault(name, {}).setdefault(classification, []).append(value)
    output = {}
    for name, groups in values.items():
        output[name] = {}
        for classification, vals in groups.items():
            output[name][classification] = {
                "count": len(vals),
                "min": min(vals),
                "mean": sum(vals) / len(vals),
                "max": max(vals),
            }
    return output


def _source_runs_context(source_runs: list, stage: str) -> str:
    rows = []
    for order, source in enumerate(source_runs or []):
        rows.append({
            "source_order": order,
            "source_run_id": source.get("run_id"),
            "source_candidate_id": source.get("candidate_id"),
            "wl": _metric_value(source, "wl"),
            "ecp": _metric_value(source, "ecp"),
            "abs_tns_at_cp0": _metric_value(source, "TNS_EVAL"),
            "power": _metric_value(source, "power"),
            "classification": _metric_value(source, "classification"),
            "promising_score": _metric_value(source, "promising_score"),
            "kill_score": _metric_value(source, "kill_score"),
            "current_stage_params": source.get(f"{stage}_params"),
            "parent_family": source.get("parent_family"),
        })
    return _json_context(rows, "No source-run context was supplied.")


def _edge_context(source_target_edges) -> str:
    if isinstance(source_target_edges, list):
        normalized = []
        for index, edge in enumerate(source_target_edges):
            record = dict(edge) if isinstance(edge, dict) else {"edge": edge}
            record.setdefault("edge_index", index)
            record.setdefault("output_index", record["edge_index"])
            normalized.append(record)
        source_target_edges = normalized
    return _json_context(
        source_target_edges,
        "No positional edge map was supplied; treat suggestions as a candidate pool."
    )


def format_metrics_table(run_metrics: list) -> str:
    """Format run metrics as a readable table string."""
    if not run_metrics:
        return "No metrics available."

    columns = [
        ("Run ID", "run_id", lambda value: str(value)),
        ("WL", "wl", lambda value: f"{value:.2f}"),
        ("ECP", "ecp", lambda value: f"{value:.4f}"),
        ("Combo", "combo", lambda value: f"{value:.4f}"),
    ]
    optional = [
        ("Abs TNS", "TNS_EVAL", lambda value: f"{value:.4f}"),
        ("Power", "power", lambda value: f"{value:.6f}"),
        ("Promising", "promising_score", lambda value: f"{value:.4f}"),
        ("Kill", "kill_score", lambda value: f"{value:.4f}"),
        ("Rank cost", "promising_cost", lambda value: f"{value:.4f}"),
    ]
    columns.extend(
        column for column in optional
        if any(_metric_value(metric, column[1]) is not None for metric in run_metrics)
    )
    lines = [
        "| " + " | ".join(label for label, _, _ in columns) + " |",
        "| " + " | ".join(":---:" for _ in columns) + " |",
    ]
    for m in run_metrics:
        values = []
        for _, key, formatter in columns:
            value = _metric_value(m, key)
            values.append(formatter(value) if value is not None else "N/A")
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def format_param_ranges(param_constraints: dict) -> str:
    """Format parameter constraints as a readable string."""
    lines = []
    for name, info in param_constraints.items():
        ptype = info["type"]
        prange = info["range"]
        desc = info.get("description", "")
        lines.append(f"- {name} ({ptype}, {prange[0]} to {prange[1]}): {desc}")
    return "\n".join(lines)


def build_cts_prompt(platform: str, design: str, objective: str,
                     num_kill: int, num_params: int,
                     metrics: list, source_runs: list,
                     param_constraints: dict,
                     objective_contract: dict = None,
                     top_successful_configs: list = None,
                     stratified_bests=None,
                     basin_summary=None,
                     parameter_distributions=None,
                     distance_info=None,
                     run_classifications=None,
                     source_target_edges=None,
                     optimization_context=None,
                     pdk_context=None,
                     design_context=None) -> str:
    """Build the CTS parameter generation prompt."""
    metrics_table = format_metrics_table(metrics)
    param_ranges = format_param_ranges(param_constraints)
    param_keys = ", ".join(param_constraints.keys())
    contract = _objective_contract(objective, objective_contract)
    classification_context, classifications = _classification_payload(
        metrics, objective, contract, run_classifications)
    top_configs = top_successful_configs
    if top_configs is None:
        top_configs = _top_successful(metrics, objective, classifications)
    distributions = parameter_distributions
    if distributions is None:
        distributions = _parameter_distribution(metrics, classifications)

    return CTS_PARAM_PROMPT.format(
        platform=platform,
        design=design,
        objective=objective,
        optimization_context=_json_context(
            optimization_context, "Optimization context unavailable."),
        pdk_context=_json_context(pdk_context, "PDK profile unavailable."),
        design_context=_json_context(design_context, "Design profile unavailable."),
        num_kill=num_kill,
        metrics_table=metrics_table,
        source_runs_info=_source_runs_context(source_runs, "cts"),
        objective_contract=_json_context(contract, "Objective contract unavailable."),
        run_classifications=_json_context(
            classification_context, "Outcome classifications unavailable."),
        top_successful_configs=_json_context(
            top_configs, "No successful parameter records were supplied."),
        stratified_bests=_json_context(
            stratified_bests, "No stratified best records were supplied."),
        basin_summary=_json_context(
            basin_summary, "No basin or coverage summary was supplied."),
        parameter_distributions=_json_context(
            distributions, "No parameter distributions were supplied."),
        distance_info=_json_context(
            distance_info, "No normalized distance information was supplied."),
        source_target_edges=_edge_context(source_target_edges),
        num_params_to_generate=num_params,
        param_ranges=param_ranges,
        param_keys=param_keys,
    )


def build_routing_prompt(platform: str, design: str, objective: str,
                         num_kill: int, num_params: int,
                         metrics: list, source_runs: list,
                         param_constraints: dict,
                         objective_contract: dict = None,
                         top_successful_configs: list = None,
                         stratified_bests=None,
                         basin_summary=None,
                         parameter_distributions=None,
                         distance_info=None,
                         run_classifications=None,
                         source_target_edges=None,
                         optimization_context=None,
                         pdk_context=None,
                         design_context=None) -> str:
    """Build the routing parameter generation prompt."""
    metrics_table = format_metrics_table(metrics)
    param_ranges = format_param_ranges(param_constraints)
    param_keys = ", ".join(param_constraints.keys())
    contract = _objective_contract(objective, objective_contract)
    classification_context, classifications = _classification_payload(
        metrics, objective, contract, run_classifications)
    top_configs = top_successful_configs
    if top_configs is None:
        top_configs = _top_successful(metrics, objective, classifications)
    distributions = parameter_distributions
    if distributions is None:
        distributions = _parameter_distribution(metrics, classifications)

    return ROUTING_PARAM_PROMPT.format(
        platform=platform,
        design=design,
        objective=objective,
        optimization_context=_json_context(
            optimization_context, "Optimization context unavailable."),
        pdk_context=_json_context(pdk_context, "PDK profile unavailable."),
        design_context=_json_context(design_context, "Design profile unavailable."),
        num_kill=num_kill,
        metrics_table=metrics_table,
        source_runs_info=_source_runs_context(source_runs, "routing"),
        objective_contract=_json_context(contract, "Objective contract unavailable."),
        run_classifications=_json_context(
            classification_context, "Outcome classifications unavailable."),
        top_successful_configs=_json_context(
            top_configs, "No successful parameter records were supplied."),
        stratified_bests=_json_context(
            stratified_bests, "No stratified best records were supplied."),
        basin_summary=_json_context(
            basin_summary, "No basin or coverage summary was supplied."),
        parameter_distributions=_json_context(
            distributions, "No parameter distributions were supplied."),
        distance_info=_json_context(
            distance_info, "No normalized distance information was supplied."),
        source_target_edges=_edge_context(source_target_edges),
        num_params_to_generate=num_params,
        param_ranges=param_ranges,
        param_keys=param_keys,
    )


def build_optimize_prompt(platform: str, design: str, objective: str,
                          iteration: int, num_runs: int,
                          results: list, history: str,
                          failed_configs: str,
                          synthesis_constraints: dict,
                          placement_constraints: dict,
                          cts_constraints: dict,
                          routing_constraints: dict,
                          clk_period_range: list,
                          explore_frac: float = 0.5,
                          objective_contract: dict = None,
                          top_successful_configs: list = None,
                          stratified_bests=None,
                          basin_summary=None,
                          parameter_distributions=None,
                          distance_info=None,
                          run_classifications=None,
                          source_target_edges=None,
                          optimization_context=None,
                          pdk_context=None,
                          design_context=None) -> str:
    """Build the inter-iteration optimization prompt."""
    results_table = format_metrics_table(results)
    explore_pct = int(round(explore_frac * 100))
    exploit_pct = 100 - explore_pct
    synthesis_ranges = format_param_ranges(synthesis_constraints)
    placement_ranges = format_param_ranges(placement_constraints)
    cts_ranges = format_param_ranges(cts_constraints)
    routing_ranges = format_param_ranges(routing_constraints)

    all_keys = (list(synthesis_constraints.keys())
                + list(placement_constraints.keys())
                + list(cts_constraints.keys())
                + list(routing_constraints.keys())
                + ["clk_period"])
    contract = _objective_contract(objective, objective_contract)
    classification_context, classifications = _classification_payload(
        results, objective, contract, run_classifications)
    top_configs = top_successful_configs
    if top_configs is None:
        top_configs = _top_successful(results, objective, classifications)
    distributions = parameter_distributions
    if distributions is None:
        distributions = _parameter_distribution(results, classifications)

    return OPTIMIZE_PROMPT.format(
        platform=platform,
        design=design,
        objective=objective,
        optimization_context=_json_context(
            optimization_context, "Optimization context unavailable."),
        pdk_context=_json_context(pdk_context, "PDK profile unavailable."),
        design_context=_json_context(design_context, "Design profile unavailable."),
        iteration=iteration,
        num_runs=num_runs,
        objective_contract=_json_context(contract, "Objective contract unavailable."),
        run_classifications=_json_context(
            classification_context, "Outcome classifications unavailable."),
        top_successful_configs=_json_context(
            top_configs, "No successful parameter records were supplied."),
        stratified_bests=_json_context(
            stratified_bests, "No stratified best records were supplied."),
        basin_summary=_json_context(
            basin_summary, "No basin or coverage summary was supplied."),
        parameter_distributions=_json_context(
            distributions, "No parameter distributions were supplied."),
        distance_info=_json_context(
            distance_info, "No normalized distance information was supplied."),
        source_target_edges=_edge_context(source_target_edges),
        results_table=results_table,
        history_summary=history,
        failed_configs=failed_configs,
        synthesis_ranges=synthesis_ranges,
        placement_ranges=placement_ranges,
        cts_ranges=cts_ranges,
        routing_ranges=routing_ranges,
        clk_period_range=f"{clk_period_range[0]} to {clk_period_range[1]}",
        all_param_keys=", ".join(all_keys),
        explore_pct=explore_pct,
        exploit_pct=exploit_pct,
    )
