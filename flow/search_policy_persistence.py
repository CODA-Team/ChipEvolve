"""Atomic persistence helpers for campaign search-policy state."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


STATE_VERSION = 1


def load_optimization_state(state_path: Path) -> Optional[Dict[str, Any]]:
    """Load a previously persisted policy state."""
    path = Path(state_path)
    if not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read optimization state {path}: {exc}") from exc
    if not isinstance(state, dict) or state.get("state_version") != STATE_VERSION:
        raise RuntimeError(f"unsupported optimization state in {path}")
    return state


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            tmp_name = handle.name
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass

def persist_optimization_state(state_path: Path,
                               state: Mapping[str, Any]) -> Dict[str, Any]:
    """Persist an already-computed state without attaching a next-batch contract."""
    payload = dict(state)
    _atomic_write_json(Path(state_path), payload)
    return payload


def persist_batch_plan(state_path: Path, state: Mapping[str, Any],
                       plan: Mapping[str, Any], *,
                       csv_path: Optional[Path] = None,
                       target_iteration: Optional[int] = None,
                       expected_rows: Optional[int] = None) -> Dict[str, Any]:
    """Attach the next-batch contract used by maindriver and persist atomically."""
    merged = dict(state)
    plan_payload = dict(plan)
    if csv_path is not None:
        artifact = Path(csv_path)
        if not artifact.is_file():
            raise RuntimeError(f"next-batch CSV is missing: {artifact}")
        with artifact.open("r", encoding="utf-8", newline="") as handle:
            csv_rows = list(csv.reader(handle))
        header = csv_rows[0] if csv_rows else []
        row_count = max(0, len(csv_rows) - 1)
        if expected_rows is not None and row_count != int(expected_rows):
            raise RuntimeError(
                f"next-batch CSV row count {row_count} != expected {expected_rows}")
        contract = {
            "path": str(artifact.resolve()),
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "row_count": row_count,
            "header": header,
            "source_iteration": int(state.get("current_iteration", 0)),
            "target_iteration": (
                int(target_iteration) if target_iteration is not None else None),
            "campaign_id": state.get("campaign_id"),
        }
        plan_payload["batch_contract"] = contract
        merged["next_batch_contract"] = contract
    merged["next_batch_plan"] = plan_payload
    merged["protected_replay_slots"] = list(
        plan.get("protected_replay_slots", [])
    )
    merged["protected_config_replay_slots"] = list(
        plan.get("protected_config_replay_slots", [])
    )
    merged["config_replay_slots"] = [
        dict(item) for item in plan.get("config_replay_slots", [])
        if isinstance(item, Mapping)
    ]
    merged["protected_probe_slots"] = list(
        plan.get("protected_probe_slots", [])
    )
    merged["protected_focus_control_slots"] = list(
        plan.get("protected_focus_control_slots", [])
    )
    merged["protected_focus_experiment_slots"] = list(
        plan.get("protected_focus_experiment_slots", [])
    )
    merged["protected_candidate_slots"] = list(
        plan.get("protected_candidate_slots", [])
    )
    merged["protected_candidate_ids"] = list(
        plan.get("protected_candidate_ids", [])
    )
    merged["protected_candidate_families"] = list(
        plan.get("protected_candidate_families", [])
    )
    merged["candidate_slots"] = [
        dict(item) for item in plan.get("candidate_slots", [])
        if isinstance(item, Mapping)
    ]
    focus_model = plan.get("routing_focus_model", {})
    agentic_tools = (focus_model.get("agentic_tools", {})
                     if isinstance(focus_model, Mapping) else {})
    if isinstance(agentic_tools, Mapping) and agentic_tools.get("configured"):
        merged["routing_focus_agentic"] = {
            "model": dict(agentic_tools.get("model_config") or {}),
            "selection": dict(agentic_tools.get("selection_config") or {}),
            "feature_weights": list(
                (agentic_tools.get("inspection") or {}).get("feature_weights") or []),
            "tool_requests": dict(agentic_tools.get("tool_requests") or {}),
            "tool_calls": dict(agentic_tools.get("tool_calls") or {}),
            "tool_configs_applied": dict(
                agentic_tools.get("tool_configs_applied") or {}),
            "tool_audit": dict(agentic_tools.get("tool_audit") or {}),
            "source_iteration": int(state.get("current_iteration", 0)),
        }
    _atomic_write_json(Path(state_path), merged)
    return merged


__all__ = [
    "STATE_VERSION",
    "_atomic_write_json",
    "load_optimization_state",
    "persist_batch_plan",
    "persist_optimization_state",
]
