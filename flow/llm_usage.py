#!/usr/bin/env python3
"""Campaign-scoped accounting for external LLM API usage.

The optimizer launches several Python processes per iteration, so an in-memory
counter cannot represent a campaign. Each request appends lifecycle events to one
JSONL ledger. Summaries are derived artifacts and can always be rebuilt from it.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

try:
    import fcntl
except ImportError:  # pragma: no cover - DRP-Agent runs on Unix hosts.
    fcntl = None


SCHEMA_VERSION = 1
LEDGER_NAME = "llm_usage_events.jsonl"
SUMMARY_NAME = "llm_usage_summary.json"
LEDGER_ENV = "DRP_LLM_USAGE_FILE"
CAMPAIGN_ENV = "DRP_CAMPAIGN_ID"

_CONTEXT_KEYS = (
    "scope",
    "stage",
    "agent",
    "operation",
    "react_step",
    "source_iteration",
    "target_iteration",
)

_IDENTITY_KEYS = (
    "schema_version",
    "campaign_id",
    "platform",
    "design",
    "objective",
    "iteration",
    "pid",
    "requested_model",
    "provider_hash",
    *_CONTEXT_KEYS,
)


class LLMUsageError(RuntimeError):
    """Raised when the usage ledger or summary contract is invalid."""


@dataclass(frozen=True)
class CallHandle:
    call_id: str
    enabled: bool
    started_monotonic: float
    identity: Dict[str, Any]


def _utc_now() -> str:
    return (datetime.datetime.now(datetime.timezone.utc)
            .isoformat(timespec="milliseconds").replace("+00:00", "Z"))


def _optional_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isinstance(value, str):
        try:
            if value != parsed:
                return None
        except Exception:
            return None
    return parsed if parsed >= 0 else None


def _env_iteration() -> Optional[int]:
    return _optional_int(os.environ.get("DRP_ITER", "").strip())


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _stable_hash(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8")
    except Exception:
        try:
            fallback = repr(value)
        except Exception:
            fallback = f"<unrepresentable:{type(value).__name__}>"
        encoded = fallback.encode("utf-8", errors="replace")
    return hashlib.sha256(encoded).hexdigest()


def _provider_hash(provider: Optional[str]) -> Optional[str]:
    if not provider:
        return None
    provider_text = _optional_text(provider)
    if provider_text is None:
        return None
    return hashlib.sha256(provider_text.encode("utf-8")).hexdigest()[:16]


def _optional_text(value: Any) -> Optional[str]:
    """Return JSON-safe provider metadata without retaining SDK objects."""
    if value is None:
        return None
    try:
        return str(value)
    except Exception:
        return f"<unprintable:{type(value).__name__}>"


def _usage_path() -> Optional[Path]:
    raw = os.environ.get(LEDGER_ENV, "").strip()
    return Path(raw) if raw else None


def _append_event(path: Path, event: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        line = json.dumps(dict(event), sort_keys=True, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise LLMUsageError(
            f"LLM usage event is not JSON serializable: {exc}") from exc
    try:
        with path.open("a", encoding="utf-8") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        raise LLMUsageError(f"cannot append LLM usage event to {path}: {exc}") from exc


def _identity(context: Optional[Mapping[str, Any]], model: str,
              provider: Optional[str]) -> Tuple[Optional[Path], Dict[str, Any]]:
    path = _usage_path()
    campaign_id = os.environ.get(CAMPAIGN_ENV, "").strip()
    if path is None and not campaign_id:
        return None, {}
    if path is None or not campaign_id:
        raise LLMUsageError(
            f"{LEDGER_ENV} and {CAMPAIGN_ENV} must be set together")

    supplied = dict(context or {})
    event_iteration = _env_iteration()
    if event_iteration is None:
        event_iteration = _optional_int(supplied.get("iteration"))
    identity: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "platform": os.environ.get("PLATFORM") or None,
        "design": os.environ.get("DESIGN") or None,
        "objective": os.environ.get("OBJECTIVE") or None,
        "iteration": event_iteration,
        "pid": os.getpid(),
        "requested_model": _optional_text(model) or "unknown",
        "provider_hash": _provider_hash(provider),
    }
    for key in _CONTEXT_KEYS:
        value = supplied.get(key)
        if key in {"react_step", "source_iteration", "target_iteration"}:
            value = _optional_int(value)
        elif value is not None:
            value = _optional_text(value)
        identity[key] = value
    return path, identity


def begin_call(*, model: str, context: Optional[Mapping[str, Any]] = None,
               request_payload: Any = None,
               provider: Optional[str] = None) -> CallHandle:
    """Record the start of one external request and return its durable identity."""
    path, identity = _identity(context, model, provider)
    call_id = uuid.uuid4().hex
    started = time.monotonic()
    if path is None:
        return CallHandle(call_id, False, started, {})
    event = {
        **identity,
        "event": "request_started",
        "call_id": call_id,
        "timestamp_utc": _utc_now(),
        "request_sha256": _stable_hash(request_payload),
    }
    if os.environ.get('DRP_EXECUTION_BACKEND') == 'platform':
        from platform_model import process_identity
        event['process_identity'] = process_identity(os.getpid())
    _append_event(path, event)
    return CallHandle(call_id, True, started, identity)


def _usage_values(response: Any) -> Dict[str, Any]:
    usage = _field(response, "usage")
    prompt = _optional_int(_field(usage, "prompt_tokens"))
    completion = _optional_int(_field(usage, "completion_tokens"))
    total = _optional_int(_field(usage, "total_tokens"))

    # Keep the recorder compatible with a future Responses API adapter and with
    # gateways that expose Responses-style names on an otherwise compatible result.
    if prompt is None:
        prompt = _optional_int(_field(usage, "input_tokens"))
    if completion is None:
        completion = _optional_int(_field(usage, "output_tokens"))
    total_source = "reported" if total is not None else None
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
        total_source = "derived_prompt_plus_completion"

    counts_consistent: Optional[bool] = None
    if prompt is not None and completion is not None and total is not None:
        counts_consistent = total == prompt + completion

    prompt_details = (_field(usage, "prompt_tokens_details")
                      or _field(usage, "input_tokens_details"))
    completion_details = (_field(usage, "completion_tokens_details")
                          or _field(usage, "output_tokens_details"))
    cached = _optional_int(_field(prompt_details, "cached_tokens"))
    reasoning = _optional_int(_field(completion_details, "reasoning_tokens"))
    available = any(value is not None for value in (prompt, completion, total))
    complete = (
        all(value is not None for value in (prompt, completion, total))
        and counts_consistent is not False
    )
    return {
        "usage_available": available,
        "usage_complete": complete,
        "usage_consistent": counts_consistent,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "total_tokens_source": total_source,
        "cached_tokens": cached,
        "reasoning_tokens": reasoning,
    }


def finish_call(call: CallHandle, response: Any) -> None:
    """Record a returned response and its provider-reported usage."""
    if not call.enabled:
        return
    path = _usage_path()
    if path is None:
        raise LLMUsageError(f"{LEDGER_ENV} disappeared during an LLM request")
    event = {
        **call.identity,
        "event": "response_received",
        "call_id": call.call_id,
        "timestamp_utc": _utc_now(),
        "latency_seconds": round(time.monotonic() - call.started_monotonic, 6),
        "response_model": _optional_text(_field(response, "model")),
        "request_id": _optional_text(
            _field(response, "_request_id") or _field(response, "id")),
        **_usage_values(response),
    }
    _append_event(path, event)


def fail_call(call: CallHandle, error: BaseException) -> None:
    """Record an attempt whose token usage is unknown to the client."""
    if not call.enabled:
        return
    path = _usage_path()
    if path is None:
        raise LLMUsageError(f"{LEDGER_ENV} disappeared during an LLM request")
    event = {
        **call.identity,
        "event": "request_failed",
        "call_id": call.call_id,
        "timestamp_utc": _utc_now(),
        "latency_seconds": round(time.monotonic() - call.started_monotonic, 6),
        "error_type": type(error).__name__,
        "error": (_optional_text(error) or "")[:500],
        "usage_available": False,
        "usage_complete": False,
        "usage_consistent": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "cached_tokens": None,
        "reasoning_tokens": None,
    }
    _append_event(path, event)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r}")


def load_events(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        raise LLMUsageError(f"LLM usage ledger is missing: {path}")
    events: List[Dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            locked = False
            try:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
                    locked = True
                for line_number, raw in enumerate(handle, 1):
                    if not raw.strip():
                        continue
                    try:
                        value = json.loads(
                            raw, parse_constant=_reject_json_constant)
                    except (json.JSONDecodeError, ValueError,
                            RecursionError) as exc:
                        raise LLMUsageError(
                            f"invalid LLM usage ledger {path} at line "
                            f"{line_number}: {exc}") from exc
                    if not isinstance(value, dict):
                        raise LLMUsageError(
                            f"invalid LLM usage ledger {path} at line "
                            f"{line_number}: event is not an object")
                    events.append(value)
            finally:
                if locked:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except LLMUsageError:
        raise
    except (OSError, UnicodeError) as exc:
        raise LLMUsageError(f"invalid LLM usage ledger {path}: {exc}") from exc
    return events


def _calls(events: Iterable[Mapping[str, Any]],
           campaign_id: str) -> List[Dict[str, Any]]:
    calls: Dict[str, Dict[str, Any]] = {}
    for event_index, event in enumerate(events, 1):
        if not isinstance(event, Mapping):
            raise LLMUsageError(
                f"LLM usage event {event_index} is not an object")
        if event.get("schema_version") != SCHEMA_VERSION:
            raise LLMUsageError("LLM usage event schema version mismatch")
        if event.get("campaign_id") != campaign_id:
            raise LLMUsageError("LLM usage ledger spans multiple campaigns")
        call_id = str(event.get("call_id") or "")
        if not call_id:
            raise LLMUsageError("LLM usage event has no call_id")
        record = calls.setdefault(call_id, {
            "call_id": call_id,
            "started": None,
            "terminal": None,
        })
        kind = event.get("event")
        if kind == "request_started":
            if record["started"] is not None:
                raise LLMUsageError(f"duplicate request_started event: {call_id}")
            record["started"] = dict(event)
        elif kind in {"response_received", "request_failed"}:
            if record["terminal"] is not None:
                raise LLMUsageError(f"duplicate terminal LLM event: {call_id}")
            record["terminal"] = dict(event)
        else:
            raise LLMUsageError(f"unsupported LLM usage event type: {kind!r}")

    records = list(calls.values())
    for record in records:
        call_id = record["call_id"]
        started = record.get("started")
        if started is None:
            raise LLMUsageError(
                f"terminal LLM event has no request_started event: {call_id}")
        terminal = record.get("terminal")
        if terminal is None:
            continue
        for key in _IDENTITY_KEYS:
            if started.get(key) != terminal.get(key):
                raise LLMUsageError(
                    f"LLM call identity changed for {call_id}: {key}")
    return records


def _sum(records: Iterable[Mapping[str, Any]], field: str) -> int:
    return sum(value for value in (
        _optional_int(record.get(field)) for record in records
    ) if value is not None)


def _usage_counts_inconsistent(record: Mapping[str, Any]) -> bool:
    if record.get("usage_consistent") is False:
        return True
    prompt = _optional_int(record.get("prompt_tokens"))
    completion = _optional_int(record.get("completion_tokens"))
    total = _optional_int(record.get("total_tokens"))
    return (
        prompt is not None
        and completion is not None
        and total is not None
        and total != prompt + completion
    )


def _aggregate(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    responses = []
    failures = []
    for record in records:
        terminal = record.get("terminal") or {}
        if terminal.get("event") == "response_received":
            responses.append(terminal)
        elif terminal.get("event") == "request_failed":
            failures.append(record)
    pending = [record for record in records if record.get("terminal") is None]
    inconsistent = [record for record in responses
                    if _usage_counts_inconsistent(record)]
    trusted_responses = [record for record in responses
                         if not _usage_counts_inconsistent(record)]
    with_total = [record for record in trusted_responses
                  if _optional_int(record.get("total_tokens")) is not None]
    with_prompt = [record for record in trusted_responses
                   if _optional_int(record.get("prompt_tokens")) is not None]
    with_completion = [record for record in trusted_responses
                       if _optional_int(record.get("completion_tokens")) is not None]
    with_cached = [record for record in trusted_responses
                   if _optional_int(record.get("cached_tokens")) is not None]
    with_reasoning = [record for record in trusted_responses
                      if _optional_int(record.get("reasoning_tokens")) is not None]
    unknown = bool(failures or pending or inconsistent)
    total_complete = not unknown and len(with_total) == len(responses)
    prompt_complete = not unknown and len(with_prompt) == len(responses)
    completion_complete = not unknown and len(with_completion) == len(responses)
    cached_complete = not unknown and len(with_cached) == len(responses)
    reasoning_complete = not unknown and len(with_reasoning) == len(responses)
    known_prompt = _sum(trusted_responses, "prompt_tokens")
    known_completion = _sum(trusted_responses, "completion_tokens")
    known_total = _sum(trusted_responses, "total_tokens")
    known_cached = _sum(trusted_responses, "cached_tokens")
    known_reasoning = _sum(trusted_responses, "reasoning_tokens")
    return {
        "requests_started": len(records),
        "successful_calls": len(responses),
        "successful_with_usage": len(with_total),
        "successful_missing_usage": len(responses) - len(with_total),
        "successful_inconsistent_usage": len(inconsistent),
        "failed_unknown_usage": len(failures),
        "pending_calls": len(pending),
        "known_prompt_tokens": known_prompt,
        "known_completion_tokens": known_completion,
        "known_total_tokens": known_total,
        "known_cached_tokens": known_cached,
        "known_reasoning_tokens": known_reasoning,
        "prompt_tokens": known_prompt if prompt_complete else None,
        "completion_tokens": known_completion if completion_complete else None,
        "total_tokens": known_total if total_complete else None,
        "cached_tokens": known_cached if cached_complete else None,
        "reasoning_tokens": known_reasoning if reasoning_complete else None,
        "usage_complete": total_complete,
        "cached_breakdown_complete": cached_complete,
        "reasoning_breakdown_complete": reasoning_complete,
    }


def _group(records: List[Dict[str, Any]], field: str) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        identity = record.get("terminal") or record.get("started") or {}
        key = str(identity.get(field) if identity.get(field) is not None else "unknown")
        grouped.setdefault(key, []).append(record)
    return [{field: key, **_aggregate(grouped[key])} for key in sorted(grouped)]


def build_summary(events: Iterable[Mapping[str, Any]], *, campaign_id: str,
                  llm_enabled: bool, status: str,
                  iteration: Optional[int] = None,
                  exit_code: Optional[int] = None,
                  completed_iterations: Optional[int] = None) -> Dict[str, Any]:
    campaign_id = str(campaign_id).strip()
    if not campaign_id:
        raise LLMUsageError("campaign_id must not be empty")
    if not isinstance(llm_enabled, bool):
        raise LLMUsageError("llm_enabled must be a boolean")
    all_records = _calls(events, campaign_id)
    if not llm_enabled and all_records:
        raise LLMUsageError(
            "No-LLM campaign recorded external LLM requests; hard gate violated")
    records = all_records
    if iteration is not None:
        records = [
            record for record in all_records
            if _optional_int(record["started"].get("iteration")) == iteration
        ]
    aggregate = _aggregate(records)
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "generated_utc": _utc_now(),
        "status": status,
        "llm_enabled": bool(llm_enabled),
        "iteration": iteration,
        "exit_code": exit_code,
        "completed_iterations": completed_iterations,
        **aggregate,
        "by_agent": _group(records, "agent"),
        "by_stage": _group(records, "stage"),
        "by_operation": _group(records, "operation"),
        "by_model": _group(records, "requested_model"),
    }


def _read_manifest(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LLMUsageError(f"cannot read campaign manifest {path}: {exc}") from exc
    if not isinstance(value, dict) or not str(value.get("campaign_id") or "").strip():
        raise LLMUsageError(f"campaign manifest has no campaign_id: {path}")
    if not isinstance(value.get("llm_enabled"), bool):
        raise LLMUsageError(f"campaign manifest has no boolean llm_enabled: {path}")
    return value


def _atomic_json(path: Path, payload: Mapping[str, Any], *, replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise LLMUsageError(f"refusing to overwrite LLM usage artifact: {path}")
    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(temporary_fd, "w", encoding="utf-8") as handle:
            temporary_fd = -1
            json.dump(
                dict(payload), handle, indent=2, sort_keys=True,
                allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except (OSError, TypeError, ValueError) as exc:
        raise LLMUsageError(
            f"cannot write LLM usage artifact {path}: {exc}") from exc
    finally:
        if temporary_fd >= 0:
            os.close(temporary_fd)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def initialize(manifest_path: Path, ledger_path: Path,
               summary_path: Path) -> str:
    manifest = _read_manifest(manifest_path)
    campaign_id = str(manifest["campaign_id"])
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with ledger_path.open("x", encoding="utf-8"):
            pass
    except FileExistsError as exc:
        raise LLMUsageError(
            f"refusing to reuse existing LLM usage ledger: {ledger_path}") from exc
    try:
        summary = build_summary(
            [], campaign_id=campaign_id,
            llm_enabled=manifest["llm_enabled"], status="running")
        _atomic_json(summary_path, summary, replace=False)
    except Exception:
        ledger_path.unlink(missing_ok=True)
        raise
    return campaign_id


def snapshot(manifest_path: Path, ledger_path: Path, summary_path: Path,
             output_path: Path, iteration: int) -> Dict[str, Any]:
    manifest = _read_manifest(manifest_path)
    campaign_id = str(manifest["campaign_id"])
    events = load_events(ledger_path)
    iteration_summary = build_summary(
        events, campaign_id=campaign_id,
        llm_enabled=manifest["llm_enabled"], status="iteration_complete",
        iteration=iteration,
    )
    _atomic_json(output_path, iteration_summary, replace=False)
    running = build_summary(
        events, campaign_id=campaign_id,
        llm_enabled=manifest["llm_enabled"], status="running",
        completed_iterations=iteration,
    )
    _atomic_json(summary_path, running, replace=True)
    return iteration_summary


def finalize(manifest_path: Path, ledger_path: Path, summary_path: Path, *,
             status: str, exit_code: int,
             completed_iterations: int) -> Dict[str, Any]:
    manifest = _read_manifest(manifest_path)
    campaign_id = str(manifest["campaign_id"])
    summary = build_summary(
        load_events(ledger_path), campaign_id=campaign_id,
        llm_enabled=manifest["llm_enabled"], status=status,
        exit_code=exit_code, completed_iterations=completed_iterations,
    )
    _atomic_json(summary_path, summary, replace=True)
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DRP campaign LLM usage accounting")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "snapshot", "finalize"):
        sub = commands.add_parser(name)
        sub.add_argument("--manifest", type=Path, required=True)
        sub.add_argument("--ledger", type=Path, required=True)
        sub.add_argument("--summary", type=Path, required=True)
        if name == "snapshot":
            sub.add_argument("--output", type=Path, required=True)
            sub.add_argument("--iteration", type=int, required=True)
        elif name == "finalize":
            sub.add_argument(
                "--status",
                choices=["completed", "early_stop", "failed", "interrupted",
                         "recovered_abandoned"],
                required=True,
            )
            sub.add_argument("--exit-code", type=int, required=True)
            sub.add_argument("--completed-iterations", type=int, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "init":
        print(initialize(args.manifest, args.ledger, args.summary))
    elif args.command == "snapshot":
        result = snapshot(
            args.manifest, args.ledger, args.summary,
            args.output, args.iteration)
        print(
            f"[LLM usage] iteration {args.iteration}: "
            f"requests={result['requests_started']}, "
            f"successful={result['successful_calls']}, "
            f"known_total={result['known_total_tokens']}, "
            f"exact={result['usage_complete']}")
    else:
        result = finalize(
            args.manifest, args.ledger, args.summary,
            status=args.status, exit_code=args.exit_code,
            completed_iterations=args.completed_iterations)
        total = result["total_tokens"]
        total_label = str(total) if total is not None else (
            f"at least {result['known_total_tokens']} (unknown requests present)")
        print(
            f"[LLM usage] campaign status={result['status']}, "
            f"requests={result['requests_started']}, "
            f"successful={result['successful_calls']}, "
            f"total_tokens={total_label}, "
            f"known_prompt={result['known_prompt_tokens']}, "
            f"known_completion={result['known_completion_tokens']}, "
            f"known_cached={result['known_cached_tokens']}, "
            f"known_reasoning={result['known_reasoning_tokens']}, "
            f"exact={result['usage_complete']}")


if __name__ == "__main__":
    main()
