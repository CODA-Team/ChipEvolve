#!/usr/bin/env python3
"""Materialize phase-scoped parameters for protected static-config replays.

A lineage-resolved routing child can use one pair of layer adjustments while its
floorplan is built and another pair after CTS.  The ordinary CSV only represents
the latter.  This module restores the floorplan-scoped values immediately after
Phase 0 creates the per-run configs; no physical checkpoint is saved or restored.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from config_recipe import (
    SCHEMA_VERSION,
    SCOPED_PARAM_NAMES,
    recipe_from_scoped,
)
from lineage import CONFIG_PARAM_NAMES, atomic_write_json, config_snapshot, utc_now


SCOPED_PARAMS = SCOPED_PARAM_NAMES


def _load_json_object(path: Path, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number, not bool")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be finite and within [0, 1]")
    return number


def _validate_scoped_params(raw: Any) -> Dict[str, float]:
    if not isinstance(raw, Mapping):
        raise ValueError("scoped_params must be a JSON object")
    keys = set(map(str, raw))
    required = set(SCOPED_PARAMS)
    if keys != required:
        missing = sorted(required - keys)
        extra = sorted(keys - required)
        raise ValueError(
            f"scoped_params must contain exactly {list(SCOPED_PARAMS)}; "
            f"missing={missing}, extra={extra}"
        )
    return {name: _number(raw[name], name) for name in SCOPED_PARAMS}


def _validate_config_context(config_path: Path) -> Dict[str, Any]:
    snapshot = config_snapshot(config_path)
    params = snapshot.get("params") or {}
    missing = sorted(set(CONFIG_PARAM_NAMES) - set(params))
    if missing:
        raise ValueError(
            f"generated config lacks tunable context {missing}: {config_path}")
    sdc = snapshot.get("effective_sdc") or {}
    if "clk_period" not in params or not sdc.get("sha256"):
        raise ValueError(f"generated config has no resolvable clock SDC: {config_path}")
    return snapshot


def _recipe_signature(snapshot: Mapping[str, Any],
                      scoped: Mapping[str, float]) -> str:
    sdc = snapshot.get("effective_sdc") or {}
    identity = sdc.get("recipe_sha256", sdc.get("sha256"))
    recipe = recipe_from_scoped(snapshot.get("params"), scoped, identity)
    if recipe is None:
        raise ValueError("generated config cannot form a complete canonical recipe")
    return str(recipe["signature"])


def _replace_assignment(content: str, name: str, value: float) -> str:
    pattern = re.compile(
        rf"^[ \t]*(?:export[ \t]+)?{re.escape(name)}[ \t]*=.*$", re.MULTILINE)
    matches = list(pattern.finditer(content))
    if len(matches) > 1:
        raise ValueError(f"config contains duplicate {name} assignments")
    assignment = f"export {name} = {repr(value)}"
    if matches:
        return pattern.sub(assignment, content, count=1)
    separator = "" if not content or content.endswith("\n") else "\n"
    return f"{content}{separator}{assignment}\n"


def _atomic_write_text(path: Path, content: str) -> None:
    mode = path.stat().st_mode
    fd, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(raw_temp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _materialize_one(config_path: Path, entry: Mapping[str, Any]) -> Dict[str, Any]:
    before = _validate_config_context(config_path)
    scoped = _validate_scoped_params(entry.get("scoped_params"))
    expected_signature = str(entry["recipe_signature"])
    actual_signature = _recipe_signature(before, scoped)
    if actual_signature != expected_signature:
        raise ValueError(
            f"config replay recipe signature mismatch for {config_path}: "
            f"state={expected_signature}, materialized={actual_signature}")
    content = config_path.read_text(encoding="utf-8")
    for name, value in scoped.items():
        content = _replace_assignment(content, name, value)
    _atomic_write_text(config_path, content)

    after = _validate_config_context(config_path)
    context = after.get("routing_context") or {}
    expected_context = {
        "PIN_LAYER_ADJUST": scoped["FLOORPLAN_PIN_LAYER_ADJUST"],
        "ABOVE_LAYER_ADJUST": scoped["FLOORPLAN_ABOVE_LAYER_ADJUST"],
    }
    if context.get("source") != "explicit_floorplan" or any(
        context.get(name) != value for name, value in expected_context.items()
    ):
        raise RuntimeError(
            f"materialized floorplan context failed snapshot validation: {config_path}")
    if _recipe_signature(after, scoped) != expected_signature:
        raise RuntimeError(f"materialized recipe identity changed: {config_path}")
    installed = config_path.read_text(encoding="utf-8")
    for name, value in scoped.items():
        matches = re.findall(
            rf"^[ \t]*(?:export[ \t]+)?{re.escape(name)}[ \t]*=[ \t]*([^#\s]+)",
            installed, flags=re.MULTILINE)
        if len(matches) != 1 or float(matches[0]) != value:
            raise RuntimeError(f"failed to verify materialized {name} in {config_path}")

    result = {
        "run_id": int(entry["run_id"]),
        "recipe_signature": str(entry["recipe_signature"]),
        "scoped_params": scoped,
        "config_path": str(config_path),
        "config_before": before,
        "config_after": after,
        "status": "ok",
    }
    for name in ("role", "origin_iteration", "origin_run_id", "reference_objective"):
        if name in entry:
            result[name] = entry[name]
    return result


def materialize(
    *,
    state_path: Path,
    config_dir: Path,
    output_path: Path,
    iteration: int,
    num_runs: int,
    platform: str,
    design: str,
    objective: str,
    manifest_path: Optional[Path] = None,
) -> Dict[str, Any]:
    if iteration < 1 or num_runs < 2:
        raise ValueError("iteration must be >=1 and num_runs must be >=2")
    # A failed retry must never leave a prior receipt that create_backup could accept.
    try:
        output_path.unlink()
    except FileNotFoundError:
        pass

    state: Dict[str, Any] = {}
    if state_path.is_file():
        state = _load_json_object(state_path, "optimization state")
        for key, expected in (
            ("platform", platform), ("design", design), ("objective", objective)):
            if state.get(key) not in (None, expected):
                raise ValueError(
                    f"optimization state {key}={state.get(key)!r}, expected {expected!r}")
        if iteration > 1:
            try:
                state_iteration = int(state.get("current_iteration", -1))
            except (TypeError, ValueError) as exc:
                raise ValueError("optimization state current_iteration is invalid") from exc
            if state_iteration != iteration - 1:
                raise ValueError(
                    f"optimization state iteration {state_iteration} "
                    f"cannot materialize iteration {iteration}")
    elif iteration != 1:
        raise ValueError(f"optimization state is missing for iteration {iteration}: {state_path}")

    campaign_id = state.get("campaign_id")
    if manifest_path is not None:
        manifest = _load_json_object(manifest_path, "campaign manifest")
        manifest_campaign = manifest.get("campaign_id")
        if not manifest_campaign:
            raise ValueError("campaign manifest has no campaign_id")
        if state and campaign_id != manifest_campaign:
            raise ValueError("optimization state belongs to a different campaign")
        campaign_id = manifest_campaign

    raw_plan = state.get("config_replay_slots", [])
    if not isinstance(raw_plan, list):
        raise ValueError("optimization_state.config_replay_slots must be a list")

    validated = []
    seen_runs = set()
    for raw in raw_plan:
        if not isinstance(raw, Mapping):
            raise ValueError("each config_replay_slots entry must be an object")
        try:
            run_id = int(raw.get("run_id"))
        except (TypeError, ValueError) as exc:
            raise ValueError("config replay run_id must be an integer") from exc
        if isinstance(raw.get("run_id"), bool) or not 1 <= run_id <= num_runs:
            raise ValueError(f"config replay run_id {run_id} outside 1..{num_runs}")
        signature = raw.get("recipe_signature")
        if not isinstance(signature, str) or not signature.strip():
            raise ValueError(f"config replay slot {run_id} has no recipe_signature")
        if run_id in seen_runs:
            raise ValueError(f"duplicate config replay run_id {run_id}")
        normalized = {
            "run_id": run_id,
            "recipe_signature": signature,
            "scoped_params": _validate_scoped_params(raw.get("scoped_params")),
        }
        for name in ("role", "origin_iteration", "origin_run_id", "reference_objective"):
            if name in raw:
                normalized[name] = raw[name]
        validated.append(normalized)
        seen_runs.add(run_id)

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "platform": platform,
        "design": design,
        "objective": objective,
        "iteration": iteration,
        "created_utc": utc_now(),
        "slots": [],
        "status": "ok",
    }
    for entry in validated:
        config_path = config_dir / f"config_{entry['run_id']}.mk"
        receipt["slots"].append(_materialize_one(config_path, entry))

    atomic_write_json(output_path, receipt)
    return receipt


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    command = subparsers.add_parser("materialize")
    command.add_argument("--state", type=Path, required=True)
    command.add_argument("--config-dir", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--iteration", type=int, required=True)
    command.add_argument("--num-runs", type=int, required=True)
    command.add_argument("--platform", required=True)
    command.add_argument("--design", required=True)
    command.add_argument("--objective", required=True)
    command.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)

    try:
        receipt = materialize(
            state_path=args.state,
            config_dir=args.config_dir,
            output_path=args.output,
            iteration=args.iteration,
            num_runs=args.num_runs,
            platform=args.platform,
            design=args.design,
            objective=args.objective,
            manifest_path=args.manifest,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[config-replay][ERROR] {exc}", file=sys.stderr)
        return 1
    print(
        f"[config-replay] materialized {len(receipt['slots'])} slot(s) "
        f"for iteration {args.iteration} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
