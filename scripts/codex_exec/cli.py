from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path


def default_operation_id() -> str:
    return f"codex_exec_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one non-interactive Codex operation and record artifacts."
    )
    parser.add_argument("--operation-id", default=default_operation_id())
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--profile")
    parser.add_argument("--sandbox", default="workspace-write")
    parser.add_argument("--skip-git-repo-check", action="store_true")
    parser.add_argument("--color", default="never")
    parser.add_argument(
        "--cwd",
        type=Path,
        help=(
            "Working directory passed to `codex exec -C` and to the wrapper "
            "process. Defaults to the ORFS root."
        ),
    )
    parser.add_argument("--config", action="append", default=[])
    parser.add_argument("--add-dir", action="append", default=[])
    parser.add_argument(
        "--resume-session-id",
        help="Resume an existing Codex exec session/thread instead of starting new.",
    )
    parser.add_argument(
        "--resume-last",
        action="store_true",
        help="Resume the most recent Codex exec session. Mostly for manual debugging.",
    )
    parser.add_argument("--input-price-per-1m", type=float)
    parser.add_argument("--cached-input-price-per-1m", type=float)
    parser.add_argument("--output-price-per-1m", type=float)
    return parser.parse_args(argv)
