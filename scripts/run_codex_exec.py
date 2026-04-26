#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from runtime_paths import resolve_runtime_paths


def runtime_paths():
    return resolve_runtime_paths(
        anchor_file=__file__,
        agent_root_levels_up=1,
        script_name="run_codex_exec.py",
    )


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


def ensure_operation_dir(operations_dir: Path, operation_id: str) -> Path:
    op_dir = operations_dir / operation_id
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
    if args.resume_session_id or args.resume_last:
        # `codex exec resume` intentionally reuses the original session's cwd
        # and writable roots, so it does not accept the full `exec` option set.
        cmd = [
            "codex",
            "exec",
            "resume",
            "--json",
            "-o",
            str(last_message_path),
        ]
        if args.model:
            cmd.extend(["--model", args.model])
        if args.skip_git_repo_check:
            cmd.append("--skip-git-repo-check")
        for cfg in args.config:
            cmd.extend(["-c", cfg])
        if args.resume_last:
            cmd.append("--last")
        else:
            cmd.append(args.resume_session_id)
        cmd.append("-")
        return cmd

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


def prepare_codex_home(codex_home: Path) -> Path:
    """Prepare a local CODEX_HOME without copying credentials into state.

    Codex stores resumable sessions under CODEX_HOME.  For experiment rounds we
    want those sessions near the round artifacts, while still reusing the
    user's existing auth/config safely.  Symlinks keep secrets out of copied
    experiment artifacts and make the relationship explicit.
    """
    source_home = Path.home() / ".codex"
    codex_home.mkdir(parents=True, exist_ok=True)
    try:
        codex_home.chmod(0o700)
    except OSError:
        pass

    for name in [
        "auth.json",
        "config.toml",
        "AGENTS.md",
        "installation_id",
        "skills",
        "memories",
        "vendor_imports",
    ]:
        src = source_home / name
        dst = codex_home / name
        if not src.exists() or dst.exists() or dst.is_symlink():
            continue
        dst.symlink_to(src, target_is_directory=src.is_dir())

    for name in ["sessions", "cache", "tmp", "shell_snapshots"]:
        (codex_home / name).mkdir(parents=True, exist_ok=True)

    return codex_home


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
    ap.add_argument(
        "--codex-home",
        type=Path,
        help=(
            "Use this CODEX_HOME for the codex subprocess. The directory is "
            "prepared with symlinks to user auth/config and local sessions."
        ),
    )
    ap.add_argument("--config", action="append", default=[])
    ap.add_argument("--add-dir", action="append", default=[])
    ap.add_argument(
        "--resume-session-id",
        help="Resume an existing Codex exec session/thread instead of starting a new one.",
    )
    ap.add_argument(
        "--resume-last",
        action="store_true",
        help="Resume the most recent Codex exec session. Mostly for manual debugging.",
    )
    ap.add_argument("--input-price-per-1m", type=float)
    ap.add_argument("--cached-input-price-per-1m", type=float)
    ap.add_argument("--output-price-per-1m", type=float)
    args = ap.parse_args()

    runtime = runtime_paths()
    root = runtime.orfs_root
    op_dir = ensure_operation_dir(runtime.operations_dir, args.operation_id)
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
    codex_home = prepare_codex_home(args.codex_home) if args.codex_home else None

    started_at = dt.datetime.now().isoformat()
    start_time = time.perf_counter()

    invocation = {
        "operation_id": args.operation_id,
        "repo_root": str(root),
        "agent_root": str(runtime.agent_root),
        "state_root": str(runtime.state_root),
        "command": command,
        "model": args.model,
        "profile": args.profile,
        "sandbox": args.sandbox,
        "codex_home": str(codex_home) if codex_home else None,
        "resume_session_id": args.resume_session_id,
        "resume_last": args.resume_last,
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
            env={**os.environ, **({"CODEX_HOME": str(codex_home)} if codex_home else {})},
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
