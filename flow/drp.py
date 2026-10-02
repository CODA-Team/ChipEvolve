#!/usr/bin/env python3
"""
Doomed Run Prediction (DRP) for staged OpenROAD optimization.

Core logic:
1. Sort runs by objective metric (ascending = better)
2. Identify bottom M runs to kill
3. Identify top M runs to copy
4. Copy checkpoint files from source to target runs
5. Call agent.py to generate new stage-specific parameters
6. Update target run config files with new parameters
"""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lineage import (
    CHECKPOINT_FILES,
    CONFIG_PARAM_NAMES,
    STAGE_PARAM_NAMES,
    checkpoint_snapshot,
    config_snapshot,
    evaluate_trust,
    file_sha256 as lineage_file_sha256,
    utc_now,
    write_stage_summary,
)
from drp_selection import (
    _finite_metric,
    _systematic_resample,
    gwtw_select,
    select_survivors_and_victims,
    sort_runs,
)


_PREDICTOR_SCORE_FIELDS = (
    "kill_score",
    "promising_score",
    "power_violation_probability",
    "power_feasible_probability",
    "tns_worse_probability",
    "tns_better_probability",
)
_PREDICTOR_AUDIT_FIELDS = (
    "progress",
    "baseline_clock_ratio",
    "ongoing_clock_ratio",
)

_CLEAN_IDENTITY_RESERVATION_KEY = "clean_identity_reservation"
_CLEAN_IDENTITY_RESERVATION_SCHEMA = 1


def _file_sha256(path: Optional[Path]) -> Optional[str]:
    """Return a model artifact hash for result provenance."""
    if path is None or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_predictor_scores(raw_scores, run_ids: List[int]) -> Dict[int, Optional[Dict]]:
    """Validate the public predictor_bridge score schema before ranking on it."""
    if not isinstance(raw_scores, dict):
        raise RuntimeError("predictor returned a non-dict score batch")

    scores: Dict[int, Optional[Dict]] = {}
    for rid in run_ids:
        raw = raw_scores.get(rid)
        if raw is None:
            scores[rid] = None
            continue
        if not isinstance(raw, dict):
            raise RuntimeError(f"predictor score for run {rid} is not a dict")
        missing = [key for key in _PREDICTOR_SCORE_FIELDS if key not in raw]
        if missing:
            raise RuntimeError(
                f"predictor score for run {rid} is missing fields {missing}")
        details = {}
        for key in _PREDICTOR_SCORE_FIELDS:
            try:
                value = float(raw[key])
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"predictor score {key} for run {rid} is not numeric") from exc
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise RuntimeError(
                    f"predictor score {key} for run {rid} is outside [0, 1]: {value}")
            details[key] = value
        # The V2 bridge also reports the exact temporal/clock context used by the
        # Transformer. Keep it in the DRP JSON when present so a ranking can be
        # reproduced without reopening every generated SDC file.
        for key in _PREDICTOR_AUDIT_FIELDS:
            if key not in raw:
                continue
            try:
                value = float(raw[key])
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"predictor audit field {key} for run {rid} is not numeric") from exc
            valid = math.isfinite(value) and value > 0.0
            if key == "progress":
                valid = valid and value <= 1.0
            if not valid:
                raise RuntimeError(
                    f"predictor audit field {key} for run {rid} is invalid: {value}")
            details[key] = value
        scores[rid] = details
    return scores


def load_metrics(metrics_file: Path) -> List[Dict]:
    """Load run metrics from JSON file."""
    with open(metrics_file) as f:
        return json.load(f)


def predictor_active(predictor: bool, objective: str) -> Tuple[bool, str]:
    """The -P flag alone decides the DRP ranking key (no objective gating):
      -P     -> predict_model promising/kill score ranks the runs,
      no -P  -> the intermediate stage metric (e.g. CP_0 stage TNS_EVAL) ranks them.
    Both paths are kept on purpose so predictor effectiveness can be validated by
    A/B on the same seed. Dual elitism protects true-objective top-K runs whenever
    the learned rank key is active."""
    return predictor, ""


def resolve_explicit_protection(metrics: List[Dict], protect_runs: List[int],
                                objective: str, stage: str,
                                abort_on_fail: bool) -> set:
    """Identity-based DRP kill protection for specific run slots.

    iter 1: run_1 is the UNPERTURBED DEFAULT config — the baseline. Everything the
    campaign anchors on derives from its genuine final result (CP_0 = its ECP x 0.9,
    tns_base/power_base, the predictor's default baseline trajectory, and the
    "best is never worse than baseline" contract). If DRP kills it, copy_checkpoint/
    copy_source_config overwrite its slot with ANOTHER config and every one of those
    anchors silently becomes a pseudo-baseline. So with abort_on_fail=True a protected
    run that FAILED the stage is a fatal error (exit 3): report "baseline failed"
    loudly instead of fabricating a fake one.

    iter 2+: run_1 is the elitism-carried BEST-so-far replay (the comparison anchor).
    It must not be killed mid-iteration while healthy, but its failure is NOT fatal —
    protection is simply waived and normal failure handling kills it.

    Returns objective-valid run_ids. ``run_drp`` additionally requires their current
    stage checkpoint before protection is allowed to take effect.
    """
    protected = set()
    for rid in sorted(set(protect_runs or [])):
        m = next((x for x in metrics if x.get("run_id") == rid), None)
        if m is not None and _finite_metric(m.get(objective)):
            protected.add(rid)
            continue
        if abort_on_fail:
            print(f"ABORT: baseline run {rid} FAILED the {stage} stage (no valid "
                  f"{objective}). Refusing to overwrite its slot and fabricate a "
                  f"pseudo-baseline (CP_0/tns_base/power_base/baseline trajectory "
                  f"all derive from it) — fix the default config/flow first.",
                  file=sys.stderr)
            sys.exit(3)
        print(f"[protect] run {rid} has no valid {objective} at {stage}; identity "
              f"protection waived (normal failure handling applies).")
    return protected


