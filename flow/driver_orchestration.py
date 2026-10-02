#!/usr/bin/env python3
"""Driver-side contracts and reporting for the staged DRP campaign.

The shell driver owns process sequencing.  This module owns structured data:
configuration lookup, campaign manifests, iteration contracts, candidate/CSV
binding, artifact validation, predictor baseline maintenance, and final reports.
Imports that require the predictor runtime are intentionally lazy so non-predictor
commands remain usable in a minimal flow environment.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from search_policy_persistence import STATE_VERSION as OPTIMIZATION_STATE_VERSION


FLOW_PARAM_NAMES: Tuple[str, ...] = (
    "SYNTH_FLATTEN",
    "CORE_UTILIZATION",
    "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT",
    "CELL_PAD_IN_SITES_DETAIL_PLACEMENT",
    "ENABLE_DPO",
    "PLACE_DENSITY_LB_ADDON",
    "TNS_END_PERCENT",
    "FLOORPLAN_PIN_LAYER_ADJUST",
    "FLOORPLAN_ABOVE_LAYER_ADJUST",
    "clk_period",
)
CANONICAL_ARTIFACT_PREFIXES: Tuple[str, ...] = (
    "metrics_place",
    "metrics_cts",
    "metrics_final",
    "drp_place",
    "drp_cts",
    "lineage",
    "config_replay",
    "candidate_lifecycle",
)
PROTECTED_SLOT_FIELDS: Tuple[str, ...] = (
    "protected_replay_slots",
    "protected_config_replay_slots",
    "protected_probe_slots",
    "protected_focus_control_slots",
    "protected_candidate_slots",
)
VALID_OBJECTIVES = frozenset(("wl", "ecp", "combo", "TNS_EVAL"))
LLM_USAGE_LEDGER_NAME = "llm_usage_events.jsonl"
LLM_USAGE_SUMMARY_NAME = "llm_usage_summary.json"


class DriverContractError(RuntimeError):
    """A persisted driver artifact violates the campaign contract."""


def _is_finite_number(value: Any) -> bool:
    # Driver artifacts are JSON, so valid numeric values deserialize as int/float.
    # Do not silently coerce strings such as "12.3" into an accepted metric.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _read_json(path: Path, *, description: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DriverContractError(
            f"ERROR: cannot read {description} {path}: {exc}") from exc


def _read_json_object(path: Path, *, description: str) -> Dict[str, Any]:
    payload = _read_json(path, description=description)
    if not isinstance(payload, dict):
        raise DriverContractError(
            f"ERROR: {description} must be a JSON object: {path}")
    return payload


def _validate_optimization_state(payload: Mapping[str, Any], path: Path) -> None:
    if payload.get("state_version") != OPTIMIZATION_STATE_VERSION:
        raise DriverContractError(
            f"ERROR: unsupported optimization state version in {path}")
    for field in ("enabled", "stop_requested"):
        if field in payload and not isinstance(payload[field], bool):
            raise DriverContractError(
                f"ERROR: optimization state {field} must be boolean in {path}")


def _pipe_safe(value: Any) -> str:
    return str(value).replace("|", "/").replace("\n", " ").replace("\r", " ")


def _optional_power_budget(value: Any) -> Optional[float]:
    """Parse an optional campaign power budget without string-truthiness traps."""
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in {"", "none", "null"}:
        return None
    try:
        budget = float(text)
    except (TypeError, ValueError) as exc:
        raise DriverContractError(
            f"ERROR: invalid power budget {value!r}") from exc
    if not math.isfinite(budget):
        raise DriverContractError(f"ERROR: invalid power budget {value!r}")
    return budget


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_combo_weights(weight_wl: str, weight_ecp: str) -> None:
    try:
        first, second = float(weight_wl), float(weight_ecp)
    except (TypeError, ValueError) as exc:
        raise DriverContractError(
            f"ERROR: invalid combo weights wl={weight_wl} ecp={weight_ecp}") from exc
    if (not math.isfinite(first) or not math.isfinite(second)
            or first < 0 or second < 0 or first + second <= 0):
        raise DriverContractError(
            f"ERROR: invalid combo weights wl={weight_wl} ecp={weight_ecp}")


def load_driver_config(config_path: Path) -> Dict[str, Any]:
    return _read_json_object(config_path, description="driver config")


def predictor_rank_mode(config_path: Path) -> str:
    config = load_driver_config(config_path)
    nested = config.get("predictor")
    nested_mode = nested.get("rank_mode") if isinstance(nested, Mapping) else None
    return str(config.get("predictor_rank_mode", nested_mode or "promising"))


def predictor_baseline_mode(config_path: Path) -> str:
    return str(load_driver_config(config_path).get("predictor_baseline_mode", "best"))


def predictor_metadata(config_path: Path, checkpoint_path: Path) -> Tuple[str, str, str, str]:
    config = _read_json_object(config_path, description="predictor config")
    data = config.get("data")
    if not isinstance(data, Mapping) or "target_metrics" not in data:
        raise DriverContractError(
            f"ERROR: predictor config has no data.target_metrics: {config_path}")
    config_sha = _sha256(config_path)
    checkpoint_sha = _sha256(checkpoint_path) if checkpoint_path.is_file() else ""
    objective = str(config.get("training_objective", "(not recorded)"))
    targets = json.dumps(data["target_metrics"], separators=(",", ":"))
    return config_sha, checkpoint_sha, objective, targets


def config_info(config_path: Path, platform: str, design: str) -> Tuple[Any, Any, Any]:
    config = load_driver_config(config_path)
    configurations = config.get("configurations")
    if not isinstance(configurations, list):
        raise DriverContractError(
            f"ERROR: driver config has no configurations list: {config_path}")
    entry = next((item for item in configurations
                  if isinstance(item, Mapping)
                  and item.get("platform") == platform
                  and item.get("design") == design), None)
    if entry is None:
        raise DriverContractError(
            f"ERROR: drp_config.json has no entry for platform='{platform}' "
            f"design='{design}'.\n"
            "       Add a configurations entry (clock_period_range + baseline "
            "wl_base/ecp_base)\n"
            "       before running, or metrics normalization will be garbage "
            "(wl_base=1.0).")
    baseline = entry.get("baseline")
    if not isinstance(baseline, Mapping):
        raise DriverContractError(
            f"ERROR: platform='{platform}' design='{design}' has no baseline object")
    try:
        wl_base = baseline["wl_base"]
        ecp_base = baseline["ecp_base"]
    except KeyError as exc:
        raise DriverContractError(
            f"ERROR: baseline for platform='{platform}' design='{design}' "
            f"is missing {exc.args[0]}") from exc
    power_budget = config.get("power_budget", "")
    if power_budget is None:
        power_budget = "None"
    return wl_base, ecp_base, power_budget


def write_manifest(path: Path, *, platform: str, design: str, objective: str,
                   seed: str, iterations: int, runs: int, num_kill: int,
                   selection: str, agentic: str, predictor: str,
                   predictor_rank_mode_value: str,
                   predictor_baseline_mode_value: str,
                   predictor_config_sha256: str,
                   predictor_checkpoint_sha256: str, power_budget: str,
                   weight_wl: str, weight_ecp: str, command: str,
                   git_commit: str, log: str,
                   llm_enabled: Any = "true") -> Dict[str, Any]:
    now = datetime.datetime.now(datetime.timezone.utc)
    manifest = {
        # Microseconds prevent same-seed campaigns started within one second
        # from sharing an identity in archives and downstream aggregations.
        "campaign_id": f"{now.strftime('%Y%m%d_%H%M%S_%f')}_seed{seed}",
        "started_utc": now.replace(tzinfo=None).isoformat() + "Z",
        "platform": platform,
        "design": design,
        "objective": objective,
        "seed": seed,
        "iterations": iterations,
        "runs": runs,
        "num_kill": num_kill,
        "selection": selection,
        "agentic": agentic,
        "llm_enabled": str(llm_enabled).strip().lower() in {"1", "true", "yes", "on"},
        "predictor": predictor,
        "predictor_rank_mode": predictor_rank_mode_value,
        "predictor_baseline_mode": predictor_baseline_mode_value,
        "predictor_config_sha256": predictor_config_sha256,
        "predictor_checkpoint_sha256": predictor_checkpoint_sha256,
        "power_budget": power_budget,
        "weight_wl": weight_wl,
        "weight_ecp": weight_ecp,
        "command": command,
        "git_commit": git_commit,
        "log": log,
        "llm_usage": {
            "schema_version": 1,
            "ledger": LLM_USAGE_LEDGER_NAME,
            "summary": LLM_USAGE_SUMMARY_NAME,
            "iteration_pattern": (
                "result_dump_{iteration}/llm_usage_iter{iteration}.json"
            ),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"[manifest] {path} written")
    return manifest


def assert_campaign_start_clean(state_path: Path, manifest_path: Path,
                                backup_dir: Path) -> None:
    """Reject implicit resume or overwrite of any live campaign artifact."""
    leftovers: List[str] = []
    if state_path.exists():
        leftovers.append(str(state_path))
    if manifest_path.exists():
        leftovers.append(str(manifest_path))
    if backup_dir.is_dir():
        for name in (LLM_USAGE_LEDGER_NAME, LLM_USAGE_SUMMARY_NAME):
            path = backup_dir / name
            if path.exists():
                leftovers.append(str(path))
        leftovers.extend(str(path) for path in sorted(
            backup_dir.glob("result_dump_*")) if path.is_dir())
    if leftovers:
        detail = ", ".join(leftovers[:4])
        if len(leftovers) > 4:
            detail += f", ... (+{len(leftovers) - 4})"
        raise DriverContractError(
            "ERROR: existing campaign artifacts would be overwritten "
            f"({detail}). Implicit resume is not supported; use -F to archive "
            "the old campaign and start a new one.")


def check_stage_success(metrics_path: Path, stage: str, objective: str,
                        num_runs: int, min_success: int,
                        require_cp0: bool) -> int:
    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DriverContractError(
            f"[gate][FAIL] {stage}: cannot read {metrics_path} ({exc})") from exc
    if not isinstance(metrics, list):
        raise DriverContractError(
            f"[gate][FAIL] {stage}: {metrics_path} is not a metrics list")
    key = objective if objective in VALID_OBJECTIVES else "combo"
    if objective == "TNS_EVAL" and require_cp0:
        valid = sum(1 for item in metrics if isinstance(item, Mapping)
                    and _is_finite_number(item.get("TNS_EVAL"))
                    and item.get("tns_source") == "cp0_eval")
        label = f"{key} (CP_0 eval)"
    else:
        valid = sum(1 for item in metrics if isinstance(item, Mapping)
                    and _is_finite_number(item.get(key)))
        label = key
    if valid < min_success:
        raise DriverContractError(
            f"[gate][FAIL] {stage}: {valid}/{num_runs} runs produced a valid "
            f"{label} (min {min_success}) \u2014 no signal to proceed.")
    print(f"[gate] {stage}: {valid}/{num_runs} runs produced a valid {label}")
    return valid


def _read_csv_rows(path: Path) -> Tuple[bytes, List[List[str]]]:
    try:
        raw = path.read_bytes()
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
    except OSError as exc:
        raise DriverContractError(f"ERROR: cannot read CSV {path}: {exc}") from exc
    return raw, rows


def validate_archived_csv(csv_path: Path, state_path: Path, iteration: int,
                          expected_rows: int) -> None:
    raw, rows = _read_csv_rows(csv_path)
    if (not rows or tuple(rows[0]) != FLOW_PARAM_NAMES
            or len(rows) - 1 != expected_rows):
        raise DriverContractError(
            "ERROR: archived input CSV schema/row count is invalid")
    if iteration > 1:
        if not state_path.is_file():
            raise DriverContractError(
                "ERROR: incoming batch state is missing for archived CSV")
        state = _read_json_object(state_path, description="incoming batch state")
        contract = state.get("next_batch_contract", {})
        if (not isinstance(contract, Mapping)
                or contract.get("sha256") != hashlib.sha256(raw).hexdigest()
                or int(contract.get("target_iteration", -1)) != iteration):
            raise DriverContractError(
                "ERROR: archived input CSV does not match incoming contract")
    print(f"[backup] archived executed batch -> {csv_path.name}")


def _artifact_run_ids(value: Any, *, label: str, expected_runs: int,
                      unique: bool = True) -> List[int]:
    if not isinstance(value, list):
        raise DriverContractError(f"ERROR: {label} must be a JSON list")
    run_ids: List[int] = []
    for raw in value:
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise DriverContractError(
                f"ERROR: {label} contains invalid run id {raw!r}")
        if raw < 1 or raw > expected_runs:
            raise DriverContractError(
                f"ERROR: {label} run id {raw} is outside 1..{expected_runs}")
        run_ids.append(raw)
    if unique and len(set(run_ids)) != len(run_ids):
        raise DriverContractError(f"ERROR: {label} contains duplicate run ids")
    return run_ids


def _validate_metrics_artifact(payload: Any, name: str,
                               expected_runs: int) -> None:
    if (not isinstance(payload, list)
            or not all(isinstance(item, Mapping) for item in payload)):
        raise DriverContractError(
            f"ERROR: metrics artifact must be a list of objects: {name}")
    run_ids = _artifact_run_ids(
        [item.get("run_id") for item in payload],
        label=f"{name} run_ids", expected_runs=expected_runs)
    if set(run_ids) != set(range(1, expected_runs + 1)):
        raise DriverContractError(
            f"ERROR: metrics artifact does not cover every run: {name}")
    for item in payload:
        for field in ("wl", "ecp", "combo", "tns", "TNS_EVAL", "power"):
            value = item.get(field)
            if value is not None and not _is_finite_number(value):
                raise DriverContractError(
                    f"ERROR: metrics artifact contains non-finite/non-numeric "
                    f"{field} for run {item.get('run_id')}: {name}")


def _validate_drp_artifact(payload: Any, name: str, iteration: int,
                           expected_runs: int, stage: str) -> List[str]:
    if not isinstance(payload, Mapping):
        raise DriverContractError(f"ERROR: DRP artifact must be an object: {name}")
    survivors = _artifact_run_ids(
        payload.get("survivor_ids"), label=f"{name} survivor_ids",
        expected_runs=expected_runs)
    victims = _artifact_run_ids(
        payload.get("victim_ids"), label=f"{name} victim_ids",
        expected_runs=expected_runs)
    sources = _artifact_run_ids(
        payload.get("source_ids"), label=f"{name} source_ids",
        expected_runs=expected_runs, unique=False)
    if set(survivors) & set(victims):
        raise DriverContractError(
            f"ERROR: DRP survivors/victims overlap: {name}")
    if set(survivors) | set(victims) != set(range(1, expected_runs + 1)):
        raise DriverContractError(
            f"ERROR: DRP survivors/victims do not cover every run: {name}")
    if len(sources) != len(victims):
        raise DriverContractError(
            f"ERROR: DRP source/victim counts differ: {name}")
    if not set(sources).issubset(set(survivors)):
        raise DriverContractError(
            f"ERROR: DRP clone source is not a survivor: {name}")

    events = payload.get("lineage_events")
    edges = payload.get("candidate_edges")
    if (not isinstance(events, list)
            or not all(isinstance(item, Mapping) for item in events)
            or len(events) != len(victims)):
        raise DriverContractError(
            f"ERROR: DRP lineage event count is invalid: {name}")
    if (not isinstance(edges, list)
            or not all(isinstance(item, Mapping) for item in edges)
            or len(edges) != len(victims)):
        raise DriverContractError(
            f"ERROR: DRP candidate-edge count is invalid: {name}")
    try:
        trusted_count = int(payload.get("lineage_trusted_count", -1))
    except (TypeError, ValueError) as exc:
        raise DriverContractError(
            f"ERROR: DRP trusted lineage count is invalid: {name}") from exc
    if trusted_count != len(victims):
        raise DriverContractError(
            f"ERROR: DRP artifact contains untrusted clone transactions: {name}")

    event_ids: List[str] = []
    for event, source, victim in zip(events, sources, victims):
        event_id = str(event.get("event_id") or "")
        if (event.get("iteration") != iteration
                or event.get("stage") != stage
                or event.get("source_run_id") != source
                or event.get("target_run_id") != victim
                or not event_id):
            raise DriverContractError(
                f"ERROR: DRP lineage identity mismatch: {name}")
        event_ids.append(event_id)
    edge_ids = [str(edge.get("lineage_event_id") or "") for edge in edges]
    if edge_ids != event_ids:
        raise DriverContractError(
            f"ERROR: DRP candidate edges do not match lineage events: {name}")

    stage_events = payload.get("stage_parameter_events")
    if stage_events is not None or "stage_parameter_count" in payload:
        expected_keys = (
            {"CTS_CLUSTER_SIZE", "CTS_CLUSTER_DIAMETER"}
            if stage == "place" else
            {"PIN_LAYER_ADJUST", "ABOVE_LAYER_ADJUST"}
        )
        if (not isinstance(stage_events, list)
                or len(stage_events) != expected_runs
                or payload.get("stage_parameter_count") != expected_runs):
            raise DriverContractError(
                f"ERROR: DRP full-run stage parameter count is invalid: {name}")
        targets = []
        for item in stage_events:
            if not isinstance(item, Mapping):
                raise DriverContractError(
                    f"ERROR: DRP stage parameter event is invalid: {name}")
            source = item.get("source_run_id")
            target = item.get("target_run_id")
            mapping_kind = item.get("mapping_kind")
            params = item.get("generated_params")
            apply_status = (item.get("status") or {}).get("params_apply")
            if (not isinstance(source, int) or not isinstance(target, int)
                    or mapping_kind not in {"self", "clone"}
                    or (mapping_kind == "self") != (source == target)
                    or not isinstance(params, Mapping)
                    or set(params) != expected_keys
                    or apply_status not in {"ok", "frozen_baseline"}):
                raise DriverContractError(
                    f"ERROR: DRP stage parameter mapping/schema is invalid: {name}")
            targets.append(target)
        if sorted(targets) != list(range(1, expected_runs + 1)):
            raise DriverContractError(
                f"ERROR: DRP stage parameters do not cover every run: {name}")
    return event_ids


def validate_backup(directory: Path, iteration: int, expected_runs: int,
                    manifest_path: Path, *, announce: bool = True) -> None:
    manifest = _read_json_object(manifest_path, description="campaign manifest")
    campaign_id = str(manifest.get("campaign_id") or "").strip()
    platform = str(manifest.get("platform") or "").strip()
    design = str(manifest.get("design") or "").strip()
    objective = str(manifest.get("objective") or "").strip()
    try:
        manifest_runs = int(manifest.get("runs", -1))
    except (TypeError, ValueError) as exc:
        raise DriverContractError(
            "ERROR: campaign manifest runs is not an integer") from exc
    if (not campaign_id or not platform or not design or not objective
            or manifest_runs != expected_runs):
        raise DriverContractError(
            "ERROR: campaign manifest identity/run count is incomplete or mismatched")
    names = canonical_artifact_names(iteration)
    artifacts: Dict[str, Any] = {}
    for name in names:
        artifact_path = directory / name
        artifacts[name] = _read_json(
            artifact_path, description="canonical artifact")

    for prefix in ("metrics_place", "metrics_cts", "metrics_final"):
        name = f"{prefix}_iter{iteration}.json"
        _validate_metrics_artifact(artifacts[name], name, expected_runs)

    drp_event_ids: Dict[str, List[str]] = {}
    for prefix, stage in (("drp_place", "place"), ("drp_cts", "cts")):
        name = f"{prefix}_iter{iteration}.json"
        drp_event_ids[stage] = _validate_drp_artifact(
            artifacts[name], name, iteration, expected_runs, stage)

    replay_name = f"config_replay_iter{iteration}.json"
    replay = artifacts[replay_name]
    replay_slots = replay.get("slots") if isinstance(replay, Mapping) else None
    if (not isinstance(replay, Mapping)
            or replay.get("schema_version") != 1
            or replay.get("campaign_id") != campaign_id
            or replay.get("platform") != platform
            or replay.get("design") != design
            or replay.get("objective") != objective
            or replay.get("iteration") != iteration
            or replay.get("status") != "ok"
            or not isinstance(replay_slots, list)
            or not all(isinstance(item, Mapping) for item in replay_slots)):
        raise DriverContractError(
            f"ERROR: config replay receipt identity/status mismatch: {replay_name}")
    _artifact_run_ids(
        [item.get("run_id") for item in replay_slots],
        label=f"{replay_name} slot run_ids", expected_runs=expected_runs)

    lineage_name = f"lineage_iter{iteration}.json"
    lineage = artifacts[lineage_name]
    stages = lineage.get("stages") if isinstance(lineage, Mapping) else None
    if (not isinstance(lineage, Mapping)
            or lineage.get("schema_version") != 1
            or lineage.get("campaign_id") != campaign_id
            or lineage.get("platform") != platform
            or lineage.get("design") != design
            or lineage.get("iteration") != iteration
            or not isinstance(stages, Mapping)):
        raise DriverContractError(
            f"ERROR: lineage artifact identity mismatch: {lineage_name}")
    for stage in ("place", "cts"):
        events = stages.get(stage)
        if (not isinstance(events, list)
                or not all(isinstance(item, Mapping) for item in events)
                or [str(item.get("event_id") or "") for item in events]
                != drp_event_ids[stage]):
            raise DriverContractError(
                f"ERROR: lineage summary does not match DRP {stage} events")

    lifecycle_name = f"candidate_lifecycle_iter{iteration}.json"
    payload = artifacts[lifecycle_name]
    slots = payload.get("slots") if isinstance(payload, dict) else None
    summary = payload.get("final_summary") if isinstance(payload, dict) else None
    run_ids = ([slot.get("run_id") for slot in slots]
               if isinstance(slots, list)
               and all(isinstance(slot, Mapping) for slot in slots) else [])
    if (not isinstance(payload, dict)
            or payload.get("schema_version") != 1
            or payload.get("campaign_id") != campaign_id
            or payload.get("iteration") != iteration
            or payload.get("status") != "finalized"
            or run_ids != list(range(1, expected_runs + 1))
            or not isinstance(summary, dict)
            or summary.get("complete") != expected_runs
            or summary.get("total") != expected_runs):
        raise DriverContractError(
            "ERROR: candidate lifecycle is not a complete canonical "
            f"artifact: {lifecycle_name}")
    if announce:
        print(f"[backup] verified {len(names)} canonical JSON artifacts "
              f"for iteration {iteration}")


def canonical_artifact_names(iteration: int) -> List[str]:
    """Return the complete, ordered per-iteration archive contract."""
    return [f"{prefix}_iter{iteration}.json"
            for prefix in CANONICAL_ARTIFACT_PREFIXES]


def archive_canonical_artifacts(source_directory: Path, directory: Path,
                                iteration: int, expected_runs: int,
                                manifest_path: Path) -> None:
    """Validate and publish one complete canonical artifact set.

    Copying one file at a time from the shell allowed a failed archive to expose a
    seven-file subset when candidate_lifecycle was absent.  Validate the source set
    first, stage byte-identical copies, and only then publish all eight artifacts.
    """
    source_directory = Path(source_directory)
    directory = Path(directory)
    names = canonical_artifact_names(iteration)

    # This validates presence, campaign identity, run coverage, DRP/lineage joins,
    # replay receipt, and the finalized lifecycle before touching the destination.
    validate_backup(
        source_directory, iteration, expected_runs, manifest_path,
        announce=False,
    )

    directory.mkdir(parents=True, exist_ok=True)
    existing = [name for name in names if (directory / name).exists()]
    if existing:
        raise DriverContractError(
            "ERROR: refusing to overwrite canonical iteration artifacts: "
            + ", ".join(existing))

    staging = Path(tempfile.mkdtemp(
        prefix=f".canonical_iter{iteration}_", dir=directory))
    published: List[Path] = []
    try:
        for name in names:
            source = source_directory / name
            staged = staging / name
            shutil.copy2(source, staged)
            if _sha256(source) != _sha256(staged):
                raise DriverContractError(
                    f"ERROR: canonical artifact copy hash mismatch: {name}")

        validate_backup(
            staging, iteration, expected_runs, manifest_path,
            announce=False,
        )
        for name in names:
            target = directory / name
            os.replace(staging / name, target)
            published.append(target)

        validate_backup(
            directory, iteration, expected_runs, manifest_path,
            announce=False,
        )
    except Exception:
        # No previous canonical files existed, so rollback can only remove files
        # published by this transaction.
        for path in published:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    print(f"[backup] archived and verified {len(names)} canonical JSON "
          f"artifacts for iteration {iteration}")


def _validated_protected_slots(state: Mapping[str, Any], path: Path,
                               num_runs: int) -> List[int]:
    collected: List[Any] = []
    for field in PROTECTED_SLOT_FIELDS:
        values = state.get(field, [])
        if not isinstance(values, list):
            raise DriverContractError(f"ERROR: {field} must be a list in {path}")
        collected.extend(values)
    validated: List[int] = []
    for raw in collected:
        if isinstance(raw, bool):
            raise DriverContractError(
                f"ERROR: invalid protected slot {raw!r} in {path}")
        try:
            slot = int(raw)
        except (TypeError, ValueError) as exc:
            raise DriverContractError(
                f"ERROR: invalid protected slot {raw!r} in {path}") from exc
        if slot < 2 or slot > num_runs:
            raise DriverContractError(
                f"ERROR: protected slot {slot} outside 2..{num_runs} in {path}")
        if slot not in validated:
            validated.append(slot)
    return sorted(validated)


def read_iteration_policy(state_path: Path, num_runs: int,
                          expected_iteration: int, csv_path: Path,
                          manifest_path: Path, platform: str, design: str,
                          objective: str) -> Tuple[str, List[int], bool, str, int]:
    if not state_path.is_file():
        if expected_iteration != 1:
            raise DriverContractError(
                f"ERROR: missing optimization state for iteration "
                f"{expected_iteration}")
        return "FULL_SEARCH", [], False, "", 0

    state = _read_json_object(state_path, description="optimization state")
    _validate_optimization_state(state, state_path)
    mode = ("FULL_SEARCH" if not state.get("enabled", True)
            else state.get("mode", "FULL_SEARCH"))
    if mode not in ("FULL_SEARCH", "ROUTING_FOCUS"):
        raise DriverContractError(
            f"ERROR: invalid optimization mode {mode!r} in {state_path}")
    for key, expected in (("platform", platform), ("design", design),
                          ("objective", objective)):
        if state.get(key) not in (None, expected):
            raise DriverContractError(
                f"ERROR: optimization state {key}={state.get(key)!r}, "
                f"expected {expected!r}")

    manifest = _read_json_object(manifest_path, description="campaign manifest")
    campaign_id = manifest.get("campaign_id")
    if not campaign_id or state.get("campaign_id") != campaign_id:
        raise DriverContractError(
            "ERROR: optimization state belongs to a different campaign; "
            "use -F for a new campaign")

    protected = _validated_protected_slots(state, state_path, num_runs)
    stop = bool(state.get("stop_requested", False))
    reason = str(state.get("stop_reason") or
                 state.get("transition_reason") or "unspecified")
    try:
        current_iteration = int(state.get("current_iteration", 0))
    except (TypeError, ValueError) as exc:
        raise DriverContractError(
            "ERROR: optimization state current_iteration is not an integer") from exc

    if not stop:
        expected_source = expected_iteration - 1
        if current_iteration != expected_source:
            raise DriverContractError(
                f"ERROR: state current_iteration={current_iteration}, but iteration "
                f"{expected_iteration} needs {expected_source}; use -F "
                "(resume is not implicit)")
        contract = state.get("next_batch_contract")
        if not isinstance(contract, Mapping):
            raise DriverContractError(
                "ERROR: next-batch contract missing from optimization state")
        try:
            target_iteration = int(contract.get("target_iteration", -1))
            source_iteration = int(contract.get("source_iteration", -1))
            row_count = int(contract.get("row_count", -1))
        except (TypeError, ValueError) as exc:
            raise DriverContractError(
                "ERROR: next-batch contract contains non-integer fields") from exc
        if target_iteration != expected_iteration:
            raise DriverContractError(
                "ERROR: next-batch target iteration does not match driver iteration")
        if source_iteration != current_iteration:
            raise DriverContractError(
                "ERROR: next-batch source iteration does not match state")
        if contract.get("campaign_id") != campaign_id:
            raise DriverContractError(
                "ERROR: next-batch contract belongs to a different campaign")
        if contract.get("path") != os.path.realpath(csv_path):
            raise DriverContractError(
                "ERROR: next-batch contract points to a different CSV path")
        if row_count != num_runs:
            raise DriverContractError(
                "ERROR: next-batch contract row count does not match "
                "--parallel-runs")
        raw, csv_rows = _read_csv_rows(csv_path)
        actual_header = tuple(csv_rows[0]) if csv_rows else ()
        actual_rows = max(0, len(csv_rows) - 1)
        if actual_rows != num_runs:
            raise DriverContractError(
                f"ERROR: next-batch CSV has {actual_rows} rows, "
                f"expected {num_runs}")
        if (actual_header != FLOW_PARAM_NAMES
                or tuple(contract.get("header", ())) != FLOW_PARAM_NAMES):
            raise DriverContractError(
                "ERROR: next-batch CSV header/order does not match flow schema")
        if hashlib.sha256(raw).hexdigest() != contract.get("sha256"):
            raise DriverContractError(
                "ERROR: next-batch CSV hash does not match optimization state")
    return str(mode), protected, stop, reason, current_iteration


def _numeric(value: Any, row_number: int, name: str) -> float:
    text = str(value).strip().lower()
    if text in {"true", "false"}:
        parsed = 1.0 if text == "true" else 0.0
    else:
        try:
            parsed = float(text)
        except (TypeError, ValueError) as exc:
            raise DriverContractError(
                f"ERROR: CSV row {row_number} field {name} is not numeric: "
                f"{value!r}") from exc
    if not math.isfinite(parsed):
        raise DriverContractError(
            f"ERROR: CSV row {row_number} field {name} is not finite")
    return parsed


def bind_candidates(lifecycle_path: Path, csv_path: Path, manifest_path: Path,
                    iteration: int, expected_runs: int) -> None:
    from candidate_tracking import (  # Imported only by this lifecycle command.
        assign_batch_identity,
        attach_metadata,
        bootstrap_slots,
        load_lifecycle,
        record_batch_stage,
    )

    manifest = _read_json_object(manifest_path, description="campaign manifest")
    campaign_id = str(manifest.get("campaign_id") or "").strip()
    if not campaign_id:
        raise DriverContractError("ERROR: campaign manifest has no campaign_id")
    try:
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != FLOW_PARAM_NAMES:
                raise DriverContractError(
                    "ERROR: candidate lifecycle cannot bind an invalid CSV schema")
            raw_rows = list(reader)
    except OSError as exc:
        raise DriverContractError(
            f"ERROR: cannot read candidate CSV {csv_path}: {exc}") from exc
    if len(raw_rows) != expected_runs:
        raise DriverContractError(
            f"ERROR: candidate lifecycle expected {expected_runs} CSV rows, "
            f"got {len(raw_rows)}")
    rows = [
        {name: _numeric(row[name], run_id, name) for name in FLOW_PARAM_NAMES}
        for run_id, row in enumerate(raw_rows, start=1)
    ]
    csv_sha = _sha256(csv_path)

    if iteration == 1:
        if lifecycle_path.exists():
            stale = load_lifecycle(lifecycle_path)
            if stale.get("campaign_id") != campaign_id:
                raise DriverContractError(
                    "ERROR: stale iteration-1 candidate lifecycle found; use -F "
                    "to start a fresh campaign")
            raise DriverContractError(
                "ERROR: iteration-1 candidate lifecycle already exists; implicit "
                "resume is not supported")
        origins = ["replay"] + ["lhs"] * (expected_runs - 1)
        proposal_keys = ["default-replay:run1"] + [
            f"initial-lhs:run{run_id}"
            for run_id in range(2, expected_runs + 1)
        ]
        candidates = assign_batch_identity(
            rows, campaign_id, iteration,
            origins=origins, proposal_keys=proposal_keys)
        bootstrap_slots(candidates, campaign_id=campaign_id,
                        iteration=iteration, path=lifecycle_path)
    else:
        if not lifecycle_path.is_file():
            raise DriverContractError(
                f"ERROR: optimizer did not create candidate lifecycle for "
                f"iteration {iteration}: {lifecycle_path}")
        payload = load_lifecycle(lifecycle_path)
        if (payload.get("campaign_id") != campaign_id
                or int(payload.get("iteration", -1)) != iteration):
            raise DriverContractError(
                "ERROR: candidate lifecycle belongs to a different "
                "campaign/iteration")
        slots = payload.get("slots", [])
        if len(slots) != expected_runs:
            raise DriverContractError(
                f"ERROR: lifecycle has {len(slots)} slots, expected "
                f"{expected_runs}")
        candidates = []
        for run_id, (slot, csv_params) in enumerate(zip(slots, rows), start=1):
            if int(slot.get("run_id", -1)) != run_id:
                raise DriverContractError(
                    "ERROR: lifecycle run slots are not contiguous/in order")
            planned = slot.get("current_params") or {}
            if set(planned) != set(FLOW_PARAM_NAMES):
                raise DriverContractError(
                    f"ERROR: lifecycle run {run_id} does not contain the "
                    "complete 10D upstream config")
            for name in FLOW_PARAM_NAMES:
                try:
                    planned_value = float(planned[name])
                except (TypeError, ValueError) as exc:
                    raise DriverContractError(
                        f"ERROR: lifecycle run {run_id} field {name} is not "
                        "numeric") from exc
                if not math.isclose(planned_value, csv_params[name],
                                    rel_tol=1e-12, abs_tol=1e-12):
                    raise DriverContractError(
                        f"ERROR: lifecycle/CSV mismatch at run {run_id} {name}: "
                        f"planned={planned_value!r}, "
                        f"csv={csv_params[name]!r}")
            candidates.append(attach_metadata(
                csv_params,
                candidate_id=slot["candidate_id"],
                origin=slot["origin"],
                parent=slot.get("parent"),
            ))

    payload = load_lifecycle(lifecycle_path)
    existing = [event for event in payload.get("events", [])
                if event.get("stage") == "csv_written"]
    if existing:
        if (len(existing) != expected_runs
                or {event.get("run_id") for event in existing}
                != set(range(1, expected_runs + 1))
                or any((event.get("details") or {}).get("csv_sha256") != csv_sha
                       for event in existing)):
            raise DriverContractError(
                "ERROR: conflicting/partial csv_written lifecycle events")
        print(f"[candidate] iteration {iteration} CSV binding already verified")
        return
    record_batch_stage(
        lifecycle_path,
        candidates,
        "csv_written",
        details=[{
            "csv_path": str(csv_path.resolve()),
            "csv_sha256": csv_sha,
            "row_number": run_id,
        } for run_id in range(1, expected_runs + 1)],
    )
    print(f"[candidate] bound {expected_runs} CSV rows -> "
          f"{lifecycle_path.name} (sha256={csv_sha[:12]}...)")


def check_baseline_final(metrics_path: Path, objective: str,
                         power_budget: str) -> None:
    metrics = _read_json(metrics_path, description="final metrics")
    if not isinstance(metrics, list):
        raise DriverContractError("ERROR: final metrics must be a JSON list")
    key = objective if objective in VALID_OBJECTIVES else "combo"
    runs = {item.get("run_id"): item for item in metrics
            if isinstance(item, Mapping)}
    baseline = runs.get(1)
    ok = baseline is not None and _is_finite_number(baseline.get(key))
    if ok and objective == "TNS_EVAL":
        ok = baseline.get("tns_source") == "cp0_eval"
        if ok and _optional_power_budget(power_budget) is not None:
            ok = _is_finite_number(baseline.get("power"))
    if not ok:
        raise DriverContractError(
            "ABORT: baseline run_1's FINAL metrics are invalid at iteration 1 "
            "(route/finish failed, or its CP_0 eval/power is missing). The "
            "campaign has no genuine baseline; refusing to continue on a "
            "pseudo-baseline.")
    print(f"[baseline] run_1 final {key} valid \u2014 genuine baseline established.")


def create_predictor_baseline(work_dir: Path, platform: str, design: str,
                              config_path: Path,
                              checkpoint_path: Path) -> None:
    from predictor_bridge import stage_prefix, write_trajectory_csv

    log_dir = work_dir / "logs" / platform / design / "run_1"
    config_dir = work_dir / "designs" / platform / design
    output = config_dir / "baseline_trajectory.csv"
    cp0 = float((config_dir / "cp0.txt").read_text(encoding="utf-8").strip())
    ok = write_trajectory_csv(
        log_dir,
        stage_prefix("final", config_path),
        output,
        run_id=1,
        config_dir=config_dir,
        config_path=config_path,
        checkpoint_path=checkpoint_path,
        eval_cp0=cp0,
    )
    sidecar = output.with_suffix(".meta.json")
    if not ok or not output.is_file() or not sidecar.is_file():
        raise DriverContractError(
            "default predictor baseline or metadata sidecar was not created")
    print(f"[predictor] baseline trajectory (default) saved -> {output} "
          f"(+ {sidecar.name})")


def update_predictor_baseline(work_dir: Path, platform: str, design: str,
                              iteration: int, objective: str,
                              config_path: Path,
                              checkpoint_path: Path) -> None:
    from predictor_bridge import update_baseline_best

    config_dir = work_dir / "designs" / platform / design
    result = update_baseline_best(
        work_dir,
        platform,
        design,
        iteration,
        objective,
        config_dir / "baseline_trajectory.csv",
        config_dir / "baseline_best.txt",
        config_path=config_path,
        checkpoint_path=checkpoint_path,
    )
    if result:
        print(f"[predictor] baseline (best) updated -> run {result[0]} "
              f"({objective}={result[1]:.4f})")
    else:
        print("[predictor] baseline (best) unchanged "
              "(no improving full-survivor)")
    baseline = config_dir / "baseline_trajectory.csv"
    sidecar = baseline.with_suffix(".meta.json")
    if not baseline.is_file() or not sidecar.is_file():
        raise DriverContractError(
            "best predictor baseline or metadata sidecar is missing")


def final_metrics_report(metrics_path: Path, objective: str,
                         power_budget_raw: str, platform: str,
                         design: str) -> None:
    from common import _power_base, tns_eval_obj

    metrics = _read_json(metrics_path, description="final metrics")
    if not isinstance(metrics, list):
        raise DriverContractError("ERROR: final metrics must be a JSON list")
    power_budget = _optional_power_budget(power_budget_raw)
    power_base = _power_base(platform, design) if objective == "TNS_EVAL" else None

    def sort_key(metric: Mapping[str, Any]) -> float:
        value = (tns_eval_obj(metric, power_budget, power_base)
                 if objective == "TNS_EVAL" else metric.get(objective))
        return value if value is not None else float("inf")

    header = "  {:>5} | {:>12} | {:>12} | {:>12} | {:>12} | {:>10} | {:>6}"
    print(header.format(
        "Run", "WL", "ECP", "Combo", "TNS_eval", "Power(W)", "Feas"))
    print("  " + " | ".join(
        ["-" * 5, "-" * 12, "-" * 12, "-" * 12, "-" * 12,
         "-" * 10, "-" * 6]))
    for metric in sorted(metrics, key=sort_key):
        wl = (f"{metric['wl']:.2f}" if metric.get("wl") is not None else "N/A")
        ecp = (f"{metric['ecp']:.4f}"
               if metric.get("ecp") is not None else "N/A")
        combo = (f"{metric['combo']:.4f}"
                 if metric.get("combo") is not None else "N/A")
        tns = (f"{metric['tns']:.2f}"
               if metric.get("tns") is not None else "N/A")
        power = (f"{metric['power']:.4f}"
                 if metric.get("power") is not None else "N/A")
        if objective == "TNS_EVAL" and power_budget is not None and power_base:
            value = tns_eval_obj(metric, power_budget, power_base)
            feasible = "-" if value is None else ("no" if value >= 1e9 else "yes")
        else:
            feasible = ""
        print(header.format(
            metric["run_id"], wl, ecp, combo, tns, power, feasible))
    if objective == "TNS_EVAL" and power_budget is not None and power_base:
        feasible_metrics = [
            (tns_eval_obj(metric, power_budget, power_base), metric)
            for metric in metrics
        ]
        feasible_metrics = [
            (value, metric) for value, metric in feasible_metrics
            if value is not None and value < 1e9
        ]
        if feasible_metrics:
            value, metric = min(feasible_metrics, key=lambda item: item[0])
            print(f"  BEST (power-feasible, <= "
                  f"{(1 + power_budget) * power_base:.4f} W): "
                  f"run {metric['run_id']}  |TNS|={value:.2f}  "
                  f"power={metric.get('power')}")
        else:
            print("  BEST: none power-feasible this iteration")


def read_stop_fields(state_path: Path) -> Tuple[bool, str]:
    state = _read_json_object(state_path, description="optimization state")
    _validate_optimization_state(state, state_path)
    stop = state.get("stop_requested", False)
    reason = str(state.get("stop_reason") or
                 state.get("transition_reason") or "unspecified")
    return stop, reason


def _add_path(parser: argparse.ArgumentParser, name: str, **kwargs: Any) -> None:
    parser.add_argument(name, type=Path, **kwargs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    sub = commands.add_parser("validate-combo-weights")
    sub.add_argument("--weight-wl", required=True)
    sub.add_argument("--weight-ecp", required=True)

    for name in ("predictor-rank-mode", "predictor-baseline-mode"):
        sub = commands.add_parser(name)
        _add_path(sub, "--config", required=True)

    sub = commands.add_parser("predictor-metadata")
    _add_path(sub, "--config", required=True)
    _add_path(sub, "--checkpoint", required=True)

    sub = commands.add_parser("predictor-preflight")
    _add_path(sub, "--config", required=True)
    _add_path(sub, "--checkpoint", required=True)

    sub = commands.add_parser("config-info")
    _add_path(sub, "--config", required=True)
    sub.add_argument("--platform", required=True)
    sub.add_argument("--design", required=True)

    sub = commands.add_parser("write-manifest")
    _add_path(sub, "--path", required=True)
    for name in ("platform", "design", "objective", "seed", "selection",
                 "agentic", "llm-enabled", "predictor", "predictor-rank-mode",
                 "predictor-baseline-mode", "predictor-config-sha256",
                 "predictor-checkpoint-sha256", "power-budget", "weight-wl",
                 "weight-ecp", "invocation", "git-commit", "log"):
        sub.add_argument(f"--{name}", required=True)
    sub.add_argument("--iterations", required=True, type=int)
    sub.add_argument("--runs", required=True, type=int)
    sub.add_argument("--num-kill", required=True, type=int)

    sub = commands.add_parser("campaign-start-guard")
    _add_path(sub, "--state", required=True)
    _add_path(sub, "--manifest", required=True)
    _add_path(sub, "--backup-dir", required=True)

    sub = commands.add_parser("stage-gate")
    _add_path(sub, "--metrics", required=True)
    sub.add_argument("--stage", required=True)
    sub.add_argument("--objective", required=True)
    sub.add_argument("--runs", required=True, type=int)
    sub.add_argument("--min-success", required=True, type=int)
    sub.add_argument("--require-cp0", action="store_true")

    sub = commands.add_parser("validate-archived-csv")
    _add_path(sub, "--csv", required=True)
    _add_path(sub, "--state", required=True)
    sub.add_argument("--iteration", required=True, type=int)
    sub.add_argument("--runs", required=True, type=int)

    sub = commands.add_parser("validate-backup")
    _add_path(sub, "--directory", required=True)
    _add_path(sub, "--manifest", required=True)
    sub.add_argument("--iteration", required=True, type=int)
    sub.add_argument("--runs", required=True, type=int)

    sub = commands.add_parser("archive-canonical")
    _add_path(sub, "--source-directory", required=True)
    _add_path(sub, "--directory", required=True)
    _add_path(sub, "--manifest", required=True)
    sub.add_argument("--iteration", required=True, type=int)
    sub.add_argument("--runs", required=True, type=int)

    sub = commands.add_parser("iteration-policy")
    _add_path(sub, "--state", required=True)
    _add_path(sub, "--csv", required=True)
    _add_path(sub, "--manifest", required=True)
    sub.add_argument("--runs", required=True, type=int)
    sub.add_argument("--iteration", required=True, type=int)
    sub.add_argument("--platform", required=True)
    sub.add_argument("--design", required=True)
    sub.add_argument("--objective", required=True)

    sub = commands.add_parser("bind-candidates")
    _add_path(sub, "--lifecycle", required=True)
    _add_path(sub, "--csv", required=True)
    _add_path(sub, "--manifest", required=True)
    sub.add_argument("--iteration", required=True, type=int)
    sub.add_argument("--runs", required=True, type=int)

    sub = commands.add_parser("baseline-final-check")
    _add_path(sub, "--metrics", required=True)
    sub.add_argument("--objective", required=True)
    sub.add_argument("--power-budget", required=True)

    for name in ("predictor-baseline-create", "predictor-baseline-update"):
        sub = commands.add_parser(name)
        _add_path(sub, "--work-dir", required=True)
        sub.add_argument("--platform", required=True)
        sub.add_argument("--design", required=True)
        _add_path(sub, "--config", required=True)
        _add_path(sub, "--checkpoint", required=True)
        if name.endswith("update"):
            sub.add_argument("--iteration", required=True, type=int)
            sub.add_argument("--objective", required=True)

    sub = commands.add_parser("final-metrics-report")
    _add_path(sub, "--metrics", required=True)
    sub.add_argument("--objective", required=True)
    sub.add_argument("--power-budget", required=True)
    sub.add_argument("--platform", required=True)
    sub.add_argument("--design", required=True)

    sub = commands.add_parser("stop-fields")
    _add_path(sub, "--state", required=True)
    return parser


def dispatch(args: argparse.Namespace) -> None:
    command = args.command
    if command == "validate-combo-weights":
        validate_combo_weights(args.weight_wl, args.weight_ecp)
    elif command == "predictor-rank-mode":
        print(predictor_rank_mode(args.config))
    elif command == "predictor-baseline-mode":
        print(predictor_baseline_mode(args.config))
    elif command == "predictor-metadata":
        print("|".join(predictor_metadata(args.config, args.checkpoint)))
    elif command == "predictor-preflight":
        from predictor_bridge import preflight_predictor
        preflight_predictor(args.config, args.checkpoint)
        print(f"[predictor] preflight passed: config={args.config}, "
              f"checkpoint={args.checkpoint}")
    elif command == "config-info":
        print("|".join(map(str, config_info(
            args.config, args.platform, args.design))))
    elif command == "write-manifest":
        write_manifest(
            args.path,
            platform=args.platform,
            design=args.design,
            objective=args.objective,
            seed=args.seed,
            iterations=args.iterations,
            runs=args.runs,
            num_kill=args.num_kill,
            selection=args.selection,
            agentic=args.agentic,
            llm_enabled=args.llm_enabled,
            predictor=args.predictor,
            predictor_rank_mode_value=args.predictor_rank_mode,
            predictor_baseline_mode_value=args.predictor_baseline_mode,
            predictor_config_sha256=args.predictor_config_sha256,
            predictor_checkpoint_sha256=args.predictor_checkpoint_sha256,
            power_budget=args.power_budget,
            weight_wl=args.weight_wl,
            weight_ecp=args.weight_ecp,
            command=args.invocation,
            git_commit=args.git_commit,
            log=args.log,
        )
    elif command == "campaign-start-guard":
        assert_campaign_start_clean(
            args.state, args.manifest, args.backup_dir)
    elif command == "stage-gate":
        check_stage_success(
            args.metrics, args.stage, args.objective, args.runs,
            args.min_success, args.require_cp0)
    elif command == "validate-archived-csv":
        validate_archived_csv(
            args.csv, args.state, args.iteration, args.runs)
    elif command == "validate-backup":
        validate_backup(
            args.directory, args.iteration, args.runs, args.manifest)
    elif command == "archive-canonical":
        archive_canonical_artifacts(
            args.source_directory, args.directory, args.iteration,
            args.runs, args.manifest)
    elif command == "iteration-policy":
        mode, protected, stop, reason, current = read_iteration_policy(
            args.state, args.runs, args.iteration, args.csv, args.manifest,
            args.platform, args.design, args.objective)
        print(f"{mode}|{','.join(map(str, protected))}|"
              f"{'1' if stop else '0'}|{_pipe_safe(reason)}|{current}")
    elif command == "bind-candidates":
        bind_candidates(
            args.lifecycle, args.csv, args.manifest,
            args.iteration, args.runs)
    elif command == "baseline-final-check":
        check_baseline_final(args.metrics, args.objective, args.power_budget)
    elif command == "predictor-baseline-create":
        create_predictor_baseline(
            args.work_dir, args.platform, args.design,
            args.config, args.checkpoint)
    elif command == "predictor-baseline-update":
        update_predictor_baseline(
            args.work_dir, args.platform, args.design, args.iteration,
            args.objective, args.config, args.checkpoint)
    elif command == "final-metrics-report":
        final_metrics_report(
            args.metrics, args.objective, args.power_budget,
            args.platform, args.design)
    elif command == "stop-fields":
        stop, reason = read_stop_fields(args.state)
        print(f"{'1' if stop else '0'}|{_pipe_safe(reason)}")
    else:  # pragma: no cover - argparse rejects unknown subcommands.
        raise DriverContractError(f"ERROR: unsupported command {command}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        dispatch(args)
    except DriverContractError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
