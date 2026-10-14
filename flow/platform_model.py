"""Durable responses for replay of an interrupted native decision phase.

Only the platform backend opts in. Replays keep the original call identity and
provider usage; they are evidence, not another paid response in the usage ledger.
"""

import fcntl
import json
import os
import signal
import time
from pathlib import Path
from types import SimpleNamespace

from llm_usage import (
    CallHandle,
    LLMUsageError,
    _atomic_json,
    _calls,
    _identity,
    _stable_hash,
    _usage_values,
    begin_call,
    fail_call,
    finish_call,
    load_events,
)


def write_record(path, value):
    _atomic_json(path, value, replace=True)


def process_identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {
            "pid": pid,
            "start_ticks": fields[19],
            "process_group": int(fields[2]),
            "state": fields[0],
        }
    except FileNotFoundError:
        return None


def is_alive(saved):
    current = process_identity(saved["pid"]) if saved else None
    return (
        current is not None
        and current["state"] != "Z"
        and current["start_ticks"] == saved["start_ticks"]
    )


def _json_value(value):
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, SimpleNamespace):
        return _json_value(vars(value))
    return value


def _response(value):
    message = value["message"]
    calls = [
        SimpleNamespace(
            id=row["id"], type=row["type"], function=SimpleNamespace(**row["function"])
        )
        for row in message.get("tool_calls") or []
    ]
    return SimpleNamespace(
        id=value["id"],
        model=value["model"],
        usage=value["usage"],
        _request_id=value.get("_request_id"),
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=message["content"], tool_calls=calls)
            )
        ],
    )


