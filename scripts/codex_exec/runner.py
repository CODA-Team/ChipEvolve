from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[2]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from runtime_paths import resolve_runtime_paths
from scripts.codex_exec.artifacts import (
    maybe_cost_estimate,
    summarize_events,
    summarize_stderr,
    write_readme,
)
from scripts.codex_exec.cli import parse_args


def runtime_paths() -> Any:
    return resolve_runtime_paths(
        anchor_file=__file__,
        agent_root_levels_up=2,
        script_name="run_codex_exec.py",
    )


def default_exec_root(runtime: Any) -> Path:
    return runtime.orfs_root


def load_prompt(args: Any) -> str:
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


def build_command(args: Any, root: Path, last_message_path: Path) -> list[str]:
    if args.resume_session_id or args.resume_last:
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runtime = runtime_paths()
    root = args.cwd.resolve() if args.cwd else default_exec_root(runtime)
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

    started_at = dt.datetime.now().isoformat()
    start_time = time.perf_counter()
    invocation = {
        "operation_id": args.operation_id,
        "repo_root": str(root),
        "codex_cwd": str(root),
        "agent_root": str(runtime.agent_root),
        "state_root": str(runtime.state_root),
        "command": command,
        "model": args.model,
        "profile": args.profile,
        "sandbox": args.sandbox,
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
            env=os.environ.copy(),
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
    summary["stderr_summary"] = summarize_stderr(stderr_path)
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
    return returncode
