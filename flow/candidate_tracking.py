#!/usr/bin/env python3
"""Stable candidate provenance and per-iteration lifecycle records.

Optimizer parameters are reshaped several times before a run is executed.  The
reserved metadata in this module travels with a candidate while numeric-only
consumers can remove it explicitly.  Candidate identity is derived from a stable
proposal key, never from parameters that later shaping passes may change.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


SCHEMA_VERSION = 1

CANDIDATE_ID_KEY = "_candidate_id"
CANDIDATE_ORIGIN_KEY = "_candidate_origin"
CANDIDATE_PARENT_KEY = "_candidate_parent"
RESERVED_METADATA_KEYS = frozenset({
    CANDIDATE_ID_KEY,
    CANDIDATE_ORIGIN_KEY,
    CANDIDATE_PARENT_KEY,
})

ALLOWED_ORIGINS = frozenset({
    "llm",
    "bayes",
    "lhs",
    "exploit",
    "replay",
    "full_probe",
    "focus_exact",
    "focus_agent2",
    "focus_novelty",
})


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    """Return a deterministic, JSON-safe representation of ordinary state."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("candidate tracking values must be finite")
        return 0.0 if value == 0.0 else value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(
            value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    # NumPy scalar values expose item() but importing NumPy here would make the
    # provenance path depend on the modeling environment.
    item = getattr(value, "item", None)
    if callable(item):
        converted = item()
        if converted is not value:
            return _jsonable(converted)
    raise TypeError(f"value is not JSON serializable: {type(value).__name__}")


def _validate_origin(origin: Any) -> str:
    value = str(origin).strip() if origin is not None else ""
    if value not in ALLOWED_ORIGINS:
        raise ValueError(
            f"candidate origin must be one of {sorted(ALLOWED_ORIGINS)}; "
            f"got {origin!r}")
    return value


def _validate_candidate_id(candidate_id: Any) -> str:
    value = str(candidate_id).strip() if candidate_id is not None else ""
    if not value:
        raise ValueError("candidate_id must be a non-empty string")
    return value


def _parent_id(parent: Any) -> Optional[str]:
    if parent is None:
        return None
    if isinstance(parent, Mapping):
        parent = parent.get(CANDIDATE_ID_KEY)
    return _validate_candidate_id(parent)


def make_candidate_id(
    campaign_id: Any,
    iteration: int,
    proposal_key: Any = None,
    *,
    stable_key: Any = None,
) -> str:
    """Build an identity from immutable proposal provenance.

    ``proposal_key`` should be assigned when the proposal is created (for
    example ``"lhs:17"`` or ``"clone:cts:<parent-id>:run41"``).  Parameters
    deliberately are not accepted by this function because clock/CTS quotas and
    other shaping operations may alter them after selection.
    """
    campaign = str(campaign_id).strip() if campaign_id is not None else ""
    if not campaign:
        raise ValueError("campaign_id must be a non-empty string")
    try:
        iteration_value = int(iteration)
    except (TypeError, ValueError) as exc:
        raise ValueError("iteration must be a positive integer") from exc
    if iteration_value < 1 or isinstance(iteration, bool):
        raise ValueError("iteration must be a positive integer")
    if proposal_key is not None and stable_key is not None and proposal_key != stable_key:
        raise ValueError("proposal_key and stable_key disagree")
    if proposal_key is None:
        proposal_key = stable_key
    if proposal_key is None or proposal_key == "":
        raise ValueError("proposal_key must be non-empty")
    identity_payload = {
        "campaign_id": campaign,
        "iteration": iteration_value,
        "proposal_key": _jsonable(proposal_key),
        "schema_version": SCHEMA_VERSION,
    }
    encoded = json.dumps(
        identity_payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"cand-i{iteration_value:04d}-{digest[:24]}"


def metadata(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a copy of the reserved metadata present on ``candidate``."""
    if not isinstance(candidate, Mapping):
        raise TypeError("candidate must be a mapping")
    return {
        key: candidate[key]
        for key in (CANDIDATE_ID_KEY, CANDIDATE_ORIGIN_KEY, CANDIDATE_PARENT_KEY)
        if key in candidate
    }


def strip_metadata(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    """Return only executable/model parameters from a candidate mapping."""
    if not isinstance(candidate, Mapping):
        raise TypeError("candidate must be a mapping")
    return {
        str(key): value for key, value in candidate.items()
        if key not in RESERVED_METADATA_KEYS and not str(key).startswith("_")
    }


def attach_metadata(
    params: Mapping[str, Any],
    *,
    candidate_id: Any,
    origin: Any,
    parent: Any = None,
) -> Dict[str, Any]:
    """Attach validated reserved metadata without mutating ``params``."""
    result = strip_metadata(params)
    result[CANDIDATE_ID_KEY] = _validate_candidate_id(candidate_id)
    result[CANDIDATE_ORIGIN_KEY] = _validate_origin(origin)
    parent_id = _parent_id(parent)
    if parent_id is not None:
        result[CANDIDATE_PARENT_KEY] = parent_id
    return result


def preserve_metadata(
    params: Mapping[str, Any], source: Mapping[str, Any]
) -> Dict[str, Any]:
    """Copy candidate metadata from ``source`` onto transformed parameters."""
    result = strip_metadata(params)
    result.update(metadata(source))
    return result


def ensure_candidate(
    candidate: Mapping[str, Any],
    campaign_id: Any = None,
    iteration: Optional[int] = None,
    proposal_key: Any = None,
    origin: Any = None,
    parent: Any = None,
) -> Dict[str, Any]:
    """Validate an existing identity or assign one from a stable proposal key."""
    current = metadata(candidate)
    candidate_id = current.get(CANDIDATE_ID_KEY)
    current_origin = current.get(CANDIDATE_ORIGIN_KEY)
    current_parent = current.get(CANDIDATE_PARENT_KEY)

    if candidate_id is None:
        if campaign_id is None or iteration is None or proposal_key is None:
            raise ValueError(
                "campaign_id, iteration, and proposal_key are required for an "
                "unidentified candidate")
        candidate_id = make_candidate_id(campaign_id, iteration, proposal_key)
    else:
        candidate_id = _validate_candidate_id(candidate_id)

    if current_origin is None:
        if origin is None:
            raise ValueError("origin is required for a candidate without origin metadata")
        resolved_origin = _validate_origin(origin)
    else:
        resolved_origin = _validate_origin(current_origin)
        if origin is not None and _validate_origin(origin) != resolved_origin:
            raise ValueError(
                f"candidate origin cannot change from {resolved_origin!r} to {origin!r}")

    resolved_parent = _parent_id(current_parent)
    requested_parent = _parent_id(parent)
    if resolved_parent is None:
        resolved_parent = requested_parent
    elif requested_parent is not None and requested_parent != resolved_parent:
        raise ValueError(
            f"candidate parent cannot change from {resolved_parent!r} "
            f"to {requested_parent!r}")

    return attach_metadata(
        candidate, candidate_id=candidate_id, origin=resolved_origin,
        parent=resolved_parent)


def _optional_sequence_value(
    values: Optional[Sequence[Any]], index: int, expected: int, label: str
) -> Any:
    if values is None:
        return None
    if len(values) != expected:
        raise ValueError(f"{label} has {len(values)} entries; expected {expected}")
    return values[index]


def assign_batch_identity(
    candidates: Sequence[Mapping[str, Any]],
    campaign_id: Any,
    iteration: int,
    *,
    origin: str = "lhs",
    origins: Optional[Sequence[str]] = None,
    proposal_keys: Optional[Sequence[Any]] = None,
    parents: Optional[Sequence[Any]] = None,
) -> List[Dict[str, Any]]:
    """Assign stable identity to a batch while preserving existing identities."""
    total = len(candidates)
    identified: List[Dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        proposal_key = _optional_sequence_value(
            proposal_keys, index, total, "proposal_keys")
        if proposal_key is None:
            proposal_key = f"slot:{index + 1}"
        item_origin = _optional_sequence_value(origins, index, total, "origins")
        if item_origin is None:
            item_origin = metadata(candidate).get(CANDIDATE_ORIGIN_KEY, origin)
        item_parent = _optional_sequence_value(parents, index, total, "parents")
        identified.append(ensure_candidate(
            candidate,
            campaign_id=campaign_id,
            iteration=iteration,
            proposal_key=proposal_key,
            origin=item_origin,
            parent=item_parent,
        ))
    ids = [item[CANDIDATE_ID_KEY] for item in identified]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate batch contains duplicate candidate IDs")
    return identified


def lifecycle_path(work_dir: Path, iteration: int) -> Path:
    """Return the canonical live lifecycle path for an iteration."""
    return Path(work_dir) / "tmp" / f"candidate_lifecycle_iter{int(iteration)}.json"


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(raw_temp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(_jsonable(payload), stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _validate_lifecycle(payload: Any, path: Optional[Path] = None) -> Dict[str, Any]:
    label = f" {path}" if path is not None else ""
    if not isinstance(payload, dict):
        raise ValueError(f"candidate lifecycle{label} must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported candidate lifecycle schema{label}")
    if not str(payload.get("campaign_id", "")).strip():
        raise ValueError(f"candidate lifecycle{label} has no campaign_id")
    try:
        iteration = int(payload.get("iteration"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"candidate lifecycle{label} has invalid iteration") from exc
    if iteration < 1:
        raise ValueError(f"candidate lifecycle{label} has invalid iteration")
    slots = payload.get("slots")
    events = payload.get("events")
    candidates = payload.get("candidates")
    if (not isinstance(slots, list) or not isinstance(events, list)
            or not isinstance(candidates, dict)):
        raise ValueError(
            f"candidate lifecycle{label} has invalid candidates/slots/events")
    run_ids = [slot.get("run_id") for slot in slots if isinstance(slot, dict)]
    if len(run_ids) != len(slots) or len(run_ids) != len(set(run_ids)):
        raise ValueError(f"candidate lifecycle{label} has invalid/duplicate slots")
    for candidate_id, candidate in candidates.items():
        if (not isinstance(candidate, dict)
                or candidate.get("candidate_id") != candidate_id):
            raise ValueError(
                f"candidate lifecycle{label} has an invalid candidate registry")
        _validate_origin(candidate.get("origin"))
    return payload


def load_lifecycle(path: Path) -> Dict[str, Any]:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read candidate lifecycle {path}: {exc}") from exc
    return _validate_lifecycle(payload, path)


def _slot_from_candidate(run_id: int, candidate: Mapping[str, Any]) -> Dict[str, Any]:
    candidate_meta = metadata(candidate)
    candidate_id = _validate_candidate_id(candidate_meta.get(CANDIDATE_ID_KEY))
    origin = _validate_origin(candidate_meta.get(CANDIDATE_ORIGIN_KEY))
    parent = _parent_id(candidate_meta.get(CANDIDATE_PARENT_KEY))
    slot = {
        "run_id": int(run_id),
        "candidate_id": candidate_id,
        "origin": origin,
        "parent": parent,
        "initial_params": _jsonable(strip_metadata(candidate)),
        "current_params": _jsonable(strip_metadata(candidate)),
        "event_ids": [],
        "superseded_candidate_ids": [],
        "final": None,
    }
    return slot


def _new_lifecycle(campaign_id: Any, iteration: int) -> Dict[str, Any]:
    campaign = str(campaign_id).strip() if campaign_id is not None else ""
    if not campaign:
        raise ValueError("campaign_id must be a non-empty string")
    try:
        iteration_value = int(iteration)
    except (TypeError, ValueError) as exc:
        raise ValueError("iteration must be a positive integer") from exc
    if iteration_value < 1 or isinstance(iteration, bool):
        raise ValueError("iteration must be a positive integer")
    now = _utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": campaign,
        "iteration": iteration_value,
        "created_utc": now,
        "updated_utc": now,
        "finalized_utc": None,
        "status": "active",
        "next_event_sequence": 1,
        "candidates": {},
        "slots": [],
        "events": [],
    }


def _register_candidate(
    payload: Dict[str, Any], candidate: Mapping[str, Any]
) -> Dict[str, Any]:
    candidate_meta = metadata(candidate)
    candidate_id = _validate_candidate_id(candidate_meta.get(CANDIDATE_ID_KEY))
    origin = _validate_origin(candidate_meta.get(CANDIDATE_ORIGIN_KEY))
    parent = _parent_id(candidate_meta.get(CANDIDATE_PARENT_KEY))
    params = _jsonable(strip_metadata(candidate))
    registry = payload.setdefault("candidates", {})
    entity = registry.get(candidate_id)
    if entity is None:
        now = _utc_now()
        entity = {
            "candidate_id": candidate_id,
            "origin": origin,
            "parent": parent,
            "initial_params": params,
            "current_params": params,
            "created_utc": now,
            "updated_utc": now,
            "event_ids": [],
            "bound_run_ids": [],
            "final": None,
            "final_by_run": {},
        }
        registry[candidate_id] = entity
        return entity
    if entity.get("origin") != origin or entity.get("parent") != parent:
        raise ValueError(
            f"candidate {candidate_id} metadata conflicts with its registry entry")
    entity["current_params"] = params
    entity["updated_utc"] = _utc_now()
    return entity


def bootstrap_slots(
    candidates: Sequence[Mapping[str, Any]],
    *,
    campaign_id: Any,
    iteration: int,
    path: Optional[Path] = None,
    origin: str = "lhs",
    origins: Optional[Sequence[str]] = None,
    proposal_keys: Optional[Sequence[Any]] = None,
    parents: Optional[Sequence[Any]] = None,
) -> Dict[str, Any]:
    """Create the lifecycle and its run-slot identities from a candidate batch."""
    identified = assign_batch_identity(
        candidates, campaign_id, iteration, origin=origin, origins=origins,
        proposal_keys=proposal_keys, parents=parents)
    payload = _new_lifecycle(campaign_id, iteration)
    for run_id, candidate in enumerate(identified, start=1):
        entity = _register_candidate(payload, candidate)
        entity["bound_run_ids"].append(run_id)
        payload["slots"].append(_slot_from_candidate(run_id, candidate))
    _validate_lifecycle(payload)
    if path is not None:
        _atomic_write_json(Path(path), payload)
    return payload


def _slot(payload: Mapping[str, Any], run_id: int) -> Dict[str, Any]:
    for slot in payload.get("slots", []):
        if int(slot.get("run_id", -1)) == int(run_id):
            return slot
    raise ValueError(f"candidate lifecycle has no run slot {run_id}")


def _append_event(
    payload: Dict[str, Any],
    holder: Dict[str, Any],
    *,
    stage: str,
    status: str,
    run_id: Optional[int] = None,
    details: Optional[Mapping[str, Any]] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    stage_value = str(stage).strip()
    status_value = str(status).strip()
    if not stage_value or not status_value:
        raise ValueError("candidate event stage and status must be non-empty")
    sequence = int(payload.get("next_event_sequence", len(payload["events"]) + 1))
    event: Dict[str, Any] = {
        "event_id": f"event-{sequence:06d}",
        "sequence": sequence,
        "recorded_utc": _utc_now(),
        "stage": stage_value,
        "status": status_value,
        "run_id": int(run_id) if run_id is not None else (
            int(holder["run_id"]) if holder.get("run_id") is not None else None),
        "candidate_id": holder["candidate_id"],
        "origin": holder["origin"],
        "parent": holder.get("parent"),
        "params": _jsonable(holder.get("current_params", {})),
        "details": _jsonable(details or {}),
    }
    if extra:
        event.update(_jsonable(extra))
    payload["events"].append(event)
    holder.setdefault("event_ids", []).append(event["event_id"])
    payload["next_event_sequence"] = sequence + 1
    return event


def _install_candidate(slot: Dict[str, Any], candidate: Mapping[str, Any]) -> None:
    candidate_meta = metadata(candidate)
    new_id = _validate_candidate_id(candidate_meta.get(CANDIDATE_ID_KEY))
    old_id = slot.get("candidate_id")
    if old_id and old_id != new_id:
        superseded = slot.setdefault("superseded_candidate_ids", [])
        if old_id not in superseded:
            superseded.append(old_id)
    slot["candidate_id"] = new_id
    slot["origin"] = _validate_origin(candidate_meta.get(CANDIDATE_ORIGIN_KEY))
    slot["parent"] = _parent_id(candidate_meta.get(CANDIDATE_PARENT_KEY))
    slot["current_params"] = _jsonable(strip_metadata(candidate))


def _link_event_to_slot(slot: Dict[str, Any], event_id: str) -> None:
    event_ids = slot.setdefault("event_ids", [])
    if event_id not in event_ids:
        event_ids.append(event_id)


def _bind_entity_to_run(entity: Dict[str, Any], run_id: int) -> None:
    runs = entity.setdefault("bound_run_ids", [])
    run_id = int(run_id)
    if run_id not in runs:
        runs.append(run_id)


def record_pool_stage(
    path: Path,
    candidates: Sequence[Mapping[str, Any]],
    stage: str,
    *,
    status: str = "ok",
    details: Optional[Any] = None,
    campaign_id: Any = None,
    iteration: Optional[int] = None,
    origin: str = "lhs",
    origins: Optional[Sequence[str]] = None,
    proposal_keys: Optional[Sequence[Any]] = None,
    parents: Optional[Sequence[Any]] = None,
) -> Dict[str, Any]:
    """Record an arbitrary-size candidate pool without creating run slots."""
    path = Path(path)
    if path.is_file():
        payload = load_lifecycle(path)
        campaign_id = payload["campaign_id"]
        iteration = payload["iteration"]
    elif campaign_id is None or iteration is None:
        raise ValueError(
            "campaign_id and iteration are required to create a lifecycle")
    else:
        payload = _new_lifecycle(campaign_id, iteration)

    identified = assign_batch_identity(
        candidates, campaign_id, int(iteration), origin=origin, origins=origins,
        proposal_keys=proposal_keys, parents=parents)
    if details is None or isinstance(details, Mapping):
        per_candidate_details = [details] * len(identified)
    else:
        if not isinstance(details, Sequence) or isinstance(details, (str, bytes)):
            raise TypeError("details must be a mapping or one mapping per candidate")
        if len(details) != len(identified):
            raise ValueError("per-candidate details count does not match pool")
        per_candidate_details = list(details)

    for candidate, item_details in zip(identified, per_candidate_details):
        if not isinstance(item_details or {}, Mapping):
            raise TypeError("each candidate event detail must be a mapping")
        entity = _register_candidate(payload, candidate)
        _append_event(
            payload, entity, stage=stage, status=status, details=item_details)
    payload["updated_utc"] = _utc_now()
    _validate_lifecycle(payload)
    _atomic_write_json(path, payload)
    return payload


def bind_slots(
    path: Path,
    selected_candidates: Sequence[Mapping[str, Any]],
    stage: str = "selected",
    *,
    status: str = "ok",
    details: Optional[Any] = None,
) -> Dict[str, Any]:
    """Bind a selected batch to run IDs after arbitrary pool-stage recording."""
    path = Path(path)
    payload = load_lifecycle(path)
    selected = list(selected_candidates)
    if not selected:
        raise ValueError("selected candidate batch must not be empty")
    if payload["slots"] and len(payload["slots"]) != len(selected):
        raise ValueError(
            f"selected batch has {len(selected)} candidates; lifecycle has "
            f"{len(payload['slots'])} existing slots")
    if details is None or isinstance(details, Mapping):
        per_candidate_details = [details] * len(selected)
    else:
        if not isinstance(details, Sequence) or isinstance(details, (str, bytes)):
            raise TypeError("details must be a mapping or one mapping per candidate")
        if len(details) != len(selected):
            raise ValueError("per-candidate details count does not match selection")
        per_candidate_details = list(details)

    if not payload["slots"]:
        payload["slots"] = [
            _slot_from_candidate(run_id, candidate)
            for run_id, candidate in enumerate(selected, start=1)
        ]
    for run_id, (candidate, item_details) in enumerate(
            zip(selected, per_candidate_details), start=1):
        if not isinstance(item_details or {}, Mapping):
            raise TypeError("each candidate event detail must be a mapping")
        slot = _slot(payload, run_id)
        previous_id = slot.get("candidate_id")
        _install_candidate(slot, candidate)
        entity = _register_candidate(payload, candidate)
        _bind_entity_to_run(entity, run_id)
        event = _append_event(
            payload,
            entity,
            stage=stage,
            status=status,
            run_id=run_id,
            details=item_details,
            extra={
                "event_type": "slot_bind",
                "previous_candidate_id": (
                    previous_id if previous_id != entity["candidate_id"] else None),
            },
        )
        _link_event_to_slot(slot, event["event_id"])
    payload["updated_utc"] = _utc_now()
    _validate_lifecycle(payload)
    _atomic_write_json(path, payload)
    return payload


def record_candidate_stage(
    path: Path,
    candidate: Mapping[str, Any],
    stage: str,
    *,
    run_id: Optional[int] = None,
    status: str = "ok",
    details: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Atomically record one candidate's state at a lifecycle stage."""
    path = Path(path)
    payload = load_lifecycle(path)
    candidate_id = metadata(candidate).get(CANDIDATE_ID_KEY)
    if run_id is None:
        matches = [slot for slot in payload["slots"]
                   if slot.get("candidate_id") == candidate_id]
        if len(matches) != 1:
            raise ValueError(
                "run_id is required unless candidate_id identifies exactly one slot")
        slot = matches[0]
    else:
        slot = _slot(payload, run_id)
    _install_candidate(slot, candidate)
    entity = _register_candidate(payload, candidate)
    _bind_entity_to_run(entity, int(slot["run_id"]))
    event = _append_event(
        payload, entity, stage=stage, status=status,
        run_id=int(slot["run_id"]), details=details)
    _link_event_to_slot(slot, event["event_id"])
    payload["updated_utc"] = _utc_now()
    _atomic_write_json(path, payload)
    return payload


def record_batch_stage(
    path: Path,
    candidates: Sequence[Mapping[str, Any]],
    stage: str,
    *,
    status: str = "ok",
    details: Optional[Any] = None,
    campaign_id: Any = None,
    iteration: Optional[int] = None,
    origin: str = "lhs",
    origins: Optional[Sequence[str]] = None,
    proposal_keys: Optional[Sequence[Any]] = None,
    parents: Optional[Sequence[Any]] = None,
) -> Dict[str, Any]:
    """Record one event per run using a single atomic lifecycle update."""
    path = Path(path)
    if path.is_file():
        payload = load_lifecycle(path)
        identified = list(candidates)
    else:
        if campaign_id is None or iteration is None:
            raise ValueError(
                "campaign_id and iteration are required to create a lifecycle")
        payload = bootstrap_slots(
            candidates, campaign_id=campaign_id, iteration=iteration,
            origin=origin, origins=origins, proposal_keys=proposal_keys,
            parents=parents)
        identified = [attach_metadata(
            slot["current_params"], candidate_id=slot["candidate_id"],
            origin=slot["origin"], parent=slot.get("parent"))
            for slot in payload["slots"]]

    if len(identified) != len(payload["slots"]):
        raise ValueError(
            f"stage batch has {len(identified)} candidates; lifecycle has "
            f"{len(payload['slots'])} slots")
    if details is None or isinstance(details, Mapping):
        per_slot_details = [details] * len(identified)
    else:
        if not isinstance(details, Sequence) or isinstance(details, (str, bytes)):
            raise TypeError("details must be a mapping or one mapping per candidate")
        if len(details) != len(identified):
            raise ValueError("per-candidate details count does not match batch")
        per_slot_details = list(details)

    for run_id, (candidate, item_details) in enumerate(
            zip(identified, per_slot_details), start=1):
        if not isinstance(item_details or {}, Mapping):
            raise TypeError("each candidate event detail must be a mapping")
        slot = _slot(payload, run_id)
        _install_candidate(slot, candidate)
        entity = _register_candidate(payload, candidate)
        _bind_entity_to_run(entity, run_id)
        event = _append_event(
            payload, entity, stage=stage, status=status, run_id=run_id,
            details=item_details)
        _link_event_to_slot(slot, event["event_id"])
    payload["updated_utc"] = _utc_now()
    _atomic_write_json(path, payload)
    return payload


def record_clone_event(
    path: Path,
    stage: str,
    source_run_id: int,
    target_run_id: int,
    *,
    generated_params: Optional[Mapping[str, Any]] = None,
    origin: Optional[str] = None,
    proposal_key: Any = None,
    status: str = "ok",
    details: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Install and record a lineage child in a target run slot."""
    if int(source_run_id) == int(target_run_id):
        raise ValueError("clone source and target run IDs must differ")
    path = Path(path)
    payload = load_lifecycle(path)
    source = _slot(payload, source_run_id)
    target = _slot(payload, target_run_id)
    parent_id = _validate_candidate_id(source.get("candidate_id"))
    child_origin = _validate_origin(origin or source.get("origin"))
    if proposal_key is None:
        proposal_key = f"clone:{stage}:{parent_id}:run{int(target_run_id)}"
    child_id = make_candidate_id(
        payload["campaign_id"], payload["iteration"], proposal_key)
    child_params = dict(source.get("current_params") or {})
    if generated_params:
        child_params.update(strip_metadata(generated_params))
    child = attach_metadata(
        child_params, candidate_id=child_id, origin=child_origin,
        parent=parent_id)
    replaced_id = target.get("candidate_id")
    _install_candidate(target, child)
    child_entity = _register_candidate(payload, child)
    _bind_entity_to_run(child_entity, int(target_run_id))
    event = _append_event(
        payload,
        child_entity,
        stage=stage,
        status=status,
        run_id=int(target_run_id),
        details=details,
        extra={
            "event_type": "clone",
            "source_run_id": int(source_run_id),
            "target_run_id": int(target_run_id),
            "source_candidate_id": parent_id,
            "replaced_candidate_id": replaced_id,
            "generated_params": _jsonable(strip_metadata(generated_params or {})),
        },
    )
    _link_event_to_slot(target, event["event_id"])
    _link_event_to_slot(source, event["event_id"])
    source_entity = payload["candidates"].get(parent_id)
    if source_entity is not None:
        event_ids = source_entity.setdefault("event_ids", [])
        if event["event_id"] not in event_ids:
            event_ids.append(event["event_id"])
    payload["updated_utc"] = _utc_now()
    _atomic_write_json(path, payload)
    return payload


def _metrics_by_run(path: Path) -> Dict[int, Dict[str, Any]]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read final metrics {path}: {exc}") from exc
    if isinstance(raw, dict) and isinstance(raw.get("runs"), list):
        raw = raw["runs"]
    elif isinstance(raw, dict):
        converted = []
        for key, value in raw.items():
            if not isinstance(value, Mapping):
                continue
            row = dict(value)
            row.setdefault("run_id", key)
            converted.append(row)
        raw = converted
    if not isinstance(raw, list):
        raise ValueError("final metrics must be a JSON list or run mapping")
    result: Dict[int, Dict[str, Any]] = {}
    for row in raw:
        if not isinstance(row, Mapping) or "run_id" not in row:
            raise ValueError("each final metric must be an object with run_id")
        try:
            run_id = int(row["run_id"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid metric run_id: {row.get('run_id')!r}") from exc
        if run_id in result:
            raise ValueError(f"duplicate final metric for run {run_id}")
        result[run_id] = _jsonable(dict(row))
    return result


def finalize_iteration(
    lifecycle: Path,
    metrics: Path,
    config_dir: Path,
    *,
    output: Optional[Path] = None,
    strict: bool = False,
) -> Dict[str, Any]:
    """Attach final metrics and effective config snapshots to every run slot."""
    from lineage import config_snapshot

    lifecycle = Path(lifecycle)
    output = Path(output) if output is not None else lifecycle
    payload = load_lifecycle(lifecycle)
    metric_rows = _metrics_by_run(Path(metrics))
    complete = missing_metrics = config_errors = 0

    for slot in payload["slots"]:
        run_id = int(slot["run_id"])
        metric = metric_rows.get(run_id)
        config_path = Path(config_dir) / f"config_{run_id}.mk"
        snapshot = None
        snapshot_error = None
        try:
            snapshot = config_snapshot(config_path)
        except Exception as exc:
            snapshot_error = f"{type(exc).__name__}: {exc}"
        if metric is None:
            missing_metrics += 1
        if snapshot_error is not None:
            config_errors += 1
        if metric is not None and snapshot is not None:
            final_status = "complete"
            complete += 1
        elif metric is None and snapshot is None:
            final_status = "missing_metrics_and_config"
        elif metric is None:
            final_status = "missing_metrics"
        else:
            final_status = "config_snapshot_failed"
        final = {
            "status": final_status,
            "finalized_utc": _utc_now(),
            "metrics": metric,
            "config_snapshot": _jsonable(snapshot) if snapshot is not None else None,
            "config_snapshot_error": snapshot_error,
            "effective_params": _jsonable((snapshot or {}).get("params") or {}),
        }
        slot["final"] = final
        candidate_id = _validate_candidate_id(slot.get("candidate_id"))
        entity = payload["candidates"].get(candidate_id)
        if entity is None:
            entity = _register_candidate(payload, attach_metadata(
                slot.get("current_params") or {}, candidate_id=candidate_id,
                origin=slot.get("origin"), parent=slot.get("parent")))
        entity["final"] = final
        entity.setdefault("final_by_run", {})[str(run_id)] = final
        event = _append_event(
            payload, entity, stage="finalize", status=final_status,
            run_id=run_id, details={
                "metrics_present": metric is not None,
                "config_snapshot_present": snapshot is not None,
            })
        _link_event_to_slot(slot, event["event_id"])

    summary = {
        "total": len(payload["slots"]),
        "complete": complete,
        "missing_metrics": missing_metrics,
        "config_snapshot_errors": config_errors,
    }
    payload["finalized_utc"] = _utc_now()
    payload["updated_utc"] = payload["finalized_utc"]
    payload["status"] = "finalized" if complete == len(payload["slots"]) else "partial"
    payload["final_summary"] = summary
    _atomic_write_json(output, payload)
    if strict and payload["status"] != "finalized":
        raise RuntimeError(
            "candidate lifecycle finalization is incomplete: "
            f"{json.dumps(summary, sort_keys=True)}")
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record and finalize optimizer candidate lifecycles")
    subparsers = parser.add_subparsers(dest="command", required=True)
    finalize = subparsers.add_parser(
        "finalize", help="attach final metrics and effective config snapshots")
    finalize.add_argument("--lifecycle", type=Path, required=True)
    finalize.add_argument("--metrics", type=Path, required=True)
    finalize.add_argument("--config-dir", type=Path, required=True)
    finalize.add_argument("--output", type=Path)
    finalize.add_argument("--strict", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "finalize":
        result = finalize_iteration(
            args.lifecycle, args.metrics, args.config_dir,
            output=args.output, strict=args.strict)
        print(json.dumps(result["final_summary"], sort_keys=True))
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
