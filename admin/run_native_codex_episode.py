"""Record one native Codex invocation; business scoring stays outside this runner."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from chip_evolve.config import read, write
from chip_evolve.jobs import digest
from chip_evolve.native_process import stop


def summarize(events: Path) -> dict[str, Any]:
    """Retain known usage separately from an interrupted or malformed trace."""
    started, completed, commands, problems, usage = 0, 0, [], [], []
    for number, line in enumerate(events.read_text().splitlines(), 1):
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise TypeError("event is not an object")
        except (ValueError, TypeError) as error:
            problems.append({"line": number, "error": str(error)})
            continue
        kind = event.get("type")
        if kind == "turn.started":
            started += 1
        elif kind == "turn.completed":
            completed += 1
            row = event.get("usage", {})
            keys = ("input_tokens", "cached_input_tokens", "output_tokens")
            if (
                isinstance(row, dict)
                and all(type(row.get(k)) is int and row[k] >= 0 for k in keys)
                and row["cached_input_tokens"] <= row["input_tokens"]
            ):
                usage.append(row)
            else:
                problems.append({"line": number, "error": "missing/invalid usage"})
        elif kind in {"error", "turn.failed"}:
            problems.append({"line": number, "event": event})
        if kind == "item.completed" and event.get("item", {}).get("type") == (
            "command_execution"
        ):
            commands.append(event["item"])
    complete = started > 0 and started == completed == len(usage) and not problems
    known = {
        key: sum(row[key] for row in usage)
        for key in ("input_tokens", "cached_input_tokens", "output_tokens")
    }
    return {
        "turns_started": started,
        "turns_completed": completed,
        "usage_complete": complete,
        "usage": known if complete else None,
        "known_usage_lower_bound": known,
        "usage_receipts": usage,
        "commands": commands,
        "trace_problems": problems,
        "cache_is_input_subset": True,
        "input_plus_output_tokens": (
            known["input_tokens"] + known["output_tokens"] if complete else None
        ),
    }


def changed(files: dict[str, str]) -> list[str]:
    return [
        p for p, sha in files.items() if not Path(p).is_file() or digest(Path(p)) != sha
    ]


def run(spec_path: Path, output: Path) -> dict[str, Any]:
    started = time.monotonic()
    started_at = time.time()
    cpu_before = os.times()
    spec = read(spec_path)
    if spec["schema"] != "chip-evolve.native-codex-episode.v1":
        raise ValueError("Unknown native episode specification")
    files = spec["input_hashes"]
    if changed(files):
        raise ValueError("Pinned episode inputs changed: " + str(changed(files)))
    prefix = spec["native_command"]
    for name in [*prefix, spec["prompt"], spec["answer_schema"]]:
        if name not in files:
            raise ValueError("Native tool and prompt/schema must be pinned: " + name)
    if spec["wall_seconds"] <= 0:
        raise ValueError("Wall deadline must be positive")
    sandbox = spec.get("sandbox", "workspace-write")
    if sandbox not in {"workspace-write", "danger-full-access"}:
        raise ValueError("Unqualified native sandbox profile: " + str(sandbox))
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / "workspace"
    workspace.mkdir()
    command = [
        *prefix,
        "exec",
        "--ignore-user-config",
        "--ephemeral",
        "--skip-git-repo-check",
        "-C",
        str(workspace),
        "-s",
        sandbox,
        "-m",
        spec["model"],
        "-c",
        "model_reasoning_effort=" + json.dumps(spec["reasoning_effort"]),
        "-c",
        'approval_policy="never"',
        "-c",
        "sandbox_workspace_write.network_access=true",
        "--json",
        "--output-schema",
        spec["answer_schema"],
        "--output-last-message",
        str(workspace / "answer.json"),
    ]
    for name in spec.get("writable_directories", []):
        command += ["--add-dir", name]
    command.append("-")
    write(output / "specification.json", spec)
    write(output / "invocation.json", command)
    record: dict[str, Any] = {
        "status": "running",
        "started_at": started_at,
        "specification_sha256": digest(spec_path),
        "requested_model": spec["model"],
        "reasoning_effort": spec["reasoning_effort"],
        "server_model_snapshot": None,
        "wall_limit_seconds": spec["wall_seconds"],
        "sandbox": sandbox,
        "token_hard_limit_enforced": False,
        "business_correctness": "requires_independent_verification",
        "formal_episode": spec.get("formal_episode", False),
    }
    write(output / "receipt.json", record)
    interrupted = False
    try:
        with (
            (output / "events.jsonl").open("x") as events,
            (output / "stderr.txt").open("x") as errors,
        ):
            process = subprocess.Popen(
                command,
                cwd=workspace,
                env=dict(
                    os.environ,
                    NO_PROXY="127.0.0.1,localhost",
                    no_proxy="127.0.0.1,localhost",
                    PYTHONNOUSERSITE="1",
                ),
                stdin=subprocess.PIPE,
                stdout=events,
                stderr=errors,
                text=True,
                start_new_session=True,
            )
            record["pid"] = process.pid
            write(output / "receipt.json", record)
            try:
                process.communicate(
                    Path(spec["prompt"]).read_text(),
                    timeout=max(
                        0.001, spec["wall_seconds"] - (time.monotonic() - started)
                    ),
                )
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
                interrupted = isinstance(error, KeyboardInterrupt)
                record["cleanup"] = stop(process)
                record["status"] = "interrupted" if interrupted else "timed_out"
            finally:
                if process.stdin is not None:
                    process.stdin.close()
        trace = summarize(output / "events.jsonl")
        record.update(trace, exit_code=process.returncode)
        answer = workspace / "answer.json"
        if answer.exists():
            record["answer"] = read(answer)
            record["answer_sha256"] = digest(answer)
        alterations = changed(files)
        record["changed_inputs"] = alterations
        if record["status"] == "running":
            record["status"] = (
                "native_completed"
                if process.returncode == 0
                and trace["usage_complete"]
                and answer.exists()
                and not alterations
                else "failed"
            )
    except Exception as error:
        record.update(
            status="failed", error_type=type(error).__name__, error=str(error)
        )
        raise
    finally:
        record.update(ended_at=time.time(), wall_seconds=time.monotonic() - started)
        cpu_after = os.times()
        record["cpu_usage"] = {
            "runner_user_seconds": cpu_after.user - cpu_before.user,
            "runner_system_seconds": cpu_after.system - cpu_before.system,
            "native_and_waited_descendants_user_seconds": (
                cpu_after.children_user - cpu_before.children_user
            ),
            "native_and_waited_descendants_system_seconds": (
                cpu_after.children_system - cpu_before.children_system
            ),
            "scope": (
                "os.times deltas for this recorder and its reaped native tree; "
                "one episode per recorder process. Independent EF/DF services, "
                "remote model compute and unreaped/detached descendants are "
                "outside this observed scope, not zero-cost work."
            ),
        }
        write(output / "receipt.json", record)
    if interrupted:
        raise KeyboardInterrupt
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.spec, args.output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "receipt": str(args.output.resolve() / "receipt.json"),
                "business_correctness": result["business_correctness"],
                "usage_complete": result["usage_complete"],
                "usage": result["usage"],
                "wall_seconds": result["wall_seconds"],
                "cpu_usage": result["cpu_usage"],
            },
            ensure_ascii=False,
        )
    )
    raise SystemExit(0 if result["status"] == "native_completed" else 1)


if __name__ == "__main__":
    main()
