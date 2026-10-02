#!/usr/bin/env python3
"""
Inter-iteration optimization for DRP-Agent.

After a complete iteration (placement → DRP → CTS → DRP → route → finish),
analyzes all run results and generates parameter sets for the next iteration.

Uses Bayesian optimization + LLM to:
1. Model the parameter-objective relationship across iterations
2. Generate new parameter sets balancing exploration and exploitation
"""

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np

# Shared helpers live in common.py now (breaks the optimize<->agent import cycle;
# optimize no longer imports agent at module load). Re-exported so existing
# `from optimize import tns_eval_obj/_power_base/...` call sites keep working.
from common import (
    call_llm, get_design_config, get_param_constraints, load_config, parse_llm_json,
    FAILURE_PENALTY_MULT, POWER_VIOLATION_PENALTY, _tns_base, _power_base, tns_eval_obj,
    is_feasible_objective_value,
)
from config_recipe import (
    build_recipe as _build_canonical_recipe,
    canonical_final_params,
    routing_parent_family,
)
from candidate_tracking import (
    CANDIDATE_ID_KEY,
    attach_metadata as attach_candidate_metadata,
    bind_slots as bind_candidate_slots,
    lifecycle_path as candidate_lifecycle_path,
    make_candidate_id,
    metadata as candidate_metadata,
)
from extract_metrics import extract_all_runs
from modelfuncs import (
    bayesian_suggest,
    clip_params,
    latin_hypercube_sample,
    params_to_array,
    perturb_params,
)
from prompts import SYSTEM_PROMPT, build_optimize_prompt, format_metrics_table
from prompt_context import build_shared_prompt_context
from lineage import config_snapshot as lineage_config_snapshot
from search_policy import (
    persist_batch_plan,
    persist_optimization_state,
    shape_next_batch,
    update_optimization_state,
)


_CTS_PARAM_NAMES = ("CTS_CLUSTER_SIZE", "CTS_CLUSTER_DIAMETER")
_ROUTING_PARAM_NAMES = ("PIN_LAYER_ADJUST", "ABOVE_LAYER_ADJUST")
_ALL_PARAM_NAMES = (
    "SYNTH_FLATTEN",
    "CORE_UTILIZATION",
    "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT",
    "CELL_PAD_IN_SITES_DETAIL_PLACEMENT",
    "ENABLE_DPO",
    "PLACE_DENSITY_LB_ADDON",
    "TNS_END_PERCENT",
    "FLOORPLAN_PIN_LAYER_ADJUST",
    "FLOORPLAN_ABOVE_LAYER_ADJUST",
    *_CTS_PARAM_NAMES,
    *_ROUTING_PARAM_NAMES,
)
_FLOORPLAN_SCOPED_PARAM_NAMES = {
    "PIN_LAYER_ADJUST": "FLOORPLAN_PIN_LAYER_ADJUST",
    "ABOVE_LAYER_ADJUST": "FLOORPLAN_ABOVE_LAYER_ADJUST",
}


def _history_candidate_id(record: Mapping[str, Any]) -> Optional[str]:
    """Resolve the executed candidate represented by a persisted history row."""
    queue = [record]
    seen = set()
    while queue:
        current = queue.pop(0)
        if not isinstance(current, Mapping) or id(current) in seen:
            continue
        seen.add(id(current))
        for key in (CANDIDATE_ID_KEY, "candidate_id", "target_candidate_id"):
            value = current.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        for key in ("stage_record", "lineage_event", "record"):
            nested = current.get(key)
            if isinstance(nested, Mapping):
                queue.append(nested)
    return None


def _stage_param_names(stage: str) -> Tuple[str, ...]:
    if stage == "cts":
        return _CTS_PARAM_NAMES
    if stage == "routing":
        return _ROUTING_PARAM_NAMES
    raise ValueError(f"unsupported lineage stage: {stage!r}")