def resolve_clean_identity_protection(
    stage: str,
    sorted_metrics: List[Dict],
    source_eligible_ids: set,
    quota: int,
    candidate_lifecycle: Optional[Path],
    iteration: int,
    explicit_protected_ids: Optional[set] = None,
) -> Tuple[set, Dict[str, Any]]:
    """Reserve original candidate identities across both GWTW decisions.

    The post-place call creates an identity reservation in the candidate lifecycle.
    The post-CTS call resolves those stable identities back to their current slots and
    supplements failed reservations only with candidates that were not cloned at
    post-place.  Thus every returned post-CTS slot still belongs to its input-batch
    identity.  A stage failure can make a reservation ineligible; if there are not
    enough other clean identities to satisfy the quota, abort rather than silently
    lowering the amount of attributable final-flow evidence.

    ``quota`` is capped by population size so the default quota of 10 also works for
    small test campaigns.  Protection covers DRP replacement through CTS; a later
    route/finish failure can still prevent an identity from producing final metrics.
    """
    if stage not in {"place", "cts"}:
        raise ValueError(f"unsupported clean-identity protection stage: {stage!r}")
    if isinstance(quota, bool) or not isinstance(quota, int) or quota < 0:
        raise ValueError("clean identity quota must be a non-negative integer")

    population_ids = [int(metric["run_id"]) for metric in sorted_metrics]
    if len(population_ids) != len(set(population_ids)):
        raise RuntimeError("clean identity protection requires unique run ids")
    effective_quota = min(quota, len(population_ids))
    disabled = {
        "enabled": False,
        "stage": stage,
        "requested_quota": quota,
        "effective_quota": effective_quota,
        "protected_run_ids": [],
        "protected_candidate_ids": [],
    }
    if effective_quota == 0:
        return set(), disabled
    if candidate_lifecycle is None:
        raise RuntimeError(
            "GWTW clean identity quota requires --candidate-lifecycle so the same "
            "candidate entities can be protected at post-place and post-CTS")

    from candidate_tracking import _atomic_write_json, load_lifecycle

    lifecycle_path = Path(candidate_lifecycle)
    if not lifecycle_path.is_file():
        raise RuntimeError(
            f"GWTW clean identity quota lifecycle is missing: {lifecycle_path}")
    payload = load_lifecycle(lifecycle_path)
    if int(payload.get("iteration", -1)) != int(iteration):
        raise RuntimeError(
            "clean identity lifecycle iteration does not match DRP iteration")

    slots = payload.get("slots", [])
    slots_by_run: Dict[int, Dict[str, Any]] = {}
    slots_by_candidate: Dict[str, Dict[str, Any]] = {}
    for slot in slots:
        try:
            run_id = int(slot["run_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(
                "candidate lifecycle contains an invalid run slot") from exc
        candidate_id = str(slot.get("candidate_id") or "").strip()
        if not candidate_id:
            raise RuntimeError(
                f"candidate lifecycle run {run_id} has no candidate identity")
        if run_id in slots_by_run or candidate_id in slots_by_candidate:
            raise RuntimeError(
                "candidate lifecycle clean-identity slots are not unique")
        slots_by_run[run_id] = slot
        slots_by_candidate[candidate_id] = slot
    if set(slots_by_run) != set(population_ids):
        raise RuntimeError(
            "candidate lifecycle run slots do not match the DRP population")

    previous = payload.get(_CLEAN_IDENTITY_RESERVATION_KEY)
    previous_entries: List[Dict[str, Any]] = []
    if previous is not None:
        if (not isinstance(previous, dict)
                or previous.get("schema_version")
                != _CLEAN_IDENTITY_RESERVATION_SCHEMA
                or int(previous.get("iteration", -1)) != int(iteration)):
            raise RuntimeError("candidate lifecycle has an invalid clean reservation")
        if (previous.get("requested_quota") != quota
                or previous.get("effective_quota") != effective_quota):
            raise RuntimeError(
                "clean identity quota changed between DRP stages")
        raw_entries = previous.get("identities", [])
        if not isinstance(raw_entries, list):
            raise RuntimeError("candidate lifecycle clean reservation is malformed")
        previous_entries = [entry for entry in raw_entries
                            if isinstance(entry, dict)]
        if len(previous_entries) != len(raw_entries):
            raise RuntimeError("candidate lifecycle clean reservation is malformed")

    eligible = set(int(run_id) for run_id in source_eligible_ids)

    def is_original(slot: Dict[str, Any]) -> bool:
        # A successful DRP clone installs a fresh child and moves the displaced input
        # identity into this list.  Source slots are unchanged when cloned elsewhere.
        superseded = slot.get("superseded_candidate_ids", [])
        return isinstance(superseded, list) and not superseded

    clean_eligible = {
        run_id for run_id, slot in slots_by_run.items()
        if run_id in eligible and is_original(slot)
    }
    if len(clean_eligible) < effective_quota:
        raise RuntimeError(
            f"GWTW clean identity quota cannot be met at post-{stage}: need "
            f"{effective_quota}, but only {len(clean_eligible)} original candidate "
            "identities have a valid stage checkpoint/objective")

    selected: List[Dict[str, Any]] = []
    selected_ids: set = set()

    def add_slot(slot: Optional[Dict[str, Any]], reserved_at_stage: str) -> None:
        if slot is None:
            return
        run_id = int(slot["run_id"])
        candidate_id = str(slot["candidate_id"])
        if (run_id not in clean_eligible or candidate_id in selected_ids
                or len(selected) >= effective_quota):
            return
        selected.append({
            "candidate_id": candidate_id,
            "run_id": run_id,
            "reserved_at_stage": reserved_at_stage,
        })
        selected_ids.add(candidate_id)

    # Stable identity, not run number, carries the reservation across stages.  This
    # also detects an unexpected overwrite even if a child later occupies that slot.
    previous_by_id = {
        str(entry.get("candidate_id") or ""): entry for entry in previous_entries
    }
    for entry in previous_entries:
        candidate_id = str(entry.get("candidate_id") or "").strip()
        if not candidate_id:
            raise RuntimeError("clean reservation contains an empty candidate id")
        add_slot(
            slots_by_candidate.get(candidate_id),
            str(entry.get("reserved_at_stage") or "place"),
        )

    # Explicit replay/probe/baseline protection already spends a survivor slot, so
    # count clean members of that set toward the quota before adding ranked rows.
    explicit = set(explicit_protected_ids or ())
    for run_id in sorted(explicit):
        add_slot(slots_by_run.get(int(run_id)), stage)
    for metric in sorted_metrics:
        add_slot(slots_by_run[int(metric["run_id"])], stage)

    if len(selected) != effective_quota:
        raise RuntimeError(
            f"GWTW clean identity reservation selected {len(selected)} identities; "
            f"expected {effective_quota}")

    selected_candidate_ids = [entry["candidate_id"] for entry in selected]
    selected_run_ids = [entry["run_id"] for entry in selected]
    carried_ids = [candidate_id for candidate_id in selected_candidate_ids
                   if candidate_id in previous_by_id]
    supplemented_ids = [candidate_id for candidate_id in selected_candidate_ids
                        if candidate_id not in previous_by_id]
    dropped_ids = [candidate_id for candidate_id in previous_by_id
                   if candidate_id not in selected_ids]
    record = {
        "stage": stage,
        "clean_stage_eligible_count": len(clean_eligible),
        "protected_run_ids": selected_run_ids,
        "protected_candidate_ids": selected_candidate_ids,
        "carried_candidate_ids": carried_ids,
        "supplemented_candidate_ids": supplemented_ids,
        "dropped_candidate_ids": dropped_ids,
    }
    old_records = (previous or {}).get("stage_records", [])
    if not isinstance(old_records, list):
        raise RuntimeError("candidate lifecycle clean stage records are malformed")
    stage_records = [item for item in old_records
                     if isinstance(item, dict) and item.get("stage") != stage]
    stage_records.append(record)
    reservation = {
        "schema_version": _CLEAN_IDENTITY_RESERVATION_SCHEMA,
        "iteration": int(iteration),
        "requested_quota": quota,
        "effective_quota": effective_quota,
        "population_size": len(population_ids),
        "status": ("reserved_post_place" if stage == "place"
                   else "protected_through_post_cts"),
        "identities": selected,
        "stage_records": stage_records,
        "updated_utc": utc_now(),
    }
    payload[_CLEAN_IDENTITY_RESERVATION_KEY] = reservation
    payload["updated_utc"] = reservation["updated_utc"]
    _atomic_write_json(lifecycle_path, payload)

    audit = {
        "enabled": True,
        "stage": stage,
        "requested_quota": quota,
        "effective_quota": effective_quota,
        **record,
    }
    return set(selected_run_ids), audit


def _checkpoint_path(results_base: Path, platform: str, design: str,
                     run_id: int, stage: str) -> Path:
    checkpoint_name = CHECKPOINT_FILES.get(stage)
    if checkpoint_name is None:
        raise ValueError(f"unsupported DRP checkpoint stage: {stage!r}")
    return (Path(results_base) / platform / design / f"run_{run_id}"
            / checkpoint_name)


def resolve_source_eligibility(metrics: List[Dict], objective: str,
                               results_base: Path, platform: str,
                               design: str, stage: str
                               ) -> Tuple[set, Dict[int, List[str]]]:
    """Resolve the hard prerequisites for advancing or cloning a staged run.

    Predictor coverage is deliberately not part of this check. A model may score a
    partial trajectory for audit purposes, but only a run with a real objective and a
    non-empty stage checkpoint can survive DRP or supply an offspring checkpoint.
    """
    checkpoint_name = CHECKPOINT_FILES.get(stage)
    if checkpoint_name is None:
        raise ValueError(f"unsupported DRP checkpoint stage: {stage!r}")

    eligible = set()
    reasons: Dict[int, List[str]] = {}
    for metric in metrics:
        run_id = metric["run_id"]
        failures = []
        if not _finite_metric(metric.get(objective)):
            failures.append(f"invalid_{objective}")

        checkpoint = _checkpoint_path(
            results_base, platform, design, run_id, stage)
        try:
            checkpoint_ready = checkpoint.is_file() and checkpoint.stat().st_size > 0
        except OSError:
            checkpoint_ready = False
        if not checkpoint_ready:
            failures.append(f"missing_or_empty_{checkpoint_name}")

        metric["drp_source_eligible"] = not failures
        metric["drp_source_ineligible_reasons"] = list(failures)
        if failures:
            reasons[run_id] = failures
        else:
            eligible.add(run_id)
    return eligible, reasons


def copy_checkpoint(source_run_id: int, target_run_id: int,
                    results_base: Path, objects_base: Path,
                    reports_base: Path, logs_base: Path,
                    platform: str, design: str,
                    stage: str,
                    hash_cache: Optional[Dict] = None) -> Dict:
    """
    Copy checkpoint files from source run to target run.

    For 'place' stage: copy all results so CTS can start fresh
    For 'cts' stage: copy all results including CTS so routing can start fresh
    """
    src_results = results_base / platform / design / f"run_{source_run_id}"
    tgt_results = results_base / platform / design / f"run_{target_run_id}"
    src_objects = objects_base / platform / design / f"run_{source_run_id}"
    tgt_objects = objects_base / platform / design / f"run_{target_run_id}"

    outcome = {
        "status": "failed",
        "error": None,
        "source_results": str(src_results),
        "target_results": str(tgt_results),
        "checkpoint": None,
        "target_checkpoint_path": None,
        "target_checkpoint_size_bytes": None,
        "objects_copy": "not_attempted",
        "combined_log_copy": "not_attempted",
        "step_logs_copy": "not_attempted",
    }
    checkpoint_name = CHECKPOINT_FILES.get(stage)
    if checkpoint_name is None:
        outcome["error"] = f"unsupported checkpoint stage: {stage}"
        return outcome
    if not src_results.is_dir():
        outcome["error"] = f"source results dir not found: {src_results}"
        print(f"[DRP][ERROR] {outcome['error']}", file=sys.stderr)
        return outcome

    source_checkpoint = src_results / checkpoint_name
    if not source_checkpoint.is_file():
        outcome["error"] = f"source checkpoint not found: {source_checkpoint}"
        print(f"[DRP][ERROR] {outcome['error']}", file=sys.stderr)
        return outcome
    try:
        checkpoint_stat = source_checkpoint.stat()
        checkpoint_sha = lineage_file_sha256(source_checkpoint, hash_cache)
        outcome["checkpoint"] = {
            "path": str(source_checkpoint),
            "name": checkpoint_name,
            "size_bytes": checkpoint_stat.st_size,
            "sha256": checkpoint_sha,
            "identity": f"{checkpoint_name}:{checkpoint_sha}",
        }

        # Copy into a temporary sibling first. A failed copy must not leave a partial
        # checkpoint tree that a later make invocation could mistake for a valid clone.
        temp_results = tgt_results.with_name(
            f".{tgt_results.name}.clone-{os.getpid()}-{target_run_id}")
        if temp_results.exists():
            shutil.rmtree(temp_results)
        try:
            shutil.copytree(src_results, temp_results)
            if stage == "place":
                _remove_stage_files(temp_results, ["4_", "5_", "6_"])
            elif stage == "cts":
                _remove_stage_files(temp_results, ["5_", "6_"])

            target_checkpoint = temp_results / checkpoint_name
            if (not target_checkpoint.is_file()
                    or target_checkpoint.stat().st_size != checkpoint_stat.st_size):
                raise IOError(
                    f"copied checkpoint verification failed: {target_checkpoint}")
            if tgt_results.exists():
                shutil.rmtree(tgt_results)
            temp_results.replace(tgt_results)
        finally:
            if temp_results.exists():
                shutil.rmtree(temp_results)

        # Copy objects directory (for copyright.txt and other Make requirements).
        if src_objects.exists():
            if tgt_objects.exists():
                shutil.rmtree(tgt_objects)
            shutil.copytree(src_objects, tgt_objects)
            outcome["objects_copy"] = "ok"
        else:
            outcome["objects_copy"] = "source_missing_optional"

    # Copy the per-run combined log too, so the target inherits the source's
    # log history rather than keeping its own stale one. run_stage.sh APPENDS
    # each stage to logs/{platform}_{design}_run{N}.log; without this, the next
    # stage's output is appended onto the victim's old log and metric extraction
    # (HPWL table, timing report, ...) reads the wrong run's data — e.g. a
    # victim cloned from a good placement would still report its own failed-place
    # log (wl=None). At each DRP checkpoint the source's log only spans up to the
    # current stage (later stages have not run yet), so a plain copy is correct
    # and needs no truncation.
        src_log = logs_base / f"{platform}_{design}_run{source_run_id}.log"
        tgt_log = logs_base / f"{platform}_{design}_run{target_run_id}.log"
        if src_log.exists():
            shutil.copy2(src_log, tgt_log)
            outcome["combined_log_copy"] = "ok"
        else:
            outcome["combined_log_copy"] = "source_missing_optional"

    # Per-run step-log directory (fallback source for extraction), if present.
        src_log_dir = logs_base / platform / design / f"run_{source_run_id}"
        tgt_log_dir = logs_base / platform / design / f"run_{target_run_id}"
        if src_log_dir.exists():
            if tgt_log_dir.exists():
                shutil.rmtree(tgt_log_dir)
            shutil.copytree(src_log_dir, tgt_log_dir)
            outcome["step_logs_copy"] = "ok"
        else:
            outcome["step_logs_copy"] = "source_missing_optional"

        installed_checkpoint = tgt_results / checkpoint_name
        outcome["target_checkpoint_path"] = str(installed_checkpoint)
        outcome["target_checkpoint_size_bytes"] = installed_checkpoint.stat().st_size
        outcome["status"] = "ok"
        print(f"  Checkpoint copied: run_{source_run_id} → run_{target_run_id} "
              f"(stage={stage}, id={outcome['checkpoint']['identity'][:28]}...)")
    except Exception as exc:
        outcome["error"] = str(exc)
        print(f"[DRP][ERROR] checkpoint copy run_{source_run_id} -> "
              f"run_{target_run_id} failed: {exc}", file=sys.stderr)
    return outcome


def _remove_stage_files(results_dir: Path, prefixes: List[str]) -> None:
    """Remove files matching given stage prefixes from results directory."""
    if not results_dir.exists():
        return
    for f in results_dir.iterdir():
        if any(f.name.startswith(p) for p in prefixes):
            f.unlink()


def update_config_params(config_path: Path, params: Dict[str, float]) -> Dict:
    """
    Update parameters in a config.mk file.
    Adds or replaces export lines for each parameter.
    """
    outcome = {"status": "failed", "error": None, "config_path": str(config_path),
               "before_sha256": None, "after_sha256": None}
    if not config_path.is_file():
        outcome["error"] = f"config file not found: {config_path}"
        print(f"[DRP][ERROR] {outcome['error']}", file=sys.stderr)
        return outcome

    try:
        outcome["before_sha256"] = lineage_file_sha256(config_path)
        content = config_path.read_text()
    except Exception as exc:
        outcome["error"] = str(exc)
        return outcome

    for name, value in params.items():
        # Format value
        if isinstance(value, float) and value == int(value):
            val_str = str(int(value))
        elif isinstance(value, float):
            val_str = f"{value:.4f}".rstrip("0").rstrip(".")
        else:
            val_str = str(value)

        # Try to replace existing line
        # Anchor the complete assignment line. Without the leading boundary, updating
        # PIN_LAYER_ADJUST also matches the suffix of FLOORPLAN_PIN_LAYER_ADJUST and
        # destroys the floorplan-time context needed by config-level replay.
        pattern = rf'(?m)^\s*(?:export\s+)?{re.escape(name)}\s*=.*$'
        replacement = f"export {name} = {val_str}"
        new_content, count = re.subn(pattern, replacement, content)

        if count > 0:
            content = new_content
        else:
            # Add new line before end of file
            content = content.rstrip("\n") + f"\nexport {name} = {val_str}\n"

    try:
        config_path.write_text(content)
        outcome["after_sha256"] = lineage_file_sha256(config_path)
        outcome["status"] = "ok"
    except Exception as exc:
        outcome["error"] = str(exc)
        print(f"[DRP][ERROR] config update failed for {config_path}: {exc}",
              file=sys.stderr)
    return outcome


def copy_source_config(source_run_id: int, target_run_id: int,
                       config_dir: Path) -> Dict:
    """Copy source run's config.mk to target run's config.mk."""
    src_config = config_dir / f"config_{source_run_id}.mk"
    tgt_config = config_dir / f"config_{target_run_id}.mk"

    outcome = {
        "status": "failed",
        "error": None,
        "source_path": str(src_config),
        "target_path": str(tgt_config),
        "source_sha256": None,
        "target_sha256": None,
    }
    if not src_config.is_file():
        outcome["error"] = f"source config not found: {src_config}"
        print(f"[DRP][ERROR] {outcome['error']}", file=sys.stderr)
        return outcome
    try:
        outcome["source_sha256"] = lineage_file_sha256(src_config)
        shutil.copy2(src_config, tgt_config)
        outcome["target_sha256"] = lineage_file_sha256(tgt_config)
        if outcome["source_sha256"] != outcome["target_sha256"]:
            raise IOError(f"config copy hash mismatch: {src_config} -> {tgt_config}")
        outcome["status"] = "ok"
        print(f"  Config copied: config_{source_run_id}.mk → config_{target_run_id}.mk")
    except Exception as exc:
        outcome["error"] = str(exc)
        print(f"[DRP][ERROR] config copy run_{source_run_id} -> "
              f"run_{target_run_id} failed: {exc}", file=sys.stderr)
    return outcome


def _lineage_iteration(metrics_file: Path) -> int:
    """Resolve the campaign iteration for the lineage filename and event ids."""
    raw = os.environ.get("DRP_ITER", "").strip()
    if raw.isdigit():
        return int(raw)
    match = re.search(r"iter(\d+)", Path(metrics_file).name)
    return int(match.group(1)) if match else 0


def _candidate_edge_payload(event: Dict) -> Dict[str, Any]:
    """Return the stable DRP edge contract embedded in the result JSON."""
    effective_config = (
        event.get("target_config") or event.get("target_config_before_clone"))
    return {
        "lineage_event_id": event.get("event_id"),
        "iteration": event.get("iteration"),
        "stage": event.get("stage"),
        "next_stage": event.get("next_stage"),
        "source_run_id": event.get("source_run_id"),
        "target_run_id": event.get("target_run_id"),
        "source_candidate_id": None,
        "target_candidate_id": None,
        "replaced_candidate_id": None,
        "replaced_target_candidate_id": None,
        "generated_params": event.get("generated_params"),
        "generated_origin": event.get("generated_origin"),
        "generated_provenance": event.get("generated_provenance"),
        "mutation_expected": bool(event.get("mutation_expected", True)),
        "mutation_applied": bool(event.get("mutation_applied", False)),
        "trusted": bool(event.get("trusted", False)),
        "trust_reasons": list(event.get("trust_reasons") or []),
        "operation_status": dict(event.get("status") or {}),
        "effective_params": dict(event.get("effective_params") or {}),
        "effective_config": effective_config,
        "config_sha256": event.get("config_sha256"),
        "lifecycle_recorded": False,
        "lifecycle_event_id": None,
    }


def _candidate_edge_fingerprint(edge: Dict[str, Any]) -> str:
    """Fingerprint physical edge semantics, excluding tracking-only identities."""
    semantic = {
        key: edge.get(key) for key in (
            "lineage_event_id", "iteration", "stage", "next_stage",
            "source_run_id", "target_run_id", "generated_params",
            "generated_origin", "generated_provenance",
            "mutation_expected", "mutation_applied", "trusted",
            "trust_reasons", "operation_status", "effective_params",
            "config_sha256",
        )
    }
    raw = json.dumps(
        semantic, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _record_candidate_edges(
    lifecycle_path: Optional[Path], finalized_events: List[Dict]
) -> List[Dict[str, Any]]:
    """Append DRP clone attempts to candidate lifecycle exactly once per edge.

    A successful config copy installs a child identity even when the later mutation
    or lineage verification fails. A preflight/copy failure only records the attempt,
    because the target slot still contains its original candidate.
    """
    edges = [_candidate_edge_payload(event) for event in finalized_events]
    if lifecycle_path is None or not edges:
        return edges

    from candidate_tracking import (
        attach_metadata,
        load_lifecycle,
        record_candidate_stage,
        record_clone_event,
    )

    lifecycle_path = Path(lifecycle_path)
    if not lifecycle_path.is_file():
        raise RuntimeError(
            f"candidate lifecycle is required for DRP but missing: {lifecycle_path}")

    def slot(payload: Dict, run_id: int) -> Dict:
        matches = [item for item in payload.get("slots", [])
                   if int(item.get("run_id", -1)) == int(run_id)]
        if len(matches) != 1:
            raise RuntimeError(
                f"candidate lifecycle has no unique run slot {run_id}")
        return matches[0]

    for lineage_event, edge in zip(finalized_events, edges):
        edge_key = str(edge.get("lineage_event_id") or "").strip()
        if not edge_key:
            raise RuntimeError("DRP lineage event has no stable event_id")
        fingerprint = _candidate_edge_fingerprint(edge)
        payload = load_lifecycle(lifecycle_path)
        if int(payload.get("iteration", -1)) != int(edge.get("iteration", -2)):
            raise RuntimeError(
                "candidate lifecycle iteration does not match DRP lineage event")

        previous = []
        for recorded in payload.get("events", []):
            details = recorded.get("details") or {}
            if (details.get("lifecycle_kind") == "drp_candidate_edge"
                    and details.get("candidate_edge_key") == edge_key):
                previous.append(recorded)
        if previous:
            if len(previous) != 1:
                raise RuntimeError(
                    f"duplicate lifecycle records for DRP edge {edge_key}")
            recorded = previous[0]
            details = recorded.get("details") or {}
            if details.get("edge_fingerprint") != fingerprint:
                raise RuntimeError(
                    f"DRP edge {edge_key} changed after it was recorded")
            edge.update({
                "source_candidate_id": details.get("source_candidate_id"),
                "target_candidate_id": recorded.get("candidate_id"),
                "replaced_candidate_id": details.get("replaced_candidate_id"),
                "replaced_target_candidate_id": details.get(
                    "replaced_candidate_id"),
                "lifecycle_recorded": True,
                "lifecycle_event_id": recorded.get("event_id"),
                "lifecycle_idempotent_reuse": True,
            })
            continue

        source_run_id = edge.get("source_run_id")
        target_run_id = edge.get("target_run_id")
        if target_run_id is None:
            raise RuntimeError(f"DRP edge {edge_key} has no target run")
        target_before = slot(payload, int(target_run_id))
        replaced_candidate_id = target_before.get("candidate_id")
        source_candidate_id = None
        if source_run_id is not None:
            source_candidate_id = slot(payload, int(source_run_id)).get("candidate_id")

        detail = {
            "lifecycle_kind": "drp_candidate_edge",
            "candidate_edge_key": edge_key,
            "edge_fingerprint": fingerprint,
            "source_run_id": source_run_id,
            "target_run_id": target_run_id,
            "source_candidate_id": source_candidate_id,
            "replaced_candidate_id": replaced_candidate_id,
            "generated_params": edge.get("generated_params"),
            "generated_origin": edge.get("generated_origin"),
            "generated_provenance": edge.get("generated_provenance"),
            "mutation_expected": edge.get("mutation_expected"),
            "mutation_applied": edge.get("mutation_applied"),
            "trusted": edge.get("trusted"),
            "trust_reasons": edge.get("trust_reasons"),
            "operation_status": edge.get("operation_status"),
            "effective_params": edge.get("effective_params"),
            "effective_config": edge.get("effective_config"),
            "config_sha256": edge.get("config_sha256"),
        }
        lifecycle_status = "trusted" if edge.get("trusted") else "failed"
        config_installed = (
            source_run_id is not None
            and (lineage_event.get("status") or {}).get("checkpoint_copy") == "ok"
            and (lineage_event.get("status") or {}).get("config_copy") == "ok"
        )

        if config_installed:
            source_before = slot(payload, int(source_run_id))
            origin = (
                edge.get("generated_origin")
                if edge.get("mutation_applied")
                else source_before.get("origin"))
            applied_params = (
                edge.get("generated_params")
                if edge.get("mutation_applied")
                and isinstance(edge.get("generated_params"), dict)
                else {})
            payload = record_clone_event(
                lifecycle_path,
                f"drp_{edge.get('stage')}",
                int(source_run_id),
                int(target_run_id),
                generated_params=applied_params,
                origin=origin,
                proposal_key=f"drp-edge:{edge_key}",
                status=lifecycle_status,
                details=detail,
            )
            recorded = payload["events"][-1]

            # Synchronize the child with the verified physical config. This covers
            # frozen clones (preserved routing knobs) and failed/partial mutations.
            effective_params = edge.get("effective_params") or {}
            if effective_params:
                current = slot(payload, int(target_run_id))
                effective_candidate = attach_metadata(
                    effective_params,
                    candidate_id=current["candidate_id"],
                    origin=current["origin"],
                    parent=current.get("parent"),
                )
                record_candidate_stage(
                    lifecycle_path,
                    effective_candidate,
                    f"drp_{edge.get('stage')}_effective_config",
                    run_id=int(target_run_id),
                    status=lifecycle_status,
                    details={
                        "lifecycle_kind": "drp_effective_config",
                        "candidate_edge_key": edge_key,
                        "config_sha256": edge.get("config_sha256"),
                    },
                )
        else:
            # The target was not replaced; record the failed attempt against its
            # existing identity without manufacturing a child configuration.
            candidate = attach_metadata(
                target_before.get("current_params") or {},
                candidate_id=target_before["candidate_id"],
                origin=target_before["origin"],
                parent=target_before.get("parent"),
            )
            payload = record_candidate_stage(
                lifecycle_path,
                candidate,
                f"drp_{edge.get('stage')}_failed",
                run_id=int(target_run_id),
                status="failed",
                details=detail,
            )
            recorded = payload["events"][-1]

        final_payload = load_lifecycle(lifecycle_path)
        target_after = slot(final_payload, int(target_run_id))
        edge.update({
            "source_candidate_id": source_candidate_id,
            "target_candidate_id": target_after.get("candidate_id"),
            "replaced_candidate_id": replaced_candidate_id,
            "replaced_target_candidate_id": replaced_candidate_id,
            "lifecycle_recorded": True,
            "lifecycle_event_id": recorded.get("event_id"),
            "lifecycle_idempotent_reuse": False,
        })

    return edges


def _record_self_stage_parameter_events(
    lifecycle_path: Optional[Path], stage_events: List[Dict[str, Any]]
) -> None:
    """Update survivor slots in place without manufacturing clone identities."""
    if lifecycle_path is None:
        return
    from candidate_tracking import attach_metadata, load_lifecycle, record_candidate_stage

    path = Path(lifecycle_path)
    if not path.is_file():
        raise RuntimeError(
            f"candidate lifecycle is required for stage parameters but missing: {path}")
    for event in stage_events:
        if event.get("mapping_kind") != "self" or not event.get("trusted"):
            continue
        run_id = int(event["target_run_id"])
        payload = load_lifecycle(path)
        slots = [slot for slot in payload.get("slots", [])
                 if int(slot.get("run_id", -1)) == run_id]
        if len(slots) != 1:
            raise RuntimeError(f"candidate lifecycle has no unique run slot {run_id}")
        slot = slots[0]
        effective = dict(event.get("effective_params") or {})
        candidate = attach_metadata(
            effective,
            candidate_id=slot["candidate_id"],
            origin=slot["origin"],
            parent=slot.get("parent"),
        )
        updated = record_candidate_stage(
            path,
            candidate,
            f"drp_{event.get('stage')}_{event.get('next_stage')}_self",
            run_id=run_id,
            status="trusted",
            details={
                "lifecycle_kind": "stage_parameter_self",
                "stage_parameter_event_id": event.get("event_id"),
                "generated_params": event.get("generated_params"),
                "generated_origin": event.get("generated_origin"),
                "frozen_baseline": bool(event.get("frozen_baseline")),
                "config_sha256": event.get("config_sha256"),
            },
        )
        recorded = updated["events"][-1]
        event["source_candidate_id"] = slot.get("candidate_id")
        event["target_candidate_id"] = slot.get("candidate_id")
        event["candidate_lifecycle_event_id"] = recorded.get("event_id")


def _attach_candidate_edges_to_lineage(
    finalized_events: List[Dict], candidate_edges: List[Dict[str, Any]]
) -> List[Dict]:
    """Embed stable candidate identities in the canonical lineage events."""
    edge_by_id: Dict[str, Dict[str, Any]] = {}
    for edge in candidate_edges:
        event_id = str(edge.get("lineage_event_id") or "").strip()
        if not event_id:
            raise RuntimeError("candidate edge has no lineage_event_id")
        if event_id in edge_by_id:
            raise RuntimeError(f"duplicate candidate edge for lineage event {event_id}")
        edge_by_id[event_id] = edge

    enriched = []
    for raw_event in finalized_events:
        event = dict(raw_event)
        event_id = str(event.get("event_id") or "").strip()
        edge = edge_by_id.pop(event_id, None)
        if edge is None:
            raise RuntimeError(
                f"lineage event {event_id or '<missing>'} has no candidate edge")
        event.update({
            "source_candidate_id": edge.get("source_candidate_id"),
            "target_candidate_id": edge.get("target_candidate_id"),
            "replaced_target_candidate_id": edge.get(
                "replaced_target_candidate_id", edge.get("replaced_candidate_id")),
            "candidate_lifecycle_event_id": edge.get("lifecycle_event_id"),
        })
        enriched.append(event)
    if edge_by_id:
        raise RuntimeError(
            "candidate edges do not correspond to finalized lineage events: "
            f"{sorted(edge_by_id)}")
    return enriched


def _parent_family_from_snapshot(snapshot: Any, stage: str) -> Optional[str]:
    if not isinstance(snapshot, dict):
        return None
    params = snapshot.get("params") or {}
    if stage == "routing":
        from config_recipe import routing_parent_family

        effective_sdc = snapshot.get("effective_sdc") or {}
        sdc_identity = effective_sdc.get(
            "recipe_sha256", effective_sdc.get("sha256"))
        return routing_parent_family(
            params, snapshot.get("routing_context"), sdc_identity)
    if stage != "cts":
        return None
    excluded = set(STAGE_PARAM_NAMES["cts"]) | set(STAGE_PARAM_NAMES["routing"])
    upstream = {
        str(name): float(value)
        for name, value in params.items()
        if name not in excluded and isinstance(value, (int, float))
    }
    if not upstream:
        return None
    payload = json.dumps(upstream, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()[:16]


def _load_stage_provenance(
    path: Path,
    params_path: Path,
    *,
    stage: str,
    iteration: int,
    source_ids: List[int],
    target_ids: List[int],
    stage_events: Optional[List[Dict]] = None,
    lineage_events: Optional[List[Dict]] = None,
    candidate_lifecycle: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Validate the agent sidecar against params, clone slots, and lifecycle."""
    from candidate_tracking import ALLOWED_ORIGINS, load_lifecycle, make_candidate_id

    if stage_events is None:
        stage_events = lineage_events or []

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read stage provenance {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise RuntimeError("stage provenance has an unsupported schema")
    if payload.get("stage") != stage:
        raise RuntimeError(
            f"stage provenance stage {payload.get('stage')!r} != {stage!r}")
    if payload.get("iteration") != iteration:
        raise RuntimeError(
            f"stage provenance iteration {payload.get('iteration')!r} != {iteration}")
    if payload.get("params_file") != Path(params_path).name:
        raise RuntimeError("stage provenance refers to a different params file")
    actual_params_sha = lineage_file_sha256(params_path)
    if payload.get("params_sha256") != actual_params_sha:
        raise RuntimeError("stage provenance params_sha256 mismatch")

    slots = payload.get("slots")
    expected_count = len(target_ids)
    if (not isinstance(slots, list) or payload.get("count") != expected_count
            or len(slots) != expected_count
            or len(source_ids) != expected_count
            or len(stage_events) != expected_count):
        raise RuntimeError(
            "stage provenance count does not match the full run-slot batch")

    lifecycle = None
    lifecycle_slots = {}
    if candidate_lifecycle is not None:
        lifecycle = load_lifecycle(candidate_lifecycle)
        if int(lifecycle.get("iteration", -1)) != int(iteration):
            raise RuntimeError("stage provenance lifecycle iteration mismatch")
        if payload.get("campaign_id") != lifecycle.get("campaign_id"):
            raise RuntimeError("stage provenance lifecycle campaign mismatch")
        lifecycle_slots = {
            int(slot["run_id"]): slot for slot in lifecycle.get("slots", [])
        }

    validated = []
    for index, (raw, source_id, target_id, event) in enumerate(zip(
            slots, source_ids, target_ids, stage_events)):
        if not isinstance(raw, dict) or raw.get("slot_index") != index:
            raise RuntimeError(f"stage provenance slot {index} is not positional")
        origin = raw.get("origin")
        if origin not in ALLOWED_ORIGINS:
            raise RuntimeError(
                f"stage provenance slot {index} has invalid origin {origin!r}")
        if (raw.get("source_run_id") != int(source_id)
                or raw.get("target_run_id") != int(target_id)):
            raise RuntimeError(
                f"stage provenance slot {index} clone endpoints do not match DRP")
        if raw.get("lineage_event_id") != event.get("event_id"):
            raise RuntimeError(
                f"stage provenance slot {index} lineage_event_id mismatch")
        expected_family = _parent_family_from_snapshot(
            event.get("source_config"), stage)
        if not expected_family or raw.get("parent_family") != expected_family:
            raise RuntimeError(
                f"stage provenance slot {index} parent_family mismatch")

        expected_identities = {
            "source_candidate_id": raw.get("source_candidate_id"),
            "target_candidate_id": raw.get("target_candidate_id"),
            "replaced_target_candidate_id": raw.get(
                "replaced_target_candidate_id"),
        }
        if lifecycle is not None:
            try:
                source_slot = lifecycle_slots[int(source_id)]
                target_slot = lifecycle_slots[int(target_id)]
            except KeyError as exc:
                raise RuntimeError(
                    f"stage provenance slot {index} is absent from lifecycle") from exc
            self_conditioned = int(source_id) == int(target_id)
            expected_target_id = (
                source_slot.get("candidate_id") if self_conditioned else
                make_candidate_id(
                    lifecycle["campaign_id"], lifecycle["iteration"],
                    f"drp-edge:{event['event_id']}")
            )
            expected_identities = {
                "source_candidate_id": source_slot.get("candidate_id"),
                "replaced_target_candidate_id": (
                    None if self_conditioned else target_slot.get("candidate_id")),
                "target_candidate_id": expected_target_id,
            }
            for name, expected in expected_identities.items():
                if raw.get(name) != expected:
                    raise RuntimeError(
                        f"stage provenance slot {index} {name} mismatch")

        expected_conditioning = {
            "source_run_id": int(source_id),
            "target_run_id": int(target_id),
            "parent_family": expected_family,
            "lineage_event_id": event.get("event_id"),
            **expected_identities,
        }
        for name, expected in expected_conditioning.items():
            actual_value = raw.get(f"actual_{name}")
            proposal_value = raw.get(f"proposal_conditioned_{name}")
            if actual_value != expected or proposal_value != expected:
                raise RuntimeError(
                    f"stage provenance slot {index} proposal/actual {name} mismatch")
        validated.append(dict(raw))
    return validated


def _mutation_is_expected(stage: str, explicit: Optional[bool]) -> bool:
    """Support an intentional frozen clone separately from a failed mutation."""
    if explicit is not None:
        return bool(explicit)
    raw = os.environ.get("DRP_MUTATION_EXPECTED", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return True


def _safe_config_snapshot(path: Path, hash_cache: Dict) -> Tuple[Optional[Dict], Optional[str]]:
    try:
        return config_snapshot(path, hash_cache), None
    except Exception as exc:
        return None, str(exc)


def _new_lineage_event(iteration: int, stage: str, next_stage: str,
                       source_run_id: Optional[int], target_run_id: int,
                       mutation_expected: bool,
                       source_config: Optional[Dict],
                       source_config_error: Optional[str]) -> Dict:
    source_label = "none" if source_run_id is None else str(source_run_id)
    return {
        "schema_version": 1,
        "event_id": f"iter{iteration}:{stage}:{source_label}->{target_run_id}",
        "iteration": iteration,
        "stage": stage,
        "next_stage": next_stage,
        "source_run_id": source_run_id,
        "target_run_id": target_run_id,
        "source_config": source_config,
        "source_config_error": source_config_error,
        "source_effective_params": ((source_config or {}).get("params") or {}),
        "generated_params": None,
        "generated_origin": None,
        "generated_provenance": None,
        "preserved_params": {},
        "preserved_params_apply": None,
        "generated_param_count_matches": False,
        "target_config": None,
        "target_config_error": None,
        "target_effective_params": {},
        "effective_sdc": None,
        "config_sha256": None,
        "checkpoint": None,
        "checkpoint_copy": None,
        "config_copy": None,
        "params_apply": None,
        "status": {
            "checkpoint_copy": "pending",
            "config_copy": "pending",
            "params_apply": "pending" if mutation_expected else "not_required",
        },
        "mutation_expected": mutation_expected,
        "mutation_applied": False,
        "trusted": False,
        "trust_reasons": ["operations_pending"],
        "created_utc": utc_now(),
        "updated_utc": utc_now(),
    }


def _source_config_errors(snapshot: Optional[Dict]) -> List[str]:
    """Return preflight errors that would make cloned lineage unreproducible."""
    if snapshot is None:
        return ["source config snapshot unavailable"]
    params = snapshot.get("params") or {}
    missing = [name for name in (*CONFIG_PARAM_NAMES, "clk_period")
               if name not in params]
    errors = []
    if missing:
        errors.append("source config missing effective params: " + ",".join(missing))
    effective_sdc = snapshot.get("effective_sdc") or {}
    if (not effective_sdc.get("sha256")
            or effective_sdc.get("clk_period") is None):
        errors.append("source config has no resolvable SDC/clock")
    return errors


def _preflight_clone_batch(
    population_ids: List[int],
    survivor_ids: List[int],
    source_ids: List[int],
    victim_ids: List[int],
    results_base: Path,
    platform: str,
    design: str,
    stage: str,
    config_dir: Path,
    iteration: int,
    next_stage: str,
    mutation_expected: bool,
    hash_cache: Dict,
) -> Tuple[List[Dict], Dict[int, List[str]]]:
    """Validate every clone edge before the first target file is modified."""
    if len(set(population_ids)) != len(population_ids):
        raise RuntimeError("DRP population contains duplicate run ids")
    if len(set(survivor_ids)) != len(survivor_ids):
        raise RuntimeError("DRP selection contains duplicate survivor slots")
    if set(survivor_ids) & set(victim_ids):
        raise RuntimeError("DRP survivor/victim sets overlap")
    if set(survivor_ids) | set(victim_ids) != set(population_ids):
        raise RuntimeError("DRP survivor/victim sets do not conserve the population")
    if len(source_ids) != len(victim_ids):
        raise RuntimeError(
            "DRP clone mapping is not aligned: source/victim lengths differ")
    if len(set(victim_ids)) != len(victim_ids):
        raise RuntimeError("DRP clone mapping contains duplicate victim slots")
    overlap = set(source_ids) & set(victim_ids)
    if overlap:
        raise RuntimeError(
            f"DRP clone mapping would overwrite source slot(s) {sorted(overlap)}")

    source_configs: Dict[int, Tuple[Optional[Dict], Optional[str]]] = {}
    source_checkpoints: Dict[int, Tuple[Optional[Dict], Optional[str]]] = {}
    events = []
    failures: Dict[int, List[str]] = {}

    for source_id, victim_id in zip(source_ids, victim_ids):
        if source_id not in source_configs:
            config_path = config_dir / f"config_{source_id}.mk"
            snapshot, snapshot_error = _safe_config_snapshot(config_path, hash_cache)
            config_errors = ([snapshot_error] if snapshot_error else [])
            config_errors.extend(_source_config_errors(snapshot))
            source_configs[source_id] = (
                snapshot, "; ".join(config_errors) if config_errors else None)

        if source_id not in source_checkpoints:
            checkpoint_path = _checkpoint_path(
                results_base, platform, design, source_id, stage)
            try:
                snapshot = checkpoint_snapshot(checkpoint_path, hash_cache)
                if snapshot["size_bytes"] <= 0:
                    raise ValueError(f"checkpoint is empty: {checkpoint_path}")
                source_checkpoints[source_id] = (snapshot, None)
            except (OSError, ValueError) as exc:
                source_checkpoints[source_id] = (None, str(exc))

        source_snapshot, source_error = source_configs[source_id]
        checkpoint_info, checkpoint_error = source_checkpoints[source_id]
        target_config_path = config_dir / f"config_{victim_id}.mk"
        target_before, target_before_error = _safe_config_snapshot(
            target_config_path, hash_cache)
        event = _new_lineage_event(
            iteration, stage, next_stage, source_id, victim_id,
            mutation_expected, source_snapshot, source_error)
        event["target_config_before_clone"] = target_before
        event["target_config_before_clone_error"] = target_before_error
        event["checkpoint"] = checkpoint_info

        errors = []
        if checkpoint_error:
            errors.append(f"checkpoint: {checkpoint_error}")
        if source_error:
            errors.append(f"source_config: {source_error}")
        if not mutation_expected and stage == "place":
            before_params = (target_before or {}).get("params", {})
            event["preserved_params"] = {
                name: before_params[name]
                for name in STAGE_PARAM_NAMES["routing"] if name in before_params
            }
            missing = [name for name in STAGE_PARAM_NAMES["routing"]
                       if name not in before_params]
            if target_before_error:
                errors.append(f"target_config: {target_before_error}")
            if missing:
                errors.append(
                    "target config missing frozen routing params: " + ",".join(missing))

        event["preflight_errors"] = list(errors)
        events.append(event)
        if errors:
            failures[victim_id] = errors

    if failures:
        # Record that every edge was deliberately left untouched. This distinguishes
        # a safe batch abort from an I/O failure after a target had been installed.
        for event in events:
            errors = event["preflight_errors"]
            checkpoint_error = next(
                (error for error in errors if error.startswith("checkpoint:")), None)
            config_error = next(
                (error for error in errors
                 if error.startswith(("source_config:", "target_config:",
                                      "target config "))), None)
            batch_error = (
                "; ".join(errors) if errors
                else "another clone edge failed batch preflight")
            event["checkpoint_copy"] = {
                "status": "failed" if checkpoint_error else "skipped",
                "error": checkpoint_error or batch_error,
            }
            event["config_copy"] = {
                "status": "failed" if config_error else "skipped",
                "error": config_error or batch_error,
            }
            event["status"].update({
                "checkpoint_copy": (
                    "preflight_failed" if checkpoint_error
                    else "skipped_batch_preflight_failed"),
                "config_copy": (
                    "preflight_failed" if config_error
                    else "skipped_batch_preflight_failed"),
            })
            if mutation_expected:
                event["status"]["params_apply"] = "skipped_batch_preflight_failed"

    return events, failures


def _recondition_frozen_routing_events(
    events: List[Dict], *, objective: str, platform: str, design: str,
    work_dir: Path, drp_config_path: Path, iteration: int,
    agentic_enabled: bool = True,
) -> Dict[str, Any]:
    """Replace stale target routing knobs with proposals for the actual clone parent.

    In ROUTING_FOCUS the post-place clone intentionally leaves CTS unchanged.  The
    target's old routing knobs, however, may have been selected for a different CSV
    parent.  Recondition them after source selection and before config copy so every
    downstream child remains causal relative to the checkpoint it actually inherits.
    """
    if not events:
        return {"enabled": False, "reason": "no_clone_events"}
    try:
        from common import get_design_config, get_param_constraints, load_config
        from routing_focus import deterministic_novelty_for_sources, propose_for_sources
        from search_policy import load_optimization_state, policy_for_context

        config = load_config(drp_config_path)
        policy = policy_for_context(config, objective, platform, design)
        design_config = get_design_config(config, platform, design)
        constraints = get_param_constraints(config, "routing", design_config)
        source_params = []
        for event in events:
            snapshot = event.get("source_config") or {}
            params = dict(snapshot.get("params") or {})
            context = snapshot.get("routing_context")
            if isinstance(context, dict):
                params["_FLOORPLAN_CONTEXT"] = dict(context)
            sdc = snapshot.get("effective_sdc") or {}
            sdc_identity = sdc.get("recipe_sha256", sdc.get("sha256"))
            if sdc_identity:
                params["_SDC_RECIPE_SHA256"] = str(sdc_identity)
            source_params.append(params)
        proposal_seed = "|".join((
            str(os.environ.get("DRP_SEED", "")), str(iteration),
            platform, design, "post-place-recondition"))
        radius = float((policy or {}).get("routing_jitter_fraction", 0.08))
        try:
            from optimize import load_stage_history

            state_path = work_dir / "designs" / platform / design / "optimization_state.json"
            state = load_optimization_state(state_path)
            if (policy is None or not isinstance(state, dict)
                    or state.get("mode") != "ROUTING_FOCUS"):
                raise RuntimeError("routing-focus state or policy unavailable")
            history = load_stage_history(
                work_dir / "backup_dir", platform, design,
                max(0, iteration - 1), "routing")
            proposals, meta = propose_for_sources(
                source_params, history, constraints, state, policy,
                seed=proposal_seed, agentic_enabled=agentic_enabled)
        except Exception as exc:
            proposals, meta = deterministic_novelty_for_sources(
                source_params, constraints, proposal_seed,
                radius_fraction=radius)
            meta["fallback_cause"] = f"conditional_history_or_model_failed:{exc}"
        if len(proposals) != len(events):
            return {"enabled": False, "reason": "proposal_count_mismatch", "meta": meta}
        for event, proposal, mode, family in zip(
                events, proposals, meta.get("modes", []), meta.get("families", [])):
            event["preserved_params"] = dict(proposal)
            event["routing_recondition"] = {
                "status": "ok", "mode": mode, "parent_family": family,
                "params": dict(proposal),
            }
        return {"enabled": True, **meta}
    except Exception as exc:
        print(f"[routing-focus][ERROR] parent reconditioning unavailable ({exc}).",
              file=sys.stderr)
        return {"enabled": False, "reason": f"parent_reconditioning_unavailable:{exc}"}


def run_drp(
    stage: str,
    metrics_file: Path,
    objective: str,
    num_kill: int,
    platform: str,
    design: str,
    work_dir: Path,
    config_dir: Path,
    drp_config_path: Path,
    next_stage: str,
    selection: str = "elitist",
    beta: float = 4.0,
    n_elite: int = 1,
    seed: Optional[int] = None,
    agentic: bool = False,
    predictor: bool = False,
    predictor_config: Optional[Path] = None,
    predictor_checkpoint: Optional[Path] = None,
    baseline_traj: Optional[Path] = None,
    predictor_rank_mode: str = "promising",
    predictor_bootstrap_fallback: bool = False,
    protect_runs: Optional[List[int]] = None,
    protect_abort_on_fail: bool = False,
    mutation_expected: Optional[bool] = None,
    candidate_lifecycle: Optional[Path] = None,
    clean_identity_quota: int = 0,
    llm_enabled: bool = True,
) -> Dict:
    """
    Execute the full DRP pipeline for a stage.

    Args:
        stage: Current stage ('place' or 'cts')
        metrics_file: JSON with run metrics
        objective: 'wl', 'ecp', or 'combo'
        num_kill: Number of runs to kill
        platform, design: Platform and design names
        work_dir: DRP-Agent working directory
        config_dir: Directory with config_i.mk files
        drp_config_path: Path to drp_config.json
        next_stage: Stage whose params to generate ('cts' or 'routing')

    Returns:
        Dict with survivor_ids, source_ids, victim_ids, generated_params
    """
    results_base = work_dir / "results"
    objects_base = work_dir / "objects"
    reports_base = work_dir / "reports"
    logs_base = work_dir / "logs"
    iteration = _lineage_iteration(metrics_file)
    if not llm_enabled and not agentic:
        raise ValueError("No-LLM mode requires the agentic pipeline")
    mutation_expected = _mutation_is_expected(stage, mutation_expected)
    if (isinstance(clean_identity_quota, bool)
            or not isinstance(clean_identity_quota, int)
            or clean_identity_quota < 0):
        raise ValueError("clean_identity_quota must be a non-negative integer")
    lineage_events: List[Dict] = []
    stage_parameter_events: List[Dict] = []
    lineage_hash_cache: Dict = {}
    clean_identity_audit: Dict[str, Any] = {
        "enabled": False,
        "stage": stage,
        "requested_quota": int(clean_identity_quota),
        "effective_quota": 0,
        "protected_run_ids": [],
        "protected_candidate_ids": [],
    }

    # 1. Load metrics. Predictor scores are converted to a lower-is-better key so all
    #    existing selection rules keep one ordering convention.
    metrics = load_metrics(metrics_file)

    source_eligible_ids, source_ineligible = resolve_source_eligibility(
        metrics, objective, results_base, platform, design, stage)
    checkpoint_name = CHECKPOINT_FILES[stage]
    invalid_objective_ids = sorted(
        run_id for run_id, reasons in source_ineligible.items()
        if f"invalid_{objective}" in reasons)
    invalid_checkpoint_ids = sorted(
        run_id for run_id, reasons in source_ineligible.items()
        if f"missing_or_empty_{checkpoint_name}" in reasons)
    print(f"[eligibility] post-{stage}: {len(source_eligible_ids)}/{len(metrics)} "
          f"runs have finite {objective} and a non-empty {checkpoint_name}.")
    if invalid_objective_ids:
        print(f"[eligibility] invalid {objective}: {invalid_objective_ids}")
    if invalid_checkpoint_ids:
        print(f"[eligibility] missing/empty {checkpoint_name}: "
              f"{invalid_checkpoint_ids}")
    population_run_ids = {int(item["run_id"]) for item in metrics}
    if iteration == 1 and 1 in population_run_ids and 1 not in source_eligible_ids:
        raise RuntimeError(
            "iteration-1 default ORFS baseline is not stage-valid; refusing to "
            "replace or mutate baseline run 1")

    # Identity protection (baseline / best-so-far replay) is resolved before ranking:
    # a failed protected run under abort_on_fail must stop the campaign first.
    explicit_protect = resolve_explicit_protection(
        metrics, protect_runs or [], objective, stage, protect_abort_on_fail)
    checkpoint_failed_protect = explicit_protect - source_eligible_ids
    if checkpoint_failed_protect:
        failed = sorted(checkpoint_failed_protect)
        if protect_abort_on_fail:
            print(f"ABORT: baseline run(s) {failed} have a valid {objective} but no "
                  f"non-empty {checkpoint_name}. Refusing to advance or overwrite "
                  f"a baseline without its post-{stage} checkpoint.", file=sys.stderr)
            sys.exit(3)
        print(f"[protect] run(s) {failed} have no non-empty {checkpoint_name}; "
              "identity protection waived (normal failure handling applies).")
        explicit_protect -= checkpoint_failed_protect
    if explicit_protect:
        print(f"[protect] identity-protected run(s) this stage: {sorted(explicit_protect)}")
    if not source_eligible_ids:
        raise RuntimeError(
            f"DRP has no stage-valid source: every run lacks a finite {objective}, "
            f"a non-empty {checkpoint_name}, or both")

    rank_key = objective
    rank_mode = predictor_rank_mode if predictor else None
    model_sha256 = _file_sha256(predictor_checkpoint) if predictor else None
    predictor_config_sha256 = _file_sha256(predictor_config) if predictor else None
    scored_count = 0
    rank_eligible_count = 0
    fallback_reason = None
    predictor_scores: Dict[int, Optional[Dict]] = {}
    predictor, gate_reason = predictor_active(predictor, objective)
    if gate_reason:
        print(f"[predictor] {gate_reason}")
    if predictor:
        if rank_mode not in {"promising", "kill"}:
            raise ValueError(
                f"predictor rank mode must be 'promising' or 'kill' (got {rank_mode!r})")
        from predictor_bridge import predict_run_scores

        run_ids = [m["run_id"] for m in metrics]
        baseline_path = (Path(baseline_traj) if baseline_traj is not None
                         else config_dir / "baseline_trajectory.csv")
        if not baseline_path.exists() and predictor_bootstrap_fallback:
            fallback_reason = "bootstrap_baseline_missing"
            print("[predictor][bootstrap] baseline trajectory is not available yet; "
                  f"using {objective} for this stage only.")
        else:
            if not baseline_path.exists():
                raise RuntimeError(
                    f"predictor baseline is missing after bootstrap: {baseline_path}")
            raw_scores = predict_run_scores(
                run_ids, stage, work_dir / "logs", platform, design,
                baseline_path, predictor_config, predictor_checkpoint, config_dir)
            if raw_scores is None:
                raise RuntimeError(
                    f"predictor returned no batch despite existing baseline {baseline_path}")
            predictor_scores = _validated_predictor_scores(raw_scores, run_ids)
            scored_count = sum(v is not None for v in predictor_scores.values())
            if scored_count == 0:
                raise RuntimeError(
                    f"predictor scored 0/{len(run_ids)} runs at stage {stage}; aborting")

            for m in metrics:
                details = predictor_scores.get(m["run_id"])
                for field in _PREDICTOR_SCORE_FIELDS:
                    m[field] = details.get(field) if details is not None else None
                if details is not None:
                    m["promising_cost"] = 1.0 - details["promising_score"]
                else:
                    m["promising_cost"] = None
            rank_key = "promising_cost" if rank_mode == "promising" else "kill_score"
            print(f"[predictor] QoR-comparator {rank_mode} ranking as DRP key "
                  f"({scored_count}/{len(run_ids)} runs scored; unscored -> worst).")

    rank_eligible_ids = {
        m["run_id"] for m in metrics
        if m["run_id"] in source_eligible_ids and _finite_metric(m.get(rank_key))
    }
    for metric in metrics:
        metric["drp_rank_eligible"] = metric["run_id"] in rank_eligible_ids
    rank_eligible_count = len(rank_eligible_ids)
    print(f"[eligibility] rank-eligible for {rank_key}: "
          f"{rank_eligible_count}/{len(metrics)} runs.")
    if rank_eligible_count == 0:
        raise RuntimeError(
            f"DRP has no run that is both stage-valid and rankable by {rank_key}")

    def result_payload(survivors, sources, victims, generated):
        serialized_scores = {}
        for rid, details in predictor_scores.items():
            if details is None:
                serialized_scores[str(rid)] = None
                continue
            row = dict(details)
            row["rank_cost"] = (
                1.0 - details["promising_score"]
                if rank_mode == "promising" else details["kill_score"])
            serialized_scores[str(rid)] = row
        finalized_events = [evaluate_trust(event) for event in lineage_events]
        candidate_edges = _record_candidate_edges(
            candidate_lifecycle, finalized_events)
        finalized_events = _attach_candidate_edges_to_lineage(
            finalized_events, candidate_edges)
        edge_by_event_id = {
            edge.get("lineage_event_id"): edge for edge in candidate_edges
        }
        for stage_event in stage_parameter_events:
            edge = edge_by_event_id.get(stage_event.get("event_id"))
            if edge is not None:
                stage_event.update({
                    "source_candidate_id": edge.get("source_candidate_id"),
                    "target_candidate_id": edge.get("target_candidate_id"),
                    "replaced_target_candidate_id": edge.get(
                        "replaced_target_candidate_id"),
                    "candidate_lifecycle_event_id": edge.get(
                        "lifecycle_event_id"),
                })
        _record_self_stage_parameter_events(
            candidate_lifecycle, stage_parameter_events)
        lineage_path = write_stage_summary(
            work_dir, platform, design, iteration, stage, finalized_events)
        return {
            "survivor_ids": survivors,
            "source_ids": sources,
            "victim_ids": victims,
            "generated_params": generated,
            "generated_provenance": [
                event.get("generated_provenance") for event in finalized_events
            ],
            "stage_generated_params": [
                event.get("generated_params") for event in stage_parameter_events
            ],
            "stage_generated_provenance": [
                event.get("generated_provenance") for event in stage_parameter_events
            ],
            "stage_parameter_count": len(stage_parameter_events),
            "stage_parameter_events": stage_parameter_events,
            "effective_rank_key": rank_key,
            "rank_mode": rank_mode,
            "model_sha256": model_sha256,
            "predictor_config_sha256": predictor_config_sha256,
            "scored_count": scored_count,
            "stage_valid_count": len(source_eligible_ids),
            "rank_eligible_count": rank_eligible_count,
            "rank_eligible_ids": sorted(rank_eligible_ids),
            "source_eligible_ids": sorted(source_eligible_ids),
            "source_ineligible": {
                str(run_id): reasons
                for run_id, reasons in sorted(source_ineligible.items())
            },
            "fallback_reason": fallback_reason,
            "predictor_scores": serialized_scores,
            "mutation_expected": mutation_expected,
            "llm_enabled": bool(llm_enabled),
            "clean_identity_protection": clean_identity_audit,
            "lineage_events": finalized_events,
            "candidate_edges": candidate_edges,
            "lineage_summary": str(lineage_path),
            "lineage_trusted_count": sum(
                1 for event in finalized_events if event.get("trusted")),
        }

    sorted_metrics = sort_runs(metrics, rank_key)

    # Dual elitism: when ranking on a LEARNED key that can disagree with
    # the true objective, unconditionally protect the top-K runs BY THE OBJECTIVE.
    # (Observed failure: the known-best replay ranked 48/50 by kill_score and survived
    # only by resampling luck, while the objective-worst run got elite protection.)
    # Identity-protected runs (baseline / best replay) are merged in unconditionally.
    protected_ids: set = set(explicit_protect)
    if iteration == 1 and any(int(m["run_id"]) == 1 for m in sorted_metrics):
        protected_ids.add(1)
        print("[protect] iteration-1 default ORFS baseline run 1 is immutable")
    if rank_key != objective:
        by_obj = sorted((m for m in sorted_metrics
                         if m["run_id"] in source_eligible_ids),
                        key=lambda m: m[objective])
        obj_elite = {m["run_id"] for m in by_obj[:max(1, n_elite)]}
        if obj_elite:
            print(f"[protect] true-{objective} elite guaranteed survival "
                  f"(rank key is {rank_key}): {sorted(obj_elite)}")
        protected_ids.update(obj_elite)

    # A GWTW copy changes the identity that owns a final QoR observation. Reserve a
    # minimum number of original input identities before the post-place draw, then
    # carry those exact identities through the post-CTS draw.  This turns the
    # clean-history coverage requirement into an executable selection invariant,
    # rather than hoping resampling happens to preserve enough candidates.
    if selection == "gwtw" and clean_identity_quota:
        clean_ids, clean_identity_audit = resolve_clean_identity_protection(
            stage,
            sorted_metrics,
            source_eligible_ids,
            clean_identity_quota,
            candidate_lifecycle,
            iteration,
            explicit_protected_ids=protected_ids,
        )
        protected_ids.update(clean_ids)
        print("[protect] clean candidate identities guaranteed through "
              f"post-{stage}: {sorted(clean_ids)}")

    print(f"\n{'='*60}")
    print(f"DRP Stage: post-{stage} | Objective: {objective} | Key: {rank_key} | Selection: {selection}")
    print(f"{'='*60}")

    # 2. Select survivors and victims
    if selection == "gwtw":
        (survivor_ids, source_ids, victim_ids,
         weights, counts) = gwtw_select(sorted_metrics, rank_key,
                                        beta=beta, n_elite=n_elite, seed=seed,
                                        protected_ids=protected_ids,
                                        eligible_ids=source_eligible_ids)
        if survivor_ids is None:
            print("\n[GWTW] No eligible run has a finite ranking value; skipping DRP "
                  "(all runs left untouched).")
            return result_payload(
                [m["run_id"] for m in sorted_metrics], [], [], [])
        print(f"\n[GWTW] beta={beta}, n_elite={n_elite}, seed={seed}")
        print(f"\nRun ranking (sorted by {rank_key}, ascending=better):")
        for i, m in enumerate(sorted_metrics):
            obj_val = m.get(rank_key, "N/A")
            if isinstance(obj_val, float):
                obj_val = f"{obj_val:.4f}"
            marker = " [KILL]" if counts[i] == 0 else (
                f" [x{counts[i]}]" if counts[i] > 1 else "")
            if m["run_id"] not in source_eligible_ids:
                marker += " [HARD-INVALID]"
            print(f"  #{i+1} Run {m['run_id']}: {rank_key}={obj_val} "
                  f"w={weights[i]:.3f} n={counts[i]}{marker}")
    else:
        # Select FIRST so the [KILL] markers reflect the actual victims (protection /
        # failure handling can diverge from plain tail-of-ranking truncation — e.g. a
        # protected worst-ranked run_1 must not be shown as [KILL]).
        survivor_ids, source_ids, victim_ids = select_survivors_and_victims(
            sorted_metrics, num_kill, rank_key, protected_ids=protected_ids,
            eligible_ids=source_eligible_ids,
        )
        victim_set = set(victim_ids)
        print(f"\nRun ranking (sorted by {rank_key}, ascending=better):")
        for i, m in enumerate(sorted_metrics):
            marker = " [KILL]" if m["run_id"] in victim_set else (
                " [PROTECT]" if m["run_id"] in protected_ids else "")
            if m["run_id"] not in source_eligible_ids:
                marker += " [HARD-INVALID]"
            obj_val = m.get(rank_key, "N/A")
            if isinstance(obj_val, float):
                obj_val = f"{obj_val:.4f}"
            print(f"  #{i+1} Run {m['run_id']}: {rank_key}={obj_val}{marker}")

    print(f"\nSurvivors: {survivor_ids}")
    print(f"Source runs (to copy): {source_ids}")
    print(f"Victim runs (to replace): {victim_ids}")
    print(f"Runs replaced this stage: {len(victim_ids)}")

    # 3. Validate the complete clone mapping before touching the first victim. The
    # selection hard mask should make checkpoint failures impossible here, but the
    # preflight also closes TOCTOU and missing/malformed source-config failures.
    if victim_ids and not source_ids:
        for victim_id in victim_ids:
            event = _new_lineage_event(
                iteration, stage, next_stage, None, victim_id,
                mutation_expected, None, "selection produced no clone source")
            event["status"].update({
                "checkpoint_copy": "skipped_no_source",
                "config_copy": "skipped_no_source",
                "params_apply": "skipped_no_source",
            })
            lineage_events.append(event)
        print("[DRP][ERROR] victims were selected without a valid clone source; "
              "leaving their slots untouched.", file=sys.stderr)
        result_payload(survivor_ids, source_ids, victim_ids, [])
        raise RuntimeError("DRP selected victims without a valid clone source")

    invalid_selected_sources = sorted(set(source_ids) - source_eligible_ids)
    if invalid_selected_sources:
        raise RuntimeError(
            "DRP selection invariant violated: hard-ineligible clone source(s) "
            f"{invalid_selected_sources}")

    lineage_events, preflight_failures = _preflight_clone_batch(
        [m["run_id"] for m in sorted_metrics], survivor_ids,
        source_ids, victim_ids, results_base, platform, design, stage,
        config_dir, iteration, next_stage, mutation_expected,
        lineage_hash_cache)
    if preflight_failures:
        result_payload(survivor_ids, source_ids, victim_ids, [])
        failed_targets = sorted(preflight_failures)
        details = "; ".join(
            f"run_{target}: {', '.join(preflight_failures[target])}"
            for target in failed_targets)
        raise RuntimeError(
            "DRP clone transaction failed batch preflight for target runs "
            f"{failed_targets}; no target files were modified ({details})")

    routing_recondition = {"enabled": False, "reason": "not_requested"}
    if not mutation_expected and stage == "place":
        routing_recondition = _recondition_frozen_routing_events(
            lineage_events, objective=objective, platform=platform, design=design,
            work_dir=work_dir, drp_config_path=drp_config_path, iteration=iteration,
            agentic_enabled=agentic)
        if routing_recondition.get("enabled"):
            print("[routing-focus] post-place routing params reconditioned against "
                  f"the actual clone parents: {routing_recondition.get('counts', {})}")
        elif os.environ.get("DRP_SEARCH_MODE", "").strip().upper() == "ROUTING_FOCUS":
            result_payload(survivor_ids, source_ids, victim_ids, [])
            raise RuntimeError(
                "ROUTING_FOCUS could not pair routing parameters with the selected "
                "post-place clone parents; no target files were modified "
                f"({routing_recondition.get('reason', 'unknown error')})")

    print(f"\nCopying checkpoints...")
    for src_id, victim_id, event in zip(source_ids, victim_ids, lineage_events):

        checkpoint_copy = copy_checkpoint(
            src_id, victim_id,
            results_base, objects_base, reports_base, logs_base,
            platform, design, stage, hash_cache=lineage_hash_cache,
        )
        event["checkpoint_copy"] = checkpoint_copy
        event["checkpoint"] = checkpoint_copy.get("checkpoint")
        event["status"]["checkpoint_copy"] = checkpoint_copy.get("status", "failed")
        if checkpoint_copy.get("status") != "ok":
            event["config_copy"] = {
                "status": "skipped", "error": "checkpoint copy failed"}
            event["status"]["config_copy"] = "skipped_checkpoint_copy_failed"
            continue

        config_copy = copy_source_config(src_id, victim_id, config_dir)
        event["config_copy"] = config_copy
        event["status"]["config_copy"] = config_copy.get("status", "failed")
        if config_copy.get("status") == "ok":
            target_path = config_dir / f"config_{victim_id}.mk"
            if event.get("preserved_params"):
                preserved_apply = update_config_params(
                    target_path, event["preserved_params"])
                event["preserved_params_apply"] = preserved_apply
                event["status"]["preserved_params_apply"] = preserved_apply.get(
                    "status", "failed")
            target_snapshot, target_error = _safe_config_snapshot(
                target_path, lineage_hash_cache)
            event["target_config"] = target_snapshot
            event["target_config_error"] = target_error

    clone_failures = [
        event for event in lineage_events
        if (event["status"].get("checkpoint_copy") != "ok"
            or event["status"].get("config_copy") != "ok"
            or (not mutation_expected and stage == "place"
                and (event["status"].get("preserved_params_apply") != "ok"
                     or not all(name in event.get("preserved_params", {})
                                for name in STAGE_PARAM_NAMES["routing"]))))
    ]
    if clone_failures:
        result_payload(survivor_ids, source_ids, victim_ids, [])
        failed_targets = [event["target_run_id"] for event in clone_failures]
        raise RuntimeError(
            f"DRP clone transaction failed for target runs {failed_targets}; "
            "campaign aborted before downstream stages")

    # An explicit frozen-stage clone is a valid intervention with no parameter
    # mutation. It must not be conflated with an agent failure or missing output.
    if not mutation_expected:
        for event in lineage_events:
            event["generated_params"] = {}
            event["generated_param_count_matches"] = True
            event["mutation_applied"] = False
            event["params_apply"] = {"status": "not_required", "error": None}
            event["status"]["params_apply"] = "not_required"
        print(f"[lineage] post-{stage} configured as a frozen clone; "
              f"{next_stage} mutation intentionally skipped.")
        payload = result_payload(survivor_ids, source_ids, victim_ids, [])
        payload["routing_recondition"] = routing_recondition
        if payload["lineage_trusted_count"] != len(victim_ids):
            raise RuntimeError(
                "frozen DRP clone completed but lineage verification failed; "
                "campaign aborted")
        return payload

    # 4. Build the post-clone execution map. Survivors condition on themselves;
    # victims condition on the survivor checkpoint/config copied into their slot.
    population_ids = sorted(int(m["run_id"]) for m in sorted_metrics)
    clone_sources = {
        int(target): int(source)
        for source, target in zip(source_ids, victim_ids)
    }
    execution_source_ids = [
        clone_sources.get(target_id, target_id) for target_id in population_ids
    ]
    clone_events_by_target = {
        int(event["target_run_id"]): event for event in lineage_events
    }
    for source_id, target_id in zip(execution_source_ids, population_ids):
        clone_event = clone_events_by_target.get(target_id)
        if clone_event is not None:
            source_snapshot = clone_event.get("source_config")
            source_error = clone_event.get("source_config_error")
        else:
            source_snapshot, source_error = _safe_config_snapshot(
                config_dir / f"config_{source_id}.mk", lineage_hash_cache)
        event = _new_lineage_event(
            iteration, stage, next_stage, source_id, target_id,
            True, source_snapshot, source_error)
        event["mapping_kind"] = (
            "self" if source_id == target_id else "clone")
        event["frozen_baseline"] = bool(iteration == 1 and target_id == 1)
        event["clone_lineage_event_id"] = (
            clone_event.get("event_id") if clone_event is not None else None)
        stage_parameter_events.append(event)

    print(f"\nGenerating {next_stage} parameters for all "
          f"{len(population_ids)} run slots...")
    params_output = work_dir / "tmp" / f"{next_stage}_params.json"
    provenance_output = params_output.with_name(
        f"{params_output.stem}_provenance.json")
    params_output.parent.mkdir(parents=True, exist_ok=True)
    # Never accept a previous iteration's params when this agent invocation fails to
    # create its own output.
    for stale_output in (params_output, provenance_output):
        try:
            stale_output.unlink()
        except FileNotFoundError:
            pass

    # Save sorted metrics for agent.py
    sorted_metrics_file = work_dir / "tmp" / f"sorted_metrics_{stage}.json"
    with open(sorted_metrics_file, "w") as f:
        json.dump(sorted_metrics, f, indent=2)

    cmd = [
        sys.executable, str(work_dir / "agent.py"),
        "--stage", next_stage,
        "--platform", platform,
        "--design", design,
        "--objective", objective,
        "--num-runs", str(len(population_ids)),
        "--metrics-file", str(sorted_metrics_file),
        "--source-runs", ",".join(str(s) for s in execution_source_ids),
        "--target-runs", ",".join(str(v) for v in population_ids),
        "--config-dir", str(config_dir),
        "--drp-config", str(drp_config_path),
        "--work-dir", str(work_dir),
        "--output", str(params_output),
    ]
    if iteration == 1 and 1 in population_ids:
        cmd.extend(["--frozen-runs", "1"])
    if agentic:
        cmd.append("--agentic")  # intra-iteration Agent1+Agent2 stage-param generation
    if not llm_enabled:
        cmd.append("--no-llm")

    # Agent provenance is keyed by the same iteration that names the clone events.
    # maindriver exports DRP_ITER, but direct drp.py invocations must be just as
    # reproducible instead of emitting a sidecar with iteration=None.
    agent_env = dict(os.environ)
    agent_env["DRP_ITER"] = str(iteration)
    if not llm_enabled:
        agent_env["DRP_NO_LLM"] = "1"
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=agent_env)
    except Exception as exc:
        result = subprocess.CompletedProcess(cmd, 1, "", str(exc))
    if result.returncode != 0:
        print(f"[WARN] agent.py failed: {result.stderr}", file=sys.stderr)
        for event in stage_parameter_events:
            event["generated_params"] = None
            event["generated_param_count_matches"] = False
            event["params_apply"] = {
                "status": "skipped_agent_failed", "error": result.stderr.strip()}
            event["status"]["params_apply"] = "skipped_agent_failed"
        for event in lineage_events:
            event["generated_params"] = None
            event["generated_param_count_matches"] = False
            event["mutation_applied"] = False
            event["params_apply"] = {
                "status": "skipped_agent_failed", "error": result.stderr.strip()}
            event["status"]["params_apply"] = "skipped_agent_failed"
        result_payload(survivor_ids, source_ids, victim_ids, [])
        raise RuntimeError(
            f"{next_stage} parameter generator failed; campaign aborted")

    print(result.stdout)
    if result.stderr:  # surface [agent]/[intra] diagnostics (obs count, warnings)
        print(result.stderr, file=sys.stderr)

    # 5. Apply one positionally aligned stage row to every run config.
    generated_params = []
    params_error = None
    if params_output.exists():
        try:
            with open(params_output) as f:
                loaded_params = json.load(f)
            if isinstance(loaded_params, list):
                generated_params = loaded_params
            else:
                params_error = ("agent output must be a JSON list, got "
                                f"{type(loaded_params).__name__}")
        except (OSError, json.JSONDecodeError) as exc:
            params_error = f"cannot read agent output: {exc}"
    else:
        params_error = f"agent produced no output file: {params_output}"

    expected_stage_keys = set(STAGE_PARAM_NAMES[next_stage])
    entries_are_exact = all(
        isinstance(item, dict) and set(item) == expected_stage_keys
        for item in generated_params
    )
    count_matches = (
        len(generated_params) == len(population_ids)
        and entries_are_exact and params_error is None
    )
    if not count_matches:
        detail = params_error or (
            f"expected {len(population_ids)} rows with exact keys "
            f"{sorted(expected_stage_keys)}, got {len(generated_params)} rows")
        print(f"[DRP][ERROR] {next_stage} parameter output mismatch: {detail}; "
              "affected lineage events will remain untrusted.", file=sys.stderr)
        for event in stage_parameter_events:
            event["generated_params"] = None
            event["generated_param_count_matches"] = False
            event["mutation_applied"] = False
            event["params_apply"] = {
                "status": "skipped_output_mismatch", "error": detail}
            event["status"]["params_apply"] = "skipped_output_mismatch"
        result_payload(survivor_ids, source_ids, victim_ids, [])
        raise RuntimeError(
            f"{next_stage} parameter output mismatch; campaign aborted")

    try:
        generated_provenance = _load_stage_provenance(
            provenance_output,
            params_output,
            stage=next_stage,
            iteration=iteration,
            source_ids=execution_source_ids,
            target_ids=population_ids,
            stage_events=stage_parameter_events,
            candidate_lifecycle=candidate_lifecycle,
        )
    except Exception as exc:
        detail = str(exc)
        print(f"[DRP][ERROR] {next_stage} provenance mismatch: {detail}; "
              "no generated parameters will be applied.", file=sys.stderr)
        for index, event in enumerate(stage_parameter_events):
            event["generated_params"] = generated_params[index]
            event["generated_param_count_matches"] = True
            event["mutation_applied"] = False
            event["params_apply"] = {
                "status": "skipped_provenance_mismatch", "error": detail}
            event["status"]["params_apply"] = "skipped_provenance_mismatch"
        result_payload(survivor_ids, source_ids, victim_ids, [])
        raise RuntimeError(
            f"{next_stage} parameter provenance mismatch; campaign aborted") from exc

    for i, event in enumerate(stage_parameter_events):
        target_id = event["target_run_id"]
        params = generated_params[i] if i < len(generated_params) else None
        event["generated_params"] = params if isinstance(params, dict) else None
        event["generated_origin"] = generated_provenance[i]["origin"]
        event["generated_provenance"] = generated_provenance[i]
        event["generated_param_count_matches"] = count_matches
        if not isinstance(params, dict):
            event["params_apply"] = {
                "status": "missing_or_invalid_generated_params",
                "error": params_error or "missing/non-dict positional parameter entry",
            }
            event["status"]["params_apply"] = "missing_or_invalid_generated_params"
            continue
        tgt_config = config_dir / f"config_{target_id}.mk"
        if event.get("frozen_baseline"):
            apply_outcome = {"status": "frozen_baseline", "error": None}
        else:
            apply_outcome = update_config_params(tgt_config, params)
        event["params_apply"] = apply_outcome
        event["status"]["params_apply"] = apply_outcome.get("status", "failed")
        event["mutation_applied"] = apply_outcome.get("status") == "ok"
        event["generated_param_count_matches"] = count_matches
        target_snapshot, target_error = _safe_config_snapshot(
            tgt_config, lineage_hash_cache)
        event["target_config"] = target_snapshot
        event["target_config_error"] = target_error
        event["source_effective_params"] = (
            (event.get("source_config") or {}).get("params") or {})
        event["target_effective_params"] = (
            (target_snapshot or {}).get("params") or {})
        event["effective_params"] = event["target_effective_params"]
        event["effective_sdc"] = (
            (target_snapshot or {}).get("effective_sdc") or {})
        event["source_routing_context"] = (
            (event.get("source_config") or {}).get("routing_context") or {})
        event["effective_routing_context"] = (
            (target_snapshot or {}).get("routing_context") or {})
        event["config_sha256"] = (
            (target_snapshot or {}).get("config_sha256"))
        event["trusted"] = (
            apply_outcome.get("status") in {"ok", "frozen_baseline"}
            and target_snapshot is not None)
        event["trust_reasons"] = ([] if event["trusted"] else [
            "stage_parameter_apply_or_snapshot_failed"])
        if event["mutation_applied"]:
            print(f"  Updated config_{target_id}.mk with {next_stage} params: {params}")
        elif event.get("frozen_baseline"):
            print(f"  Preserved config_{target_id}.mk as the iteration-1 baseline")

        clone_event = clone_events_by_target.get(target_id)
        if clone_event is not None:
            clone_event["generated_params"] = params
            clone_event["generated_origin"] = generated_provenance[i]["origin"]
            clone_event["generated_provenance"] = generated_provenance[i]
            clone_event["generated_param_count_matches"] = count_matches
            clone_event["params_apply"] = apply_outcome
            clone_event["status"]["params_apply"] = apply_outcome.get(
                "status", "failed")
            clone_event["mutation_applied"] = event["mutation_applied"]
            clone_event["target_config"] = target_snapshot
            clone_event["target_config_error"] = target_error

    apply_failures = [
        event for event in stage_parameter_events
        if event["status"].get("params_apply") not in {"ok", "frozen_baseline"}
    ]
    if apply_failures:
        result_payload(survivor_ids, source_ids, victim_ids, generated_params)
        failed_targets = [event["target_run_id"] for event in apply_failures]
        raise RuntimeError(
            f"DRP {next_stage} mutation failed for target runs {failed_targets}; "
            "campaign aborted before downstream stages")

    print(f"\nDRP complete. {len(victim_ids)} runs replaced.")
    victim_generated_params = [
        event.get("generated_params") for event in lineage_events
    ]
    payload = result_payload(
        survivor_ids, source_ids, victim_ids, victim_generated_params)
    if payload["lineage_trusted_count"] != len(victim_ids):
        raise RuntimeError(
            "DRP clone/mutation completed but lineage verification failed; "
            "campaign aborted")
    return payload


def main():
    parser = argparse.ArgumentParser(description="Doomed Run Prediction")
    parser.add_argument("--stage", choices=["place", "cts"], required=True,
                        help="Current completed stage")
    parser.add_argument("--next-stage", choices=["cts", "routing"], required=True,
                        help="Next stage whose params to generate")
    parser.add_argument("--metrics-file", type=Path, required=True,
                        help="JSON file with run metrics")
    parser.add_argument("--objective", choices=["wl", "ecp", "combo", "TNS_EVAL"], required=True)
    parser.add_argument("--num-kill", type=int, required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--design", required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--drp-config", type=Path,
                        default=Path(__file__).parent / "drp_config.json")
    parser.add_argument("--selection", choices=["elitist", "gwtw"],
                        default="elitist",
                        help="Selection rule: deterministic elitist truncation "
                             "(default) or GWTW Boltzmann resampling")
    parser.add_argument("--beta", type=float, default=None,
                        help="GWTW Boltzmann temperature (overrides drp_config)")
    parser.add_argument("--n-elite", type=int, default=None,
                        help="GWTW elites guaranteed to survive (overrides drp_config)")
    parser.add_argument("--seed", type=int, default=None,
                        help="GWTW resampling RNG seed (overrides drp_config)")
    parser.add_argument("--agentic", action="store_true",
                        help="Use Agent1+Agent2 framework for stage-param generation "
                             "(forwarded to agent.py --agentic).")
    parser.add_argument("--no-llm", action="store_true",
                        help="Keep Agentic/GPR stage generation but disable every "
                             "external LLM request (requires --agentic)")
    parser.add_argument("--predictor", action="store_true",
                        help="Rank runs by trained QoR-comparator scores instead of "
                             "the raw stage metric.")
    parser.add_argument("--predictor-config", type=Path,
                        default=Path(__file__).parent / "predict_model" / "example_config.json")
    parser.add_argument("--predictor-checkpoint", type=Path,
                        default=Path(__file__).parent / "predict_model" / "best_model.pt")
    parser.add_argument("--predictor-rank-mode", choices=["promising", "kill"],
                        default=None,
                        help="Predictor ranking policy; default comes from drp_config "
                             "and falls back to promising.")
    parser.add_argument("--predictor-bootstrap-fallback", action="store_true",
                        help="Allow raw objective ranking only while the iteration-1 "
                             "predictor baseline has not been created yet.")
    parser.add_argument("--baseline-traj", type=Path, default=None,
                        help="Baseline full-trajectory CSV (default: "
                             "designs/<p>/<d>/baseline_trajectory.csv).")
    parser.add_argument("--protect-runs", type=str, default="",
                        help="Comma-separated run ids that DRP must never kill "
                             "(iter1: the default-baseline run_1; iter2+: the "
                             "elitism-carried best replay).")
    parser.add_argument("--protect-abort-on-fail", action="store_true",
                        help="If a protected run lacks a valid objective/checkpoint, "
                             "abort (exit 3) "
                             "instead of letting it be overwritten -> pseudo-baseline. "
                             "Use at iteration 1 for the default config.")
    parser.add_argument("--candidate-lifecycle", type=Path, default=None,
                        help="Per-iteration candidate lifecycle sidecar. When set, "
                            "every DRP source-to-target edge is recorded atomically.")
    parser.add_argument("--clean-identity-quota", type=int, default=None,
                        help="For GWTW, preserve this many original candidate "
                             "identities through both post-place and post-CTS "
                             "selections (default: gwtw.clean_identity_quota).")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output JSON with DRP results")

    args = parser.parse_args()
    if args.no_llm and not args.agentic:
        parser.error("--no-llm requires --agentic")
    if args.no_llm:
        os.environ["DRP_NO_LLM"] = "1"

    # Reproducible RNG derived from the campaign base seed + (iteration, design, stage).
    from modelfuncs import seed_everything
    derived = seed_everything(os.environ.get("DRP_SEED"), os.environ.get("DRP_ITER", ""),
                              args.platform, args.design, "drp", args.stage)

    # GWTW hyperparameters: CLI overrides drp_config.json "gwtw" section.
    drp_cfg = {}
    if args.drp_config.exists():
        with open(args.drp_config) as f:
            drp_cfg = json.load(f)
    gwtw_cfg = drp_cfg.get("gwtw", {})
    beta = args.beta if args.beta is not None else gwtw_cfg.get("beta", 2.0)
    n_elite = args.n_elite if args.n_elite is not None else gwtw_cfg.get("n_elite", 1)
    # GWTW seed precedence: explicit --seed > config gwtw.seed > campaign-derived seed.
    seed = args.seed if args.seed is not None else gwtw_cfg.get("seed", None)
    if seed is None:
        seed = derived
    predictor_cfg = drp_cfg.get("predictor", {})
    configured_rank_mode = drp_cfg.get(
        "predictor_rank_mode", predictor_cfg.get("rank_mode", "promising"))
    predictor_rank_mode = args.predictor_rank_mode or configured_rank_mode
    if args.predictor and predictor_rank_mode not in {"promising", "kill"}:
        parser.error("predictor rank mode in drp_config must be 'promising' or 'kill'")
    clean_identity_quota = (
        args.clean_identity_quota if args.clean_identity_quota is not None
        else gwtw_cfg.get("clean_identity_quota", 0)
    )
    if (isinstance(clean_identity_quota, bool)
            or not isinstance(clean_identity_quota, int)
            or clean_identity_quota < 0):
        parser.error("gwtw.clean_identity_quota must be a non-negative integer")

    result = run_drp(
        stage=args.stage,
        metrics_file=args.metrics_file,
        objective=args.objective,
        num_kill=args.num_kill,
        platform=args.platform,
        design=args.design,
        work_dir=args.work_dir,
        config_dir=args.config_dir,
        drp_config_path=args.drp_config,
        next_stage=args.next_stage,
        selection=args.selection,
        beta=beta,
        n_elite=n_elite,
        seed=seed,
        agentic=args.agentic,
        predictor=args.predictor,
        predictor_config=args.predictor_config,
        predictor_checkpoint=args.predictor_checkpoint,
        baseline_traj=(args.baseline_traj if args.baseline_traj is not None
                       else args.config_dir / "baseline_trajectory.csv"),
        predictor_rank_mode=predictor_rank_mode,
        predictor_bootstrap_fallback=args.predictor_bootstrap_fallback,
        protect_runs=[int(x) for x in args.protect_runs.split(",") if x.strip()],
        protect_abort_on_fail=args.protect_abort_on_fail,
        candidate_lifecycle=args.candidate_lifecycle,
        clean_identity_quota=clean_identity_quota,
        llm_enabled=not args.no_llm,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"DRP results written to {args.output}")


if __name__ == "__main__":
    main()
