#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_operation_id() -> str:
    return f"codex_exec_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"


def load_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file is not None:
        return args.prompt_file.read_text(encoding="utf-8")
    if args.prompt is not None:
        return args.prompt
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Provide --prompt, --prompt-file, or pipe prompt text on stdin.")


def ensure_operation_dir(root: Path, operation_id: str) -> Path:
    op_dir = root / "evolve_agent" / "checkpoints" / "operations" / operation_id
    if op_dir.exists():
        raise SystemExit(
            f"Operation directory already exists for '{operation_id}': {op_dir}\n"
            "Use a fresh operation id to avoid mixing old and new Codex artifacts."
        )
    op_dir.mkdir(parents=True, exist_ok=False)
    return op_dir


def maybe_cost_estimate(
    *,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    input_price_per_1m: float | None,
    cached_input_price_per_1m: float | None,
    output_price_per_1m: float | None,
) -> dict[str, Any] | None:
    if (
        input_price_per_1m is None
        or cached_input_price_per_1m is None
        or output_price_per_1m is None
    ):
        return None

    fresh_input_tokens = max(0, input_tokens - cached_input_tokens)
    estimated_cost_usd = (
        (fresh_input_tokens / 1_000_000.0) * input_price_per_1m
        + (cached_input_tokens / 1_000_000.0) * cached_input_price_per_1m
        + (output_tokens / 1_000_000.0) * output_price_per_1m
    )
    return {
        "fresh_input_tokens": fresh_input_tokens,
        "input_price_per_1m": input_price_per_1m,
        "cached_input_price_per_1m": cached_input_price_per_1m,
        "output_price_per_1m": output_price_per_1m,
        "estimated_cost_usd": estimated_cost_usd,
    }


def build_command(args: argparse.Namespace, root: Path, last_message_path: Path) -> list[str]:
    cmd = [
        "codex",
        "exec",
        "--json",
        "-C",
        str(root),
        "-o",
        str(last_message_path),
    ]

    if args.model:
        cmd.extend(["--model", args.model])
    if args.profile:
        cmd.extend(["--profile", args.profile])
    if args.sandbox:
        cmd.extend(["--sandbox", args.sandbox])
    if args.skip_git_repo_check:
        cmd.append("--skip-git-repo-check")
    if args.color:
        cmd.extend(["--color", args.color])
    for cfg in args.config:
        cmd.extend(["-c", cfg])
    for directory in args.add_dir:
        cmd.extend(["--add-dir", directory])

    cmd.append("-")
    return cmd