def tracked_completion(client, payload, context=None):
    provider = str(getattr(client, "base_url", "") or "")
    if os.environ.get("DRP_EXECUTION_BACKEND", "native") != "platform":
        call = begin_call(
            model=payload["model"],
            context=context,
            request_payload=payload,
            provider=provider,
        )
        try:
            response = client.chat.completions.create(**payload)
        except Exception as error:
            fail_call(call, error)
            raise
        finish_call(call, response)
        return response

    if os.environ.get("EDA_PLATFORM_OBJECTIVE"):
        from eda_toolkits.objectives import objective_messages

        payload = objective_messages(payload)
    if os.environ.get("EDA_PLATFORM_CONTEXT"):
        from eda_toolkits.context import context_messages

        payload = context_messages(payload)
    ledger, identity = _identity(context, payload["model"], provider)
    if ledger is None:
        raise LLMUsageError("Platform decisions require the campaign usage ledger.")
    request_hash = _stable_hash(payload)
    key = _stable_hash(
        {
            **{k: v for k, v in identity.items() if k != "pid"},
            "request_sha256": request_hash,
        }
    )
    if key is None:
        raise LLMUsageError("Cannot hash the platform decision request.")
    settings = json.loads(Path(os.environ["DRP_PLATFORM_CONFIG"]).read_text())
    root = Path(settings["state_root"]) / "model-responses"
    root.mkdir(parents=True, exist_ok=True)
    path = root / (key + ".json")
    with path.with_suffix(".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise LLMUsageError(
                "The same decision still has an active publisher."
            ) from error
        record = json.loads(path.read_text()) if path.exists() else None
        if record is None:
            # Cover a crash after begin_call fsync but before its cache record.
            matching = [
                row
                for row in _calls(load_events(ledger), identity["campaign_id"])
                if row["started"].get("request_sha256") == request_hash
                and all(
                    row["started"].get(k) == v
                    for k, v in identity.items()
                    if k != "pid"
                )
            ]
            if matching:
                row = matching[-1]
                if row["terminal"] and row["terminal"]["event"] == "response_received":
                    raise LLMUsageError(
                        "A completed decision has no durable response; refusing a paid duplicate."
                    )
                if is_alive(row["started"].get("process_identity")):
                    raise LLMUsageError(
                        "An earlier decision publisher is still running."
                    )
                call = CallHandle(
                    row["call_id"],
                    True,
                    time.monotonic(),
                    {k: row["started"][k] for k in identity},
                )
                if row["terminal"] is None:
                    fail_call(
                        call,
                        RuntimeError(
                            "Interrupted before a durable response; provider usage unknown."
                        ),
                    )
                raise RuntimeError(
                    "The interrupted decision has unknown usage; native fallback is retained."
                )
            call = begin_call(
                model=payload["model"],
                context=context,
                request_payload=payload,
                provider=provider,
            )
            record = {
                "key": key,
                "request_sha256": request_hash,
                "call_id": call.call_id,
                "identity": call.identity,
                "started_monotonic": call.started_monotonic,
                "publisher": process_identity(os.getpid()),
                "status": "pending",
            }
            write_record(path, record)
        else:
            call = CallHandle(
                record["call_id"], True, record["started_monotonic"], record["identity"]
            )
            if record["status"] == "pending":
                if is_alive(record["publisher"]):
                    raise LLMUsageError(
                        "An earlier decision publisher is still running."
                    )
                worker_path = path.with_suffix(".worker.json")
                worker = (
                    json.loads(worker_path.read_text())
                    if worker_path.exists()
                    else None
                )
                if worker is not None and is_alive(worker):
                    if worker["process_group"] != worker["pid"]:
                        raise LLMUsageError(
                            "Saved model worker has an unexpected process group."
                        )
                    os.killpg(worker["pid"], signal.SIGKILL)
                record.update(
                    status="failed",
                    error="Interrupted before a durable response; provider usage unknown.",
                )
                write_record(path, record)
            calls = _calls(load_events(ledger), identity["campaign_id"])
            original = next(
                (row for row in calls if row["call_id"] == call.call_id), None
            )
            if (
                original is None
                or original["started"]["request_sha256"] != request_hash
                or any(
                    original["started"].get(name) != value
                    for name, value in call.identity.items()
                )
            ):
                raise LLMUsageError(
                    "Cached decision differs from its original ledger identity."
                )
            terminals = [] if original["terminal"] is None else [original["terminal"]]
            if record["status"] == "received":
                if _stable_hash(record["response"]) != record["response_sha256"]:
                    raise LLMUsageError("Durable model response hash changed.")
                response = _response(record["response"])
                if not terminals:
                    finish_call(call, response)
                elif terminals[0]["event"] != "response_received":
                    raise LLMUsageError(
                        "Cached response conflicts with its usage ledger."
                    )
                elif any(
                    terminals[0].get(name) != value
                    for name, value in _usage_values(response).items()
                ):
                    raise LLMUsageError(
                        "Cached decision usage differs from the provider ledger."
                    )
                replay = root / "replays.jsonl"
                with replay.open("a") as stream:
                    stream.write(
                        json.dumps(
                            {
                                "key": key,
                                "call_id": call.call_id,
                                "response_sha256": record["response_sha256"],
                                "pid": os.getpid(),
                                "time": time.time(),
                            }
                        )
                        + "\n"
                    )
                    stream.flush()
                    os.fsync(stream.fileno())
                return response
            if record["status"] == "failed":
                if not terminals:
                    fail_call(call, RuntimeError(record["error"]))
                raise RuntimeError(record["error"])

        # Codex records its separate session so SIGKILL cannot hide a live worker.
        client.platform_worker_record = path.with_suffix(".worker.json")
        try:
            response = client.chat.completions.create(**payload)
        except Exception as error:
            record.update(status="failed", error=str(error)[:500])
            write_record(path, record)
            fail_call(call, error)
            raise
        finally:
            client.platform_worker_record = None
        record.update(
            status="received",
            response={
                "id": getattr(response, "id", None),
                "model": getattr(response, "model", None),
                "_request_id": getattr(response, "_request_id", None),
                "usage": _json_value(response.usage),
                "message": _json_value(response.choices[0].message),
            },
        )
        record["response_sha256"] = _stable_hash(record["response"])
        write_record(path, record)
        finish_call(call, response)
        gate = os.environ.get("DRP_ACCEPTANCE_MODEL_GATE")
        if (
            gate
            == f"{identity['iteration']}:{identity['stage']}:{identity['operation']}"
        ):
            write_record(
                Path(settings["state_root"]) / "model-acceptance-gate.json",
                {
                    "call_id": call.call_id,
                    "key": key,
                    "response_sha256": record["response_sha256"],
                    "pid": os.getpid(),
                },
            )
            while not (
                Path(settings["state_root"]) / "release-model-acceptance-gate"
            ).exists():
                time.sleep(0.2)
        return response