def parameter_family(params: Dict[str, float], stage: str,
                     floorplan_context: Optional[Mapping[str, Any]] = None,
                     sdc_sha256: Any = None) -> Optional[str]:
    """Stable identity of the upstream configuration that a stage mutation sees.

    Routing is conditioned on every parameter except the routing knobs. CTS is
    conditioned only on synthesis/placement/clock: routing has not run yet, so its
    values must not split otherwise-identical CTS parents into different families.
    """
    if stage == "routing":
        return routing_parent_family(
            params, floorplan_context, sdc_sha256)
    excluded = set(_stage_param_names(stage))
    if stage == "cts":
        excluded.update(_ROUTING_PARAM_NAMES)
    upstream = {
        key: float(value)
        for key, value in params.items()
        if key not in excluded and isinstance(value, (int, float))
    }
    if not upstream:
        return None
    payload = json.dumps(upstream, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()[:16]

def _load_victim_audit(iter_dir: Path, iter_num: int) -> Tuple[set, bool, List[str]]:
    """Return victim IDs plus whether both canonical DRP records were verifiable."""
    victims = set()
    reasons = []
    for stage in ("place", "cts"):
        path = iter_dir / f"drp_{stage}_iter{iter_num}.json"
        if not path.is_file():
            reasons.append(f"missing_{path.name}")
            continue
        try:
            payload = json.loads(path.read_text())
            raw_ids = payload.get("victim_ids") if isinstance(payload, dict) else None
            if not isinstance(raw_ids, list):
                raise ValueError("victim_ids must be a list")
            for raw in raw_ids:
                if isinstance(raw, bool):
                    raise ValueError("victim_ids cannot contain bool")
                victims.add(int(raw))
        except Exception as exc:
            reasons.append(f"invalid_{path.name}")
            print(f"[optimize][WARN] cannot verify {path} ({exc}); clean/full-flow "
                  "provenance for this iteration is untrusted.", file=sys.stderr)
    return victims, not reasons, reasons


def _load_victim_ids(iter_dir: Path, iter_num: int) -> set:
    """Run IDs that were DRP victims (killed, then given ANOTHER run's checkpoint) at
    the place or cts stage this iteration. A victim's final metrics are produced by an
    INHERITED upstream checkpoint, not its own config, so pairing its config params
    with that final is misattributed (params -> objective is wrong). Such runs must be
    excluded from the optimizer history and elitism. Returns an empty set when the DRP
    records are absent (can't tell -> keep the run)."""
    victims, _, _ = _load_victim_audit(iter_dir, iter_num)
    return victims


def load_iteration_history(backup_dir: Path, platform: str, design: str,
                           max_iters: int) -> List[Dict]:
    """
    Load parameter-metric history from all completed iterations.

    Only DRP "full-survivor" runs (survived every checkpoint) are kept: their final
    result is a clean function of their own config. DRP victims inherited another
    run's checkpoint, so their (params -> final) label is misattributed and would
    poison the surrogate and make elitism chase an unreproducible "phantom" best.

    Returns list of dicts with 'params' and 'metrics' keys.
    """
    history = []
    base = backup_dir / platform / design
    n_kept = n_victim = 0

    for iter_num in range(1, max_iters + 1):
        iter_dir = base / f"result_dump_{iter_num}"
        if not iter_dir.exists():
            continue

        victim_ids, provenance_verified, provenance_reasons = _load_victim_audit(
            iter_dir, iter_num)

        # Load config files from backup
        config_files = sorted(iter_dir.glob("config_*.mk"))
        for cfg_file in config_files:
            run_id_match = re.search(r'config_(\d+)\.mk', cfg_file.name)
            if not run_id_match:
                continue
            run_id = int(run_id_match.group(1))

            # Skip DRP victims: their final came from an inherited checkpoint, so it
            # cannot be attributed to this config (approach A: full-survivors only).
            if run_id in victim_ids:
                n_victim += 1
                continue

            snapshot = None
            try:
                snapshot = lineage_config_snapshot(cfg_file)
            except Exception as exc:
                print(f"[optimize][WARN] cannot snapshot config {cfg_file} "
                      f"({exc}); config recipe unavailable.", file=sys.stderr)
            params = (_numeric_params(snapshot.get("params"))
                      if isinstance(snapshot, dict) else _extract_all_params(cfg_file))
            metrics = _extract_backup_metrics(iter_dir, run_id)

            # Keep every run that has parameters, INCLUDING ones whose metrics
            # are all None (route/placement failed). Those failures are exactly
            # the "this region is infeasible" signal the optimizer needs — they
            # are assigned a penalty objective downstream and surfaced to the LLM
            # as configs to avoid. Dropping them here (the old behaviour) left the
            # optimizer training only on feasible survivors, so it never learned
            # to steer away from the infeasible high-density region.
            if params:
                n_kept += 1
                record = {
                    "iteration": iter_num,
                    "run_id": run_id,
                    "params": params,
                    "metrics": metrics,
                    # Config-reproducible promotion is stricter than surrogate
                    # training: it needs proof that both DRP stages were audited and
                    # this final row was never replaced by another run's checkpoint.
                    "full_flow_attributable": provenance_verified,
                    "full_flow_provenance": {
                        "status": "verified" if provenance_verified else "untrusted",
                        "reasons": list(provenance_reasons),
                    },
                }
                recipe = config_recipe_from_snapshot(snapshot)
                if recipe is not None:
                    record["config_recipe"] = recipe
                history.append(record)

    if n_kept or n_victim:
        print(f"[history] full-survivor runs kept={n_kept}, DRP victims skipped="
              f"{n_victim} (misattributed final -> excluded)", file=sys.stderr)
    return history


def _extract_all_params(config_path: Path) -> Dict[str, float]:
    """Extract all tunable parameters from a config.mk file."""
    params = {}

    try:
        content = config_path.read_text()
    except Exception as e:
        print(f"[optimize][WARN] cannot read config {config_path} "
              f"({e}); its params drop out of history.", file=sys.stderr)
        return params

    for name in _ALL_PARAM_NAMES:
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

    for logical_name, scoped_name in _FLOORPLAN_SCOPED_PARAM_NAMES.items():
        if scoped_name not in params and logical_name in params:
            params[scoped_name] = params[logical_name]

    # Extract clock period from the SDC this config actually used. SDC_FILE holds an
    # absolute LIVE-workdir path that is deleted/overwritten by later iterations, so
    # following it verbatim while reading BACKUP history yields the wrong clk (or
    # None -> elitism fills the range midpoint, silently corrupting the best config).
    # Resolve the referenced file by BASENAME inside this config's own directory: in
    # a backup dump the file it names (e.g. constraint_1.sdc — which may differ from
    # this run's id because GWTW/elitism copies share an SDC) sits right beside the
    # config. Fall back to the literal path for live-context reads.
    sdc_match = re.search(r'SDC_FILE\s*=\s*(\S+)', content)
    if sdc_match:
        raw = sdc_match.group(1)
        for sdc_path in (config_path.parent / Path(raw).name, Path(raw)):
            try:
                if sdc_path.exists():
                    clk_match = re.search(r'set\s+clk_period\s+([\d.eE+\-]+)',
                                          sdc_path.read_text())
                    if clk_match:
                        params["clk_period"] = float(clk_match.group(1))
                        break
            except Exception:
                pass

    return params


def _extract_backup_metrics(iter_dir: Path, run_id: int) -> Dict[str, Optional[float]]:
    """Final metrics for a backed-up run (THIS design only), from the substep JSONs
    with a CP_0-tag override — same robust path as the live extraction."""
    from extract_metrics import extract_metrics

    metrics = {"wl": None, "ecp": None, "tns": None, "power": None,
               "tns_source": "missing"}
    logs_dir = iter_dir / "logs_dump"
    if not logs_dir.exists():
        return metrics

    # iter_dir = backup_dir/{platform}/{design}/result_dump_N. Anchor on
    # {platform}_{design}_run so stale OTHER-design logs (e.g. asap7_aes_run*.log left
    # from a prior aes run) don't poison this design's history.
    design = iter_dir.parent.name
    platform = iter_dir.parent.parent.name
    prefix = f"{platform}_{design}_run"
    log_files = (list(logs_dir.glob(f"{prefix}{run_id}.log")) +
                 list(logs_dir.glob(f"{prefix}_{run_id}.log")))
    log_file = log_files[0] if log_files else (logs_dir / "____nonexistent.log")
    json_dir = logs_dir / platform / design / f"run_{run_id}"

    try:
        m = extract_metrics(log_file, "final",
                            json_dir=json_dir if json_dir.exists() else None)
        for k in metrics:
            if m.get(k) is not None:
                metrics[k] = m[k]
    except Exception as e:
        print(f"[optimize][WARN] backup metrics extraction failed for {log_file} "
              f"({e}).", file=sys.stderr)
    return metrics


def _metric_map(iter_dir: Path, iter_num: int, stage: str) -> Dict[int, Dict]:
    """Read only the metric file belonging to this result_dump iteration.

    Old result dumps can contain files copied from many other iterations. Never glob
    here: an exact filename is part of the campaign-data integrity contract.
    """
    path = iter_dir / f"metrics_{stage}_iter{iter_num}.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except Exception as e:
        print(f"[lineage][WARN] cannot parse {path} ({e}).", file=sys.stderr)
        return {}
    if not isinstance(payload, list):
        print(f"[lineage][WARN] expected a list in {path}; ignoring it.", file=sys.stderr)
        return {}
    result = {}
    for row in payload:
        if not isinstance(row, dict) or row.get("run_id") is None:
            continue
        try:
            run_id = int(row["run_id"])
        except (TypeError, ValueError):
            continue
        metrics = dict(row)
        if metrics.get("tns") is None and metrics.get("TNS_EVAL") is not None:
            metrics["tns"] = -abs(float(metrics["TNS_EVAL"]))
        result[run_id] = metrics
    return result


def _numeric_params(value) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, raw in value.items():
        try:
            result[str(key)] = float(raw)
        except (TypeError, ValueError):
            continue
    return result


def _routing_context(value: Any) -> Dict[str, float]:
    """Normalize either logical or FLOORPLAN_* routing-context keys."""
    if not isinstance(value, Mapping):
        return {}
    context: Dict[str, float] = {}
    for logical, scoped in _FLOORPLAN_SCOPED_PARAM_NAMES.items():
        raw = value.get(logical, value.get(scoped))
        try:
            context[logical] = float(raw)
        except (TypeError, ValueError):
            continue
    return context


def _complete_final_params(value: Any) -> Dict[str, float]:
    return canonical_final_params(value) or {}


def build_config_recipe(final_params: Mapping[str, Any],
                        floorplan_routing_context: Mapping[str, Any],
                        sdc_sha256: Any) -> Optional[Dict[str, Any]]:
    """Build a stable, static no-checkpoint execution recipe.

    ``final_params`` carries the values consumed by the final CTS/routing flow, while
    ``floorplan_routing_context`` preserves the layer adjustments that shaped the
    placement checkpoint.  The latter is scoped explicitly so equal final parameter
    vectors with different physical contexts never share a replay identity.
    """
    return _build_canonical_recipe(
        final_params, floorplan_routing_context, sdc_sha256)


def _context_from_containers(*containers: Any) -> Dict[str, float]:
    """Read new lineage context fields while retaining old-archive fallbacks."""
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        for key in ("source_routing_context", "effective_routing_context",
                    "floorplan_routing_context", "routing_context"):
            context = _routing_context(container.get(key))
            if set(context) == set(_ROUTING_PARAM_NAMES):
                return context
    return {}


def _sdc_sha_from_containers(*containers: Any) -> Optional[str]:
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        for direct_name in ("sdc_recipe_sha256", "sdc_sha256"):
            direct = container.get(direct_name)
            if direct:
                return str(direct)
        for key in ("effective_sdc", "source_effective_sdc"):
            sdc = container.get(key)
            if isinstance(sdc, Mapping):
                identity = sdc.get("recipe_sha256", sdc.get("sha256"))
                if identity:
                    return str(identity)
        for key in ("target_config", "source_config"):
            config = container.get(key)
            if not isinstance(config, Mapping):
                continue
            sdc = config.get("effective_sdc")
            if isinstance(sdc, Mapping):
                identity = sdc.get("recipe_sha256", sdc.get("sha256"))
                if identity:
                    return str(identity)
    return None


def config_recipe_from_snapshot(snapshot: Any) -> Optional[Dict[str, Any]]:
    """Construct the clean-history recipe from a lineage config snapshot."""
    if not isinstance(snapshot, Mapping):
        return None
    final = _complete_final_params(snapshot.get("params"))
    context = _context_from_containers(snapshot)
    if not context:
        # Historical clean configs predate scoped context.  For a non-cloned static
        # config, its final routing pair is also the pair consumed at floorplan.
        context = _routing_context(final)
    return build_config_recipe(
        final, context, _sdc_sha_from_containers(snapshot))


def config_recipe_for_lineage(
    record: Mapping[str, Any],
    post_place_cts_record: Optional[Mapping[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve a trusted CTS/routing row into a static no-checkpoint recipe.

    TNS_END_PERCENT is consumed during placement timing repair.  A post-place clone
    that changed it cannot be represented by one static config: setting the final
    value from process start would alter the placement we are trying to reproduce.
    Such rows deliberately fail closed until the flow has another scoped parameter.
    """
    if not isinstance(record, Mapping) or record.get("trusted") is not True:
        return None
    stage = str(record.get("stage", "")).lower()
    if stage not in {"cts", "routing"}:
        return None
    final = _complete_final_params(record.get("effective_params"))
    event = record.get("lineage_event")
    event = event if isinstance(event, Mapping) else {}

    cts_parent = (post_place_cts_record
                  if isinstance(post_place_cts_record, Mapping) else None)
    if stage == "cts":
        cts_parent = record
    if cts_parent is not None:
        source_params = _numeric_params(cts_parent.get("source_effective_params"))
        cts_final = _numeric_params(cts_parent.get("effective_params"))
        source_tns = source_params.get("TNS_END_PERCENT")
        final_tns = cts_final.get("TNS_END_PERCENT")
        if (source_tns is None or final_tns is None
                or not _same_number(source_tns, final_tns)):
            return None

    context = _context_from_containers(record, event)
    if not context and cts_parent is not None:
        cts_event = cts_parent.get("lineage_event")
        context = _context_from_containers(
            cts_parent, cts_event if isinstance(cts_event, Mapping) else {})
    if not context:
        # Old trusted lineage snapshots do not have explicit context fields.  The
        # post-CTS source config still carries the pair used by its placement parent.
        context = _routing_context(record.get("source_effective_params"))
    if not context and cts_parent is not None:
        context = _routing_context(cts_parent.get("source_effective_params"))

    sdc_hash = _sdc_sha_from_containers(record, event)
    if not sdc_hash and cts_parent is not None:
        cts_event = cts_parent.get("lineage_event")
        sdc_hash = _sdc_sha_from_containers(
            cts_parent, cts_event if isinstance(cts_event, Mapping) else {})
    return build_config_recipe(final, context, sdc_hash)


def _lineage_stage(event: Dict, default_stage: Optional[str]) -> Optional[str]:
    generated = _numeric_params(
        event.get("generated_params", event.get("mutation_params", event.get("params"))))
    if set(generated) & set(_ROUTING_PARAM_NAMES):
        return "routing"
    if set(generated) & set(_CTS_PARAM_NAMES):
        return "cts"
    raw = (event.get("mutation_stage") or event.get("parameter_stage") or
           event.get("next_stage") or event.get("stage") or default_stage)
    if raw is None:
        return None
    raw = str(raw).strip().lower().replace("_", "-")
    if raw in {"routing", "route", "post-cts"}:
        return "routing"
    if raw in {"cts", "clock-tree", "post-place"}:
        return "cts"
    if raw == "place":
        return "cts"
    return None


def _payload_events(payload, default_stage: Optional[str] = None) -> List[Dict]:
    """Accept the aggregate and per-DRP lineage event shapes.

    New producers emit one event per clone. The array-shaped branch is retained for
    forward compatibility with an aggregate that stores aligned DRP arrays.
    """
    if isinstance(payload, list):
        events = []
        for item in payload:
            if isinstance(item, dict):
                event = dict(item)
                event.setdefault("_default_stage", default_stage)
                events.append(event)
        return events
    if not isinstance(payload, dict):
        return []
    stages = payload.get("stages")
    if isinstance(stages, dict):
        events = []
        # The producer keys by the completed DRP checkpoint. Its mutation family is
        # the following stage: post-place -> CTS, post-CTS -> routing.
        for producer_stage, mutation_stage in (("place", "cts"), ("cts", "routing")):
            if isinstance(stages.get(producer_stage), list):
                events.extend(_payload_events(stages[producer_stage], mutation_stage))
        return events
    for key in ("lineage_events", "events"):
        if isinstance(payload.get(key), (list, dict)):
            return _payload_events(payload[key], default_stage)
    events = []
    for stage in ("cts", "routing"):
        if isinstance(payload.get(stage), list):
            events.extend(_payload_events(payload[stage], stage))
    if events:
        return events
    sources = payload.get("source_ids")
    targets = payload.get("victim_ids", payload.get("target_ids"))
    generated = payload.get("generated_params")
    if all(isinstance(x, list) for x in (sources, targets, generated)):
        if len(sources) != len(targets) or len(targets) != len(generated):
            return []
        for source, target, params in zip(sources, targets, generated):
            events.append({
                "source_run_id": source,
                "target_run_id": target,
                "generated_params": params,
                "_default_stage": default_stage,
            })
    return events


def _explicit_lineage_events(backup_dir: Path, iter_dir: Path,
                             iter_num: int, platform: str,
                             design: str) -> List[Dict]:
    """Load explicit snapshots, preferring the exact per-iteration aggregate.

    A generic or globbed file is intentionally not accepted: both tmp and old backup
    directories can contain stale campaign data. Embedded events are read only from
    the two DRP JSON files whose iteration number matches result_dump_N.
    """
    candidates = [
        (iter_dir / f"lineage_iter{iter_num}.json", None),
        (iter_dir / f"drp_place_iter{iter_num}.json", "cts"),
        (iter_dir / f"drp_cts_iter{iter_num}.json", "routing"),
    ]
    expected_campaign = None
    manifest = iter_dir.parent / "campaign_manifest.json"
    try:
        expected_campaign = json.loads(manifest.read_text()).get("campaign_id")
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    found = []
    for path, default_stage in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
        except Exception as e:
            print(f"[lineage][WARN] cannot parse {path} ({e}).", file=sys.stderr)
            continue
        if isinstance(payload, dict):
            if payload.get("platform") not in (None, platform):
                continue
            if payload.get("design") not in (None, design):
                continue
            if (expected_campaign is not None and payload.get("campaign_id")
                    not in (None, expected_campaign)):
                continue
        if isinstance(payload, dict) and payload.get("iteration") is not None:
            try:
                if int(payload["iteration"]) != iter_num:
                    continue
            except (TypeError, ValueError):
                continue
        candidate_edges = {}
        duplicate_edge_ids = set()
        if default_stage is not None and isinstance(payload, dict):
            for edge in payload.get("candidate_edges") or []:
                if not isinstance(edge, dict):
                    continue
                event_id = str(edge.get("lineage_event_id") or "").strip()
                if not event_id:
                    continue
                if event_id in candidate_edges:
                    duplicate_edge_ids.add(event_id)
                else:
                    candidate_edges[event_id] = edge

        # New staged runs expose one event per run slot. Older archives retain the
        # clone-only lineage array and continue through the compatibility path.
        if default_stage is not None:
            if not isinstance(payload, dict) or "lineage_events" not in payload:
                continue
            stage_events = payload.get("stage_parameter_events")
            payload = (
                stage_events if isinstance(stage_events, list) and stage_events
                else payload["lineage_events"])
        for event in _payload_events(payload, default_stage):
            event = dict(event)
            event_id = str(event.get("event_id") or "").strip()
            if event_id in duplicate_edge_ids:
                event["trusted"] = False
                reasons = list(event.get("trust_reasons") or [])
                reasons.append("duplicate_candidate_edges_for_lineage_event")
                event["trust_reasons"] = list(dict.fromkeys(map(str, reasons)))
            elif event_id in candidate_edges:
                edge = candidate_edges[event_id]
                identity_fields = {
                    "source_candidate_id": edge.get("source_candidate_id"),
                    "target_candidate_id": edge.get("target_candidate_id"),
                    "replaced_target_candidate_id": edge.get(
                        "replaced_target_candidate_id",
                        edge.get("replaced_candidate_id")),
                    "candidate_lifecycle_event_id": edge.get(
                        "lifecycle_event_id"),
                }
                conflicts = [
                    name for name, value in identity_fields.items()
                    if value is not None and event.get(name) is not None
                    and str(event.get(name)) != str(value)
                ]
                if conflicts:
                    event["trusted"] = False
                    reasons = list(event.get("trust_reasons") or [])
                    reasons.append("conflicting_candidate_identity_for_lineage_event")
                    event["trust_reasons"] = list(
                        dict.fromkeys(map(str, reasons)))
                else:
                    event.update({
                        name: value for name, value in identity_fields.items()
                        if value is not None
                    })
            event["_provenance"] = str(path)
            event.setdefault("_default_stage", default_stage)
            if event.get("iteration") is not None:
                try:
                    if int(event["iteration"]) != iter_num:
                        continue
                except (TypeError, ValueError):
                    continue
            found.append(event)

    # The aggregate and embedded DRP records normally describe the same clone. Keep
    # the richest trusted snapshot instead of double-counting it.
    def semantic(event):
        checkpoint = event.get("checkpoint")
        checkpoint = checkpoint if isinstance(checkpoint, dict) else {}
        return {
            "source": event.get("source_run_id", event.get("source_id")),
            "generated": _numeric_params(event.get("generated_params")),
            "source_effective": _numeric_params(event.get("source_effective_params")),
            "effective": _numeric_params(event.get(
                "effective_params", event.get("target_effective_params"))),
            "checkpoint": checkpoint.get("identity") or checkpoint.get("sha256"),
        }

    def conflicts(left, right):
        a, b = semantic(left), semantic(right)
        if str(a["source"]) != str(b["source"]):
            return True
        for key in ("generated", "source_effective", "effective"):
            if a[key] and b[key] and a[key] != b[key]:
                return True
        return bool(a["checkpoint"] and b["checkpoint"]
                    and a["checkpoint"] != b["checkpoint"])

    best = {}
    for event in found:
        stage = _lineage_stage(event, event.get("_default_stage"))
        try:
            source = int(event.get("source_run_id", event.get("source_id")))
            target = int(event.get(
                "target_run_id", event.get("victim_run_id", event.get("target_id"))))
        except (TypeError, ValueError):
            continue
        key = (stage, target)
        effective = event.get("effective_params", event.get("target_effective_params"))
        score = (
            4 * int(event.get("trusted") is True)
            + 2 * int(isinstance(effective, dict))
            + 2 * int(isinstance(event.get("source_effective_params"), dict))
            + int(isinstance(event.get("generated_params"), dict))
            + int(bool(event.get("source_candidate_id")))
            + int(bool(event.get("target_candidate_id")))
        )
        if key in best and conflicts(best[key][1], event):
            richer = dict(event if score > best[key][0] else best[key][1])
            richer["trusted"] = False
            reasons = list(richer.get("trust_reasons") or [])
            reasons.append("conflicting_lineage_records_for_target")
            richer["trust_reasons"] = list(dict.fromkeys(map(str, reasons)))
            richer["_lineage_conflict"] = True
            best[key] = (max(score, best[key][0]), richer)
        elif key in best and best[key][1].get("_lineage_conflict"):
            continue
        elif key not in best or score > best[key][0]:
            best[key] = (score, event)
    return [entry[1] for entry in best.values()]


def _same_number(left, right, tolerance: float = 1e-9) -> bool:
    try:
        return abs(float(left) - float(right)) <= tolerance
    except (TypeError, ValueError):
        return False


def _metrics_delta(child: Dict, source: Dict, name: str,
                   absolute: bool = False) -> Optional[float]:
    child_value, source_value = child.get(name), source.get(name)
    if child_value is None or source_value is None:
        return None
    try:
        if absolute:
            return abs(float(child_value)) - abs(float(source_value))
        return float(child_value) - float(source_value)
    except (TypeError, ValueError):
        return None


def _event_sdc_identity(event: Mapping[str, Any], source: bool) -> Optional[str]:
    direct_key = "source_effective_sdc" if source else "effective_sdc"
    config_key = "source_config" if source else "target_config"
    for container in (event.get(direct_key),
                      (event.get(config_key) or {}).get("effective_sdc")
                      if isinstance(event.get(config_key), Mapping) else None):
        if isinstance(container, Mapping):
            identity = container.get("recipe_sha256", container.get("sha256"))
            if identity:
                return str(identity)
    return None


def _build_stage_record(event: Dict, iter_num: int, stage: str,
                        source_metrics: Dict, child_metrics: Dict,
                        source_present: bool, child_present: bool,
                        overwritten_later: bool = False) -> Dict:
    source = int(event["source_run_id"])
    target = int(event["target_run_id"])
    generated = _numeric_params(event.get("generated_params", event.get("params")))
    source_effective = _numeric_params(event.get("source_effective_params"))
    effective = _numeric_params(
        event.get("effective_params", event.get("target_effective_params")))
    effective_clock = event.get("effective_clock")
    source_clock = event.get("source_effective_clock", effective_clock)
    if effective_clock is not None and "clk_period" not in effective:
        try:
            effective["clk_period"] = float(effective_clock)
        except (TypeError, ValueError):
            pass
    if source_clock is not None and "clk_period" not in source_effective:
        try:
            source_effective["clk_period"] = float(source_clock)
        except (TypeError, ValueError):
            pass
    required = _stage_param_names(stage)
    mutation_expected = event.get("mutation_expected", True) is not False
    reasons = []

    trusted = event.get("trusted") is True
    if not trusted:
        producer_reasons = event.get("trust_reasons")
        if isinstance(producer_reasons, list) and producer_reasons:
            reasons.extend(str(reason) for reason in producer_reasons)
        else:
            reasons.append(str(event.get("reason") or "producer_did_not_mark_trusted"))
    if mutation_expected and not all(name in generated for name in required):
        trusted = False
        reasons.append("incomplete_generated_params")
    if not source_effective:
        trusted = False
        reasons.append("missing_source_effective_params")
    if not effective:
        trusted = False
        reasons.append("missing_effective_params")
    excluded = set(required)
    if stage == "cts":
        excluded.update(_ROUTING_PARAM_NAMES)
    required_upstream = ((set(_ALL_PARAM_NAMES) - excluded) | {"clk_period"})
    missing_source = required_upstream - set(source_effective)
    missing_effective = (required_upstream | set(required)) - set(effective)
    if missing_source:
        trusted = False
        reasons.append("incomplete_source_effective_params")
    if missing_effective:
        trusted = False
        reasons.append("incomplete_effective_params")
    if mutation_expected:
        for name in required:
            if name in generated and (name not in effective or
                                      not _same_number(generated[name], effective[name])):
                trusted = False
                reasons.append(f"effective_{name}_mismatch")
    if not source_present:
        trusted = False
        reasons.append(f"missing_source_metrics_{'cts' if stage == 'cts' else 'final'}")
    if not child_present:
        trusted = False
        reasons.append(f"missing_child_metrics_{'cts' if stage == 'cts' else 'final'}")
    if stage == "cts" and overwritten_later and not effective:
        trusted = False
        reasons.append("later_cts_clone_overwrote_unsnapshotted_config")

    upstream_params = {k: v for k, v in source_effective.items() if k not in excluded}
    source_context = (_routing_context(event.get("source_routing_context"))
                      or _routing_context(source_effective))
    effective_context = (_routing_context(event.get("effective_routing_context"))
                         or source_context)
    source_sdc_identity = _event_sdc_identity(event, True)
    effective_sdc_identity = _event_sdc_identity(event, False)
    source_sdc_identity = source_sdc_identity or effective_sdc_identity
    effective_sdc_identity = effective_sdc_identity or source_sdc_identity
    family = parameter_family(
        source_effective, stage, source_context, source_sdc_identity)
    effective_family = parameter_family(
        effective, stage, effective_context,
        effective_sdc_identity or source_sdc_identity)
    if family is None or family != effective_family:
        trusted = False
        reasons.append("source_child_upstream_family_mismatch")
    mapping_kind = str(event.get("mapping_kind") or (
        "self" if source == target else "clone"))
    if mapping_kind not in {"self", "clone"}:
        trusted = False
        reasons.append("invalid_stage_mapping_kind")
    if (mapping_kind == "self") != (source == target):
        trusted = False
        reasons.append("stage_mapping_kind_endpoint_mismatch")
    return {
        "iteration": iter_num,
        "stage": stage,
        "lineage_event_id": event.get("event_id", event.get("lineage_event_id")),
        "run_id": target,
        "target_run_id": target,
        "source_run_id": source,
        "mapping_kind": mapping_kind,
        "source_candidate_id": event.get("source_candidate_id"),
        "target_candidate_id": event.get("target_candidate_id"),
        "replaced_target_candidate_id": event.get(
            "replaced_target_candidate_id", event.get("replaced_candidate_id")),
        "candidate_lifecycle_event_id": event.get(
            "candidate_lifecycle_event_id", event.get("lifecycle_event_id")),
        "params": {name: generated[name] for name in required if name in generated},
        "metrics": child_metrics,
        "child_metrics": child_metrics,
        "source_metrics": source_metrics,
        "effective_params": effective,
        "source_effective_params": source_effective,
        "source_routing_context": source_context,
        "effective_routing_context": effective_context,
        "upstream_params": upstream_params,
        "parent_family": family,
        "upstream_family": family,
        "effective_clock": effective.get("clk_period"),
        "source_effective_clock": source_effective.get("clk_period"),
        "delta_abs_tns": _metrics_delta(child_metrics, source_metrics, "tns", True),
        "delta_power": _metrics_delta(child_metrics, source_metrics, "power"),
        "delta_wl": _metrics_delta(child_metrics, source_metrics, "wl"),
        "delta_ecp": _metrics_delta(child_metrics, source_metrics, "ecp"),
        "trusted": bool(trusted),
        "trust_reason": "ok" if trusted else ";".join(dict.fromkeys(reasons)),
        "overwritten_later": bool(overwritten_later),
        "provenance": event.get("_provenance", "lineage_event"),
        "lineage_event": {k: v for k, v in event.items() if not str(k).startswith("_")},
    }


def _legacy_routing_events(iter_dir: Path, iter_num: int,
                           final_metrics: Dict[int, Dict]) -> List[Dict]:
    """Safely reconstruct old post-CTS routing clones.

    This is intentionally routing-only. At post-CTS, the source is a survivor and
    its archived config is still the exact checkpoint parent. Old post-place CTS
    records lack snapshots, and a later CTS clone may have overwritten both the
    target config and its earlier CTS mutation, so those records fail closed.
    """
    path = iter_dir / f"drp_cts_iter{iter_num}.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text())
    except Exception as e:
        print(f"[lineage][WARN] cannot parse {path} ({e}).", file=sys.stderr)
        return []
    sources = payload.get("source_ids", []) if isinstance(payload, dict) else []
    targets = payload.get("victim_ids", []) if isinstance(payload, dict) else []
    generated = payload.get("generated_params", []) if isinstance(payload, dict) else []
    if not (isinstance(sources, list) and isinstance(targets, list) and
            isinstance(generated, list) and len(sources) == len(targets) == len(generated)):
        print(f"[lineage][WARN] unaligned routing arrays in {path}; ignoring them.",
              file=sys.stderr)
        return []

    events = []
    for source_raw, target_raw, mutation_raw in zip(sources, targets, generated):
        try:
            source, target = int(source_raw), int(target_raw)
        except (TypeError, ValueError):
            continue
        mutation = _numeric_params(mutation_raw)
        source_config_path = iter_dir / f"config_{source}.mk"
        target_config_path = iter_dir / f"config_{target}.mk"
        source_effective = _extract_all_params(source_config_path)
        effective = _extract_all_params(target_config_path)
        try:
            source_snapshot = lineage_config_snapshot(source_config_path)
            target_snapshot = lineage_config_snapshot(target_config_path)
            source_sdc = source_snapshot.get("effective_sdc", {})
            target_sdc = target_snapshot.get("effective_sdc", {})
            source_context = source_snapshot.get("routing_context", {})
            target_context = target_snapshot.get("routing_context", {})
            sdc_matches = bool(
                source_sdc.get("sha256")
                and source_sdc.get("sha256") == target_sdc.get("sha256"))
        except Exception:
            source_sdc, target_sdc, sdc_matches = {}, {}, False
            source_context, target_context = {}, {}
        source_family = parameter_family(
            source_effective, "routing", source_context,
            source_sdc.get("recipe_sha256", source_sdc.get("sha256")))
        target_family = parameter_family(
            effective, "routing", target_context,
            target_sdc.get("recipe_sha256", target_sdc.get("sha256")))
        complete = all(name in mutation for name in _ROUTING_PARAM_NAMES)
        mutation_matches = complete and all(
            name in effective and _same_number(mutation[name], effective[name])
            for name in _ROUTING_PARAM_NAMES)
        trusted = bool(
            source != target and source_effective and effective and
            source_family is not None and source_family == target_family and
            mutation_matches and sdc_matches and
            source in final_metrics and target in final_metrics)
        reason = "legacy_routing_verified" if trusted else "legacy_routing_verification_failed"
        events.append({
            "stage": "routing",
            "source_run_id": source,
            "target_run_id": target,
            "generated_params": mutation,
            "source_effective_params": source_effective,
            "effective_params": effective,
            "source_routing_context": source_context,
            "effective_routing_context": target_context,
            "effective_clock": effective.get("clk_period"),
            "source_effective_sdc": source_sdc,
            "effective_sdc": target_sdc,
            "trusted": trusted,
            "reason": reason,
            "_provenance": str(path),
        })
    return events


def load_resolved_stage_history(backup_dir: Path, platform: str, design: str,
                                max_iters: int, stage: Optional[str] = None,
                                include_untrusted: bool = False) -> List[Dict]:
    """Load lineage-resolved CTS/routing observations without changing clean history.

    CTS events use matching ``metrics_cts_iterN.json`` snapshots; routing events use
    matching final metrics. Explicit lineage snapshots are required for trusted CTS
    records. Old archives are reconstructed only for post-CTS routing, where the
    source/child config relation can be verified exactly.
    """
    if stage is not None:
        _stage_param_names(stage)
    requested = (stage,) if stage else ("cts", "routing")
    base = backup_dir / platform / design
    history = []
    counts = {name: {"trusted": 0, "untrusted": 0} for name in requested}

    for iter_num in range(1, max_iters + 1):
        iter_dir = base / f"result_dump_{iter_num}"
        if not iter_dir.exists():
            continue
        metric_maps = {
            "cts": _metric_map(iter_dir, iter_num, "cts"),
            "routing": _metric_map(iter_dir, iter_num, "final"),
        }
        explicit = _explicit_lineage_events(
            backup_dir, iter_dir, iter_num, platform, design)
        by_stage = {name: [] for name in requested}
        for raw in explicit:
            event_stage = _lineage_stage(raw, raw.get("_default_stage"))
            if event_stage in by_stage:
                by_stage[event_stage].append(raw)

        # A later post-CTS clone overwrites a prior post-place target's live config.
        # Explicit CTS effective snapshots remain valid; missing snapshots fail closed.
        routing_targets = set()
        for raw in by_stage.get("routing", []):
            try:
                routing_targets.add(int(raw.get(
                    "target_run_id", raw.get("victim_run_id", raw.get("target_id")))))
            except (TypeError, ValueError):
                pass
        routing_path = iter_dir / f"drp_cts_iter{iter_num}.json"
        routing_has_embedded_lineage = False
        if routing_path.exists():
            try:
                routing_payload = json.loads(routing_path.read_text())
                routing_has_embedded_lineage = (
                    isinstance(routing_payload, dict)
                    and "lineage_events" in routing_payload)
                routing_targets.update(int(x) for x in routing_payload.get("victim_ids", []))
            except Exception:
                pass

        for event_stage in requested:
            events = list(by_stage[event_stage])
            explicit_targets = set()
            for raw in events:
                try:
                    explicit_targets.add(int(raw.get("target_run_id", raw.get(
                        "victim_run_id", raw.get("target_id")))))
                except (TypeError, ValueError):
                    pass
            if event_stage == "routing" and not routing_has_embedded_lineage:
                for raw in _legacy_routing_events(
                        iter_dir, iter_num, metric_maps["routing"]):
                    if int(raw["target_run_id"]) not in explicit_targets:
                        events.append(raw)

            metrics = metric_maps[event_stage]
            for raw in events:
                try:
                    source = int(raw.get("source_run_id", raw.get("source_id")))
                    target = int(raw.get("target_run_id", raw.get(
                        "victim_run_id", raw.get("target_id"))))
                except (TypeError, ValueError):
                    continue
                event = dict(raw)
                event["source_run_id"] = source
                event["target_run_id"] = target
                source_metrics = metrics.get(source)
                child_metrics = metrics.get(target)
                if source_metrics is None:
                    source_metrics = (raw.get("source_metrics")
                                      if isinstance(raw.get("source_metrics"), dict) else {})
                if child_metrics is None:
                    child_metrics = (raw.get("child_metrics")
                                     if isinstance(raw.get("child_metrics"), dict) else {})
                record = _build_stage_record(
                    event, iter_num, event_stage, source_metrics, child_metrics,
                    source in metrics or bool(raw.get("source_metrics")),
                    target in metrics or bool(raw.get("child_metrics")),
                    overwritten_later=(event_stage == "cts" and target in routing_targets),
                )
                bucket = "trusted" if record["trusted"] else "untrusted"
                counts[event_stage][bucket] += 1
                if record["trusted"] or include_untrusted:
                    history.append(record)

    details = ", ".join(
        f"{name}={values['trusted']} trusted/{values['untrusted']} rejected"
        for name, values in counts.items())
    if history or any(sum(v.values()) for v in counts.values()):
        print(f"[lineage-history] {details}", file=sys.stderr)
    return history


def _attach_archived_sdc_recipe_identity(
    row: Dict[str, Any], backup_dir: Path, platform: str, design: str,
) -> None:
    """Attach the normalized SDC identity from the archived target config."""
    try:
        config_path = (backup_dir / platform / design
                       / f"result_dump_{int(row['iteration'])}"
                       / f"config_{int(row['target_run_id'])}.mk")
        snapshot = lineage_config_snapshot(config_path)
        identity = (snapshot.get("effective_sdc") or {}).get("recipe_sha256")
        if identity:
            row["sdc_recipe_sha256"] = str(identity)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        print(f"[lineage][WARN] cannot derive archived SDC recipe identity for "
              f"iter={row.get('iteration')} run={row.get('target_run_id')} ({exc}).",
              file=sys.stderr)


def load_stage_history(backup_dir: Path, platform: str, design: str,
                       max_iters: int, stage: str,
                       include_untrusted: bool = False) -> List[Dict]:
    """Load one stage and attach any statically reproducible config recipe.

    Routing recipes need the post-place CTS edge for the same source slot to prove
    that TNS_END_PERCENT was not changed after placement.  Load both stage views in
    that case, then return only the requested routing rows.
    """
    if stage == "routing":
        all_rows = load_resolved_stage_history(
            backup_dir, platform, design, max_iters, None, include_untrusted)
        cts_by_target = {
            (int(row["iteration"]), int(row["target_run_id"])): row
            for row in all_rows
            if row.get("stage") == "cts" and row.get("trusted") is True
        }
        rows = [row for row in all_rows if row.get("stage") == "routing"]
        for row in rows:
            _attach_archived_sdc_recipe_identity(
                row, backup_dir, platform, design)
            parent = cts_by_target.get(
                (int(row["iteration"]), int(row["source_run_id"])))
            if parent is not None:
                _attach_archived_sdc_recipe_identity(
                    parent, backup_dir, platform, design)
            recipe = config_recipe_for_lineage(row, parent)
            if recipe is not None:
                row["config_recipe"] = recipe
        return rows

    rows = load_resolved_stage_history(
        backup_dir, platform, design, max_iters, stage, include_untrusted)
    if stage == "cts":
        for row in rows:
            _attach_archived_sdc_recipe_identity(
                row, backup_dir, platform, design)
            recipe = config_recipe_for_lineage(row)
            if recipe is not None:
                row["config_recipe"] = recipe
    return rows


def load_lineage_history(backup_dir: Path, platform: str, design: str,
                         max_iters: int, stage: Optional[str] = None,
                         include_untrusted: bool = False) -> List[Dict]:
    return load_resolved_stage_history(
        backup_dir, platform, design, max_iters, stage, include_untrusted)


def load_resolved_history(backup_dir: Path, platform: str, design: str,
                          max_iters: int) -> List[Dict]:
    """Return reproducible clean rows plus trusted, lineage-resolved final children.

    This is deliberately separate from ``load_iteration_history`` so global elitism
    remains clean-only. It is intended for reporting and observed-best persistence.
    """
    clean = load_iteration_history(backup_dir, platform, design, max_iters)
    result = [dict(row, lineage_kind="clean", trusted=True) for row in clean]
    occupied = {(row["iteration"], row["run_id"]) for row in result}
    stage_rows = load_resolved_stage_history(
        backup_dir, platform, design, max_iters, include_untrusted=False)
    base = backup_dir / platform / design
    cts_by_target = {
        (int(row["iteration"]), int(row["target_run_id"])): row
        for row in stage_rows
        if row.get("stage") == "cts" and row.get("trusted") is True
    }

    # A routing clone is the last mutation and wins over a prior CTS event for the
    # same target. A CTS child is a final observation only when it was not overwritten.
    candidates = {}
    for row in stage_rows:
        key = (row["iteration"], row["run_id"])
        if row["stage"] == "cts" and row.get("overwritten_later"):
            continue
        if key not in candidates or row["stage"] == "routing":
            candidates[key] = row
    metric_cache = {}
    for (iter_num, run_id), row in candidates.items():
        if (iter_num, run_id) in occupied:
            continue
        if iter_num not in metric_cache:
            metric_cache[iter_num] = _metric_map(
                base / f"result_dump_{iter_num}", iter_num, "final")
        final_metrics = metric_cache[iter_num].get(run_id)
        if final_metrics is None or not row.get("effective_params"):
            continue
        cts_parent = (cts_by_target.get((iter_num, int(row["source_run_id"])))
                      if row.get("stage") == "routing" else None)
        _attach_archived_sdc_recipe_identity(
            row, backup_dir, platform, design)
        if cts_parent is not None:
            _attach_archived_sdc_recipe_identity(
                cts_parent, backup_dir, platform, design)
        recipe = config_recipe_for_lineage(row, cts_parent)
        resolved = {
            "iteration": iter_num,
            "run_id": run_id,
            "params": row["effective_params"],
            "metrics": final_metrics,
            "lineage_kind": row["stage"],
            "source_run_id": row["source_run_id"],
            "parent_family": row.get("parent_family"),
            "trusted": True,
            "stage_record": row,
        }
        if recipe is not None:
            row["config_recipe"] = recipe
            resolved["config_recipe"] = recipe
        result.append(resolved)
    return result


def best_history_entry(history: List[Dict], objective: str = "TNS_EVAL",
                       wl_base: float = 1.0, ecp_base: float = 1.0,
                       power_budget: Optional[float] = None,
                       power_base: Optional[float] = None) -> Optional[Dict]:
    """Select a best observation without mutating optimizer/elitism state."""
    scored = []
    for row in history:
        metrics = row.get("metrics", {})
        if objective == "wl":
            value = metrics.get("wl")
        elif objective == "ecp":
            value = metrics.get("ecp")
        elif objective == "TNS_EVAL":
            value = tns_eval_obj(metrics, power_budget, power_base)
        elif metrics.get("wl") is not None and metrics.get("ecp") is not None:
            value = 0.5 * (metrics["wl"] / wl_base) + 0.5 * (metrics["ecp"] / ecp_base)
        else:
            value = None
        if value is not None:
            scored.append((float(value), row))
    if not scored:
        return None
    value, row = min(scored, key=lambda item: item[0])
    return dict(row, objective_value=value)


def load_observed_best(backup_dir: Path, platform: str, design: str,
                       max_iters: int, objective: str = "TNS_EVAL",
                       wl_base: float = 1.0, ecp_base: float = 1.0,
                       power_budget: Optional[float] = None,
                       power_base: Optional[float] = None) -> Optional[Dict]:
    return best_history_entry(
        load_resolved_history(backup_dir, platform, design, max_iters),
        objective, wl_base, ecp_base, power_budget, power_base)


def load_clean_and_observed_best(
        backup_dir: Path, platform: str, design: str, max_iters: int,
        objective: str = "TNS_EVAL", wl_base: float = 1.0,
        ecp_base: float = 1.0, power_budget: Optional[float] = None,
        power_base: Optional[float] = None) -> Dict[str, Optional[Dict]]:
    """Two persistence views: reproducible clean/replay and all trusted observed."""
    resolved_history = load_resolved_history(backup_dir, platform, design, max_iters)
    clean_history = [row for row in resolved_history if row.get("lineage_kind") == "clean"]
    args = (objective, wl_base, ecp_base, power_budget, power_base)
    return {
        "clean_best": best_history_entry(clean_history, *args),
        "observed_best": best_history_entry(resolved_history, *args),
    }


load_resolved_best = load_observed_best


def build_history_summary(history: List[Dict], objective: str) -> str:
    """Build a text summary of parameter-metric history."""
    if not history:
        return "No previous history."

    lines = []
    iters = sorted(set(h["iteration"] for h in history))

    for it in iters:
        it_entries = [h for h in history if h["iteration"] == it]
        # Feasible = produced the metric(s) the objective needs (objective-agnostic
        # count so the combo case is reported correctly too).
        feasible = 0
        obj_values = []  # only for wl/ecp best/avg reporting
        for e in it_entries:
            m = e["metrics"]
            if objective == "wl":
                v = m.get("wl")
            elif objective == "ecp":
                v = m.get("ecp")
            elif objective == "TNS_EVAL":
                v = abs(m["tns"]) if m.get("tns") is not None else None
            else:
                v = m.get("wl") if (m.get("wl") is not None and m.get("ecp") is not None) else None
            if v is not None:
                feasible += 1
                if objective in ("wl", "ecp", "TNS_EVAL"):
                    obj_values.append(v)

        if feasible == 0:
            lines.append(f"Iteration {it}: {len(it_entries)} runs, "
                         f"0/{len(it_entries)} feasible (all failed routing/placement)")
        elif obj_values:
            best = min(obj_values)
            avg = sum(obj_values) / len(obj_values)
            lines.append(f"Iteration {it}: {len(it_entries)} runs, "
                         f"{feasible}/{len(it_entries)} feasible, "
                         f"best {objective}={best:.4f}, avg={avg:.4f}")
        else:  # combo: have feasibility count but best/avg computed elsewhere
            lines.append(f"Iteration {it}: {len(it_entries)} runs, "
                         f"{feasible}/{len(it_entries)} feasible")

    return "\n".join(lines) if lines else "No valid metrics in history."


def format_failed_configs(failed: List[Dict], param_names: List[str]) -> str:
    """Format failed runs' parameter sets for the LLM prompt."""
    if not failed:
        return "None (all runs produced a valid result this iteration)."

    lines = []
    for f in failed:
        params = f["params"]
        kv = ", ".join(
            f"{n}={params[n]:g}" if isinstance(params.get(n), float) else f"{n}={params[n]}"
            for n in param_names if n in params
        )
        lines.append(f"- Run {f['run_id']}: {kv}")
    return "\n".join(lines)


def generate_next_iteration_params(
    config: dict,
    platform: str,
    design: str,
    objective: str,
    num_runs: int,
    history: List[Dict],
    weight_wl: float = 0.5,
    weight_ecp: float = 0.5,
    total_iters: int = 6,
    explore_frac_override: Optional[float] = None,
    acquisition_override: Optional[str] = None,
    candidate_campaign_id: Optional[str] = None,
    candidate_iteration: Optional[int] = None,
    candidate_lifecycle_path: Optional[Path] = None,
    prompt_evidence: Optional[Mapping[str, Any]] = None,
    llm_enabled: bool = True,
    usage_context: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, float]]:
    """
    Generate parameter sets for the next iteration.

    Uses LLM + Bayesian optimization:
    - 50% exploitation: refine around best known configurations
    - 50% exploration: sample underexplored regions
    """
    design_cfg = get_design_config(config, platform, design)
    synthesis_constraints = get_param_constraints(config, "synthesis", design_cfg)
    placement_constraints = get_param_constraints(config, "placement", design_cfg)
    # Inter-iteration generation stops at the placement boundary. CTS and final
    # routing parameters are generated later from their observed stage metrics.
    cts_constraints: Dict[str, dict] = {}
    routing_constraints: Dict[str, dict] = {}

    all_constraints = {}
    all_constraints.update(synthesis_constraints)
    all_constraints.update(placement_constraints)

    clk_range = design_cfg["clock_period_range"] if design_cfg else [1.0, 10.0]
    all_constraints["clk_period"] = {
        "type": "float",
        "range": clk_range,
        "description": "Clock period",
    }

    param_names = list(all_constraints.keys())

    # Compute objective values for history entries
    wl_base = design_cfg["baseline"]["wl_base"] if design_cfg else 1.0
    ecp_base = design_cfg["baseline"]["ecp_base"] if design_cfg else 1.0

    # Power-budget constraint for objective=TNS_EVAL (default off). power_budget is a
    # fraction (e.g. 0.02 = +2%); power_base is baseline(run_1) power at CP_0.
    power_budget = config.get("power_budget") if config else None
    power_base_val = _power_base(platform, design)

    # Penalty value (objective units) assigned to runs that failed to produce a
    # valid result. Routing/placement failures (GRT-0232 congestion, DPL-0036)
    # leave wl/ecp = None; we keep their params as a "this region is infeasible"
    # data point so the optimizer steers away instead of re-proposing them.
    if objective == "wl":
        penalty = FAILURE_PENALTY_MULT * wl_base
    elif objective == "ecp":
        penalty = FAILURE_PENALTY_MULT * ecp_base
    elif objective == "TNS_EVAL":
        penalty = FAILURE_PENALTY_MULT * _tns_base(design_cfg, platform, design)
    else:
        penalty = FAILURE_PENALTY_MULT * (weight_wl + weight_ecp)

    valid_history = []
    for h in history:
        m = h["metrics"]
        if objective == "wl":
            obj_val = m.get("wl")
        elif objective == "ecp":
            obj_val = m.get("ecp")
        elif objective == "TNS_EVAL":
            obj_val = tns_eval_obj(m, power_budget, power_base_val)  # |TNS| + power penalty
        else:
            wl = m.get("wl")
            ecp = m.get("ecp")
            if wl is not None and ecp is not None:
                obj_val = weight_wl * (wl / wl_base) + weight_ecp * (ecp / ecp_base)
            else:
                obj_val = None

        if not h["params"]:
            continue
        # Failed run → large penalty instead of being discarded.
        history_candidate_id = _history_candidate_id(h)
        history_entry = {
            "params": h["params"],
            "objective": obj_val if obj_val is not None else penalty,
            "failed": obj_val is None,
            "iteration": h.get("iteration"),
            "run_id": h.get("run_id"),
        }
        if history_candidate_id is not None:
            history_entry[CANDIDATE_ID_KEY] = history_candidate_id
        valid_history.append(history_entry)

    all_params = []
    origin_counts: Dict[str, int] = defaultdict(int)

    def tagged(params: Mapping[str, Any], origin: str, *,
               stable_key: Optional[str] = None,
               parent: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """Assign immutable proposal identity before any later shaping pass."""
        origin_counts[origin] += 1
        proposal_index = origin_counts[origin]
        target_iteration = int(candidate_iteration or (
            max((h.get("iteration", 0) for h in history), default=0) + 1))
        campaign = str(candidate_campaign_id or f"adhoc:{platform}:{design}")
        proposal_key = stable_key or f"{origin}:{proposal_index}"
        parent_id = candidate_metadata(parent or {}).get(CANDIDATE_ID_KEY)
        return attach_candidate_metadata(
            params,
            candidate_id=make_candidate_id(campaign, target_iteration, proposal_key),
            origin=origin,
            parent=parent_id,
        )

    # --- Elitism: carry the best feasible configuration(s) forward verbatim ---
    # Re-evaluate (not perturb) the best-so-far so a good solution found in an
    # earlier iteration is never lost to the optimizer's exploration. Selected
    # from FEASIBLE runs only (penalty/failed entries excluded). Exploitation
    # below still perturbs around these, so we keep elitism small.
    feasible = [
        vh for vh in valid_history
        if not vh["failed"]
        and is_feasible_objective_value(vh["objective"], objective)
    ]
    if feasible:
        feasible_sorted = sorted(feasible, key=lambda x: x["objective"])
        n_elite = min(2, max(1, num_runs // 10), len(feasible_sorted))
        seen = set()
        for vh in feasible_sorted:
            if len(all_params) >= n_elite:
                break
            elite = dict(vh["params"])
            # Fill any missing/None param (e.g. clk_period if the backup SDC was
            # unreadable) with the range midpoint so the CSV row is complete.
            for name, info in all_constraints.items():
                if elite.get(name) is None:
                    lo, hi = info["range"]
                    elite[name] = (lo + hi) / 2
            elite = clip_params(elite, all_constraints)
            key = tuple(sorted((k, round(float(v), 6))
                               for k, v in elite.items() if v is not None))
            if key in seen:
                continue
            seen.add(key)
            all_params.append(tagged(
                elite,
                "replay",
                stable_key=(
                    f"replay:iter{vh.get('iteration')}:run{vh.get('run_id')}"
                ),
                parent=vh,
            ))
        if all_params:
            print(f"Elitism: carried forward {len(all_params)} best config(s), "
                  f"best objective={feasible_sorted[0]['objective']:.4f}")

    # --- LLM-guided generation ---
    current_iter = max((h["iteration"] for h in history), default=0)
    history_summary = build_history_summary(history, objective)

    # Exploration annealing: explore aggressively early, converge late. Late
    # iterations should stop injecting full-range random points (which produced
    # infeasible extremes like LB_ADDON≈0.96 and tanked routability); they should
    # refine the feasible region found so far.
    progress = min(1.0, max(0.0, current_iter / max(1, total_iters - 1)))
    explore_frac = 0.50 - 0.35 * progress      # 0.50 (early) -> 0.15 (late)
    perturb_factor = 0.15 - 0.08 * progress    # 0.15 (early) -> 0.07 (late)
    # Agent1 (ReAct model stage) may override the annealed exploration fraction.
    if explore_frac_override is not None:
        explore_frac = min(1.0, max(0.0, explore_frac_override))
    print(f"Annealing: iter {current_iter}/{total_iters}, "
          f"explore_frac={explore_frac:.2f}, perturb={perturb_factor:.3f}")

    # Get final metrics for the prompt, and collect the parameter sets of runs
    # that FAILED this iteration (no valid final metric) so the LLM can be told
    # to avoid those infeasible regions explicitly.
    current_metrics = []
    failed_param_sets = []
    for h in history:
        if h["iteration"] == current_iter:
            m = h["metrics"]
            wl = m.get("wl")
            ecp = m.get("ecp")
            combo = None
            if wl is not None and ecp is not None:
                combo = weight_wl * (wl / wl_base) + weight_ecp * (ecp / ecp_base)
            tns = h["metrics"].get("tns")
            current_metrics.append({
                "run_id": h["run_id"],
                "wl": wl,
                "ecp": ecp,
                "combo": combo,
                "tns": tns,
                "tns_source": m.get("tns_source"),
                "power": m.get("power"),
                "params": dict(h.get("params") or {}),
            })
            if objective == "wl":
                obj = wl
            elif objective == "ecp":
                obj = ecp
            elif objective == "TNS_EVAL":
                obj = tns_eval_obj(m, power_budget, power_base_val)
            else:
                obj = combo
            if not is_feasible_objective_value(obj, objective) and h["params"]:
                failed_param_sets.append({"run_id": h["run_id"], "params": h["params"]})

    failed_configs = format_failed_configs(failed_param_sets, param_names)

    evidence = dict(prompt_evidence or {})
    shared_context = build_shared_prompt_context(
        config, platform, design, objective, evidence)
    prompt = build_optimize_prompt(
        platform=platform,
        design=design,
        objective=objective,
        iteration=current_iter,
        num_runs=num_runs,
        results=current_metrics,
        history=history_summary,
        failed_configs=failed_configs,
        explore_frac=explore_frac,
        synthesis_constraints=synthesis_constraints,
        placement_constraints=placement_constraints,
        cts_constraints=cts_constraints,
        routing_constraints=routing_constraints,
        clk_period_range=clk_range,
        **shared_context,
        **{
            key: evidence.get(key)
            for key in (
                "objective_contract", "top_successful_configs",
                "stratified_bests", "basin_summary",
                "parameter_distributions", "distance_info",
                "run_classifications", "source_target_edges",
            )
        },
    )

    llm_params = None
    if llm_enabled:
        call_context = dict(usage_context or {})
        call_context.setdefault("scope", "inter_iteration")
        call_context.setdefault("stage", "next_batch")
        call_context.setdefault("agent", "agent2")
        call_context.setdefault("operation", "direct_parameter_proposal")
        call_context.setdefault("iteration", current_iter)
        call_context.setdefault("source_iteration", current_iter)
        call_context.setdefault(
            "target_iteration", int(candidate_iteration or current_iter + 1))
        llm_response = call_llm(
            prompt, config, usage_context=call_context)
        llm_params = parse_llm_json(llm_response)
    else:
        print("[no-llm][optimize] direct parameter proposals disabled; "
              "using Bayesian/exploit/LHS candidates.")

    # The LLM occasionally returns a single param set as a flat list of numbers
    # ([1, 85, ...]) instead of a list of dicts, or otherwise malformed entries.
    # Normalize a bare dict to a 1-element list and skip non-dict entries so one
    # bad response degrades gracefully to Bayesian fill instead of crashing the
    # whole campaign (clip_params expects a dict -> AttributeError on a float).
    if isinstance(llm_params, dict):
        llm_params = [llm_params]
    if llm_params:
        for p in llm_params[:max(0, num_runs - len(all_params))]:
            if not isinstance(p, dict):
                print(f"[optimize][WARN] skipping malformed LLM param entry "
                      f"(expected dict, got {type(p).__name__}): {p}", file=sys.stderr)
                continue
            clipped = clip_params(p, all_constraints)
            all_params.append(tagged(clipped, "llm"))

    # --- Bayesian-guided generation (fill remaining) ---
    remaining = num_runs - len(all_params)
    if remaining > 0 and len(valid_history) >= 3:
        X_obs = np.array([
            [vh["params"].get(n, 0) for n in param_names]
            for vh in valid_history
        ])
        y_obs = np.array([vh["objective"] for vh in valid_history])

        suggestions = bayesian_suggest(
            X_obs, y_obs, all_constraints,
            n_suggestions=remaining,
            seed=np.random.randint(0, 10000),
            acquisition=acquisition_override or "ei",   # Agent1's choice (agentic path)
        )
        all_params.extend(tagged(item, "bayes") for item in suggestions)

    # --- Fill any remaining with exploitation + exploration ---
    remaining = num_runs - len(all_params)
    if remaining > 0:
        if valid_history:
            # Exploitation: perturb best configurations. The exploit share and
            # the perturbation magnitude are annealed — later iterations exploit
            # more and perturb less, so the fill stops manufacturing extremes.
            best_entries = sorted(valid_history, key=lambda x: x["objective"])
            n_exploit = int(round((1.0 - explore_frac) * remaining))
            for i in range(n_exploit):
                base = best_entries[i % len(best_entries)]["params"]
                perturbed = perturb_params(base, all_constraints, perturb_factor,
                                           seed=np.random.randint(0, 10000))
                all_params.append(tagged(perturbed, "exploit", parent=(
                    best_entries[i % len(best_entries)])))
            remaining = num_runs - len(all_params)

        if remaining > 0:
            # Exploration: LHS (shrinks to ~explore_frac of the fill late on).
            # Derived seed: seed=None draws from OS entropy, bypassing DRP_SEED.
            lhs = latin_hypercube_sample(remaining, all_constraints,
                                         seed=np.random.randint(0, 10000))
            all_params.extend(tagged(item, "lhs") for item in lhs)

    all_params = all_params[:num_runs]

    if candidate_lifecycle_path is not None:
        from candidate_tracking import record_pool_stage

        record_pool_stage(
            candidate_lifecycle_path,
            all_params,
            "candidate_pool",
            campaign_id=(candidate_campaign_id or f"adhoc:{platform}:{design}"),
            iteration=(candidate_iteration or current_iter + 1),
            details={
                "generator": "optimize",
                "before_exploit_quota": True,
                "llm_enabled": bool(llm_enabled),
            },
        )

    # ── Unconditional exploitation quota ──
    # Reserve the tail ~20% of every batch for SMALL perturbations of the top-K
    # feasible historical configs (failure-penalty and power-infeasible observations
    # excluded). This guarantees exploitation of the best-known region regardless of
    # where the LLM instructions / wide-domain sampling drift (observed: a persisted
    # 'clk_period>=500' directive steered 54-74% of the population into the degenerate
    # slow-clock region while every baseline-beating config used 225-380 ps).
    applied_exploit_quota = 0
    feasible = sorted((vh for vh in valid_history
                       if not vh.get("failed") and vh["objective"] < penalty),
                      key=lambda x: x["objective"])
    if feasible and num_runs >= 5:
        n_front = max(2, num_runs // 10)          # keep the elites at the front intact
        quota = min(max(2, num_runs // 5), max(0, len(all_params) - n_front))
        topk = feasible[:3]
        for j in range(quota):
            base = dict(topk[j % len(topk)]["params"])
            for name, info in all_constraints.items():
                if base.get(name) is None:
                    lo, hi = info["range"]
                    base[name] = (lo + hi) / 2
            # Explicit derived seed: perturb_params(seed=None) uses OS entropy,
            # bypassing the campaign seed and breaking reproducibility.
            newp = perturb_params(base, all_constraints, perturbation_factor=0.10,
                                  seed=np.random.randint(0, 10000))
            target_index = len(all_params) - 1 - j
            all_params[target_index] = tagged(
                clip_params(newp, all_constraints),
                "exploit",
                stable_key=f"exploit-quota:slot{target_index + 1}:copy{j + 1}",
                parent=topk[j % len(topk)],
            )
        if quota:
            applied_exploit_quota = quota
            print(f"[exploit] quota: {quota}/{num_runs} tail slots -> perturbations of "
                  f"the top-{len(topk)} feasible configs "
                  f"(best objective {feasible[0]['objective']:.4f}).")

    if candidate_lifecycle_path is not None:
        from candidate_tracking import record_pool_stage

        record_pool_stage(
            candidate_lifecycle_path,
            all_params,
            "exploit_quota",
            details={"generator": "optimize", "quota_applied": applied_exploit_quota},
        )

    return all_params


def write_csv(params_list: List[Dict], output_path: Path,
              param_order: Optional[List[str]] = None) -> None:
    """Write parameter sets to CSV file for run_sequential.sh."""
    if not params_list:
        return

    if param_order is None:
        param_order = sorted(
            name for name in params_list[0].keys()
            if not str(name).startswith("_")
        )

    # Map to CSV column names expected by run_sequential.sh
    csv_columns = []
    for name in param_order:
        csv_columns.append(name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", newline="", dir=output_path.parent,
                prefix=f".{output_path.name}.", suffix=".tmp", delete=False) as f:
            temp_name = f.name
            writer = csv.DictWriter(f, fieldnames=csv_columns)
            writer.writeheader()
            for params in params_list:
                row = {}
                for name in csv_columns:
                    val = params.get(name, "")
                    if isinstance(val, float) and val == int(val):
                        val = int(val)
                    row[name] = val
                writer.writerow(row)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, output_path)
        temp_name = None
    finally:
        if temp_name:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    print(f"Wrote {len(params_list)} parameter sets to {output_path}")


def build_full_param_constraints(config: dict, platform: str,
                                 design: str) -> Dict[str, dict]:
    """Return the 10-D inter-iteration space, including the effective clock."""
    design_cfg = get_design_config(config, platform, design)
    constraints: Dict[str, dict] = {}
    for stage in ("synthesis", "placement"):
        constraints.update(get_param_constraints(config, stage, design_cfg))
    clk_range = design_cfg["clock_period_range"] if design_cfg else [1.0, 10.0]
    constraints["clk_period"] = {
        "type": "float",
        "range": list(clk_range),
        "description": "Clock period",
    }
    return constraints


def _print_policy_state(state: Dict, plan: Optional[Dict] = None) -> None:
    """Emit a compact, stable campaign-policy summary for the experiment log."""
    if not state.get("enabled"):
        return
    print(f"[search-policy] mode={state.get('mode')} "
          f"reason={state.get('transition_reason')} "
          f"pending_replays={len(state.get('pending_replays', []))}")
    for key, label in (("best_clean_replay", "clean/replay"),
                       ("best_observed_effective", "observed"),
                       ("best_routing_child", "routing-child"),
                       ("best_config_reproducible", "config-reproducible")):
        best = state.get(key)
        if isinstance(best, dict):
            print(f"[search-policy] best {label}: objective={best.get('objective'):.6g} "
                  f"iter={best.get('iteration')} run={best.get('run_id')}")
    if plan:
        print(f"[search-policy] next batch counts={plan.get('counts', {})} "
              f"protected_replay_slots={plan.get('protected_replay_slots', [])} "
              f"protected_probe_slots={plan.get('protected_probe_slots', [])} "
              f"protected_focus_control_slots="
              f"{plan.get('protected_focus_control_slots', [])}")


def main():
    """Compatibility entry point; CLI orchestration lives in optimize_cli.py."""
    from optimize_cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    main()