def summarize_events(events_path: Path) -> dict[str, Any]:
    usage_totals = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
    }
    thread_id = None
    turn_count = 0
    agent_message_count = 0
    last_agent_message = None

    with events_path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if event.get("type") == "thread.started":
                thread_id = event.get("thread_id", thread_id)

            if event.get("type") == "turn.completed":
                turn_count += 1
                usage = event.get("usage", {})
                usage_totals["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
                usage_totals["cached_input_tokens"] += int(
                    usage.get("cached_input_tokens", 0) or 0
                )
                usage_totals["output_tokens"] += int(usage.get("output_tokens", 0) or 0)

            if event.get("type") == "item.completed":
                item = event.get("item", {})
                if item.get("type") == "agent_message":
                    agent_message_count += 1
                    last_agent_message = item.get("text", last_agent_message)

    return {
        "thread_id": thread_id,
        "turn_count": turn_count,
        "agent_message_count": agent_message_count,
        "last_agent_message": last_agent_message,
        "usage": usage_totals,
    }


def write_readme(
    readme_path: Path,
    *,
    operation_id: str,
    command: list[str],
    prompt_path: Path,
    events_path: Path,
    stderr_path: Path,
    last_message_path: Path,
    summary: dict[str, Any],
) -> None:
    usage = summary["usage"]
    lines = [
        f"# {operation_id}",
        "",
        "Codex non-interactive invocation record.",
        "",
        f"- thread_id: {summary.get('thread_id')}",
        f"- turns: {summary.get('turn_count')}",
        f"- agent_messages: {summary.get('agent_message_count')}",
        f"- input_tokens: {usage['input_tokens']}",
        f"- cached_input_tokens: {usage['cached_input_tokens']}",
        f"- output_tokens: {usage['output_tokens']}",
        "",
        "## Files",
        f"- prompt: `{prompt_path}`",
        f"- events: `{events_path}`",
        f"- stderr: `{stderr_path}`",
        f"- last_message: `{last_message_path}`",
        "",
        "## Command",
        "```bash",
        " ".join(subprocess.list2cmdline([part]) for part in command),
        "```",
    ]
    readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--operation-id", default=default_operation_id())
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file", type=Path)
    ap.add_argument("--model")
    ap.add_argument("--profile")
    ap.add_argument("--sandbox", default="workspace-write")
    ap.add_argument("--skip-git-repo-check", action="store_true")
    ap.add_argument("--color", default="never")
    ap.add_argument("--config", action="append", default=[])
    ap.add_argument("--add-dir", action="append", default=[])
    ap.add_argument("--input-price-per-1m", type=float)
    ap.add_argument("--cached-input-price-per-1m", type=float)
    ap.add_argument("--output-price-per-1m", type=float)
    args = ap.parse_args()

    root = repo_root()
    op_dir = ensure_operation_dir(root, args.operation_id)
    prompt_text = load_prompt(args)

    prompt_path = op_dir / "codex_prompt.md"
    events_path = op_dir / "codex_events.jsonl"
    stderr_path = op_dir / "codex_stderr.log"
    last_message_path = op_dir / "codex_last_message.txt"
    summary_path = op_dir / "codex_usage_summary.json"
    invocation_path = op_dir / "codex_invocation.json"
    readme_path = op_dir / "README.md"

    prompt_path.write_text(prompt_text, encoding="utf-8")
    command = build_command(args, root, last_message_path)

    started_at = dt.datetime.now().isoformat()
    start_time = time.perf_counter()

    invocation = {
        "operation_id": args.operation_id,
        "repo_root": str(root),
        "command": command,
        "model": args.model,
        "profile": args.profile,
        "sandbox": args.sandbox,
        "skip_git_repo_check": args.skip_git_repo_check,
        "config": args.config,
        "add_dir": args.add_dir,
        "started_at": started_at,
    }
    invocation_path.write_text(json.dumps(invocation, indent=2) + "\n", encoding="utf-8")

    with events_path.open("w", encoding="utf-8") as events_fh, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_fh:
        proc = subprocess.Popen(
            command,
            cwd=str(root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_fh,
            text=True,
            encoding="utf-8",
        )
        assert proc.stdin is not None
        assert proc.stdout is not None
        proc.stdin.write(prompt_text)
        proc.stdin.close()

        for line in proc.stdout:
            events_fh.write(line)
            events_fh.flush()

        returncode = proc.wait()

    finished_at = dt.datetime.now().isoformat()
    elapsed_seconds = time.perf_counter() - start_time

    summary = summarize_events(events_path)
    usage = summary["usage"]
    summary["operation_id"] = args.operation_id
    summary["returncode"] = returncode
    summary["started_at"] = started_at
    summary["finished_at"] = finished_at
    summary["elapsed_seconds"] = round(elapsed_seconds, 3)
    summary["paths"] = {
        "prompt": str(prompt_path),
        "events": str(events_path),
        "stderr": str(stderr_path),
        "last_message": str(last_message_path),
        "invocation": str(invocation_path),
    }
    summary["cost_estimate"] = maybe_cost_estimate(
        input_tokens=usage["input_tokens"],
        cached_input_tokens=usage["cached_input_tokens"],
        output_tokens=usage["output_tokens"],
        input_price_per_1m=args.input_price_per_1m,
        cached_input_price_per_1m=args.cached_input_price_per_1m,
        output_price_per_1m=args.output_price_per_1m,
    )
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    write_readme(
        readme_path,
        operation_id=args.operation_id,
        command=command,
        prompt_path=prompt_path,
        events_path=events_path,
        stderr_path=stderr_path,
        last_message_path=last_message_path,
        summary=summary,
    )

    print(json.dumps(summary, indent=2))
    raise SystemExit(returncode)


if __name__ == "__main__":
    main()
