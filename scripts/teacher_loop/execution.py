"""Codex operation execution, lineage, resume, and source snapshots."""
from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from runtime_paths import clean_subprocess_env
from scripts.teacher_loop.common import ChildRound, iter_name
from scripts.teacher_loop.evidence import load_json, seed_private_source_from_elite
from scripts.teacher_loop.prompts import focused_message_excerpt, read_text_excerpt


def operation_thread_id(runtime: Any, operation_id: str) -> str | None:
    summary = load_json(runtime.operations_dir / operation_id / "codex_usage_summary.json")
    if not summary:
        return None
    thread_id = summary.get("thread_id")
    return str(thread_id) if thread_id else None


def operation_safe_to_resume(runtime: Any, operation_id: str) -> tuple[bool, str]:
    summary_path = runtime.operations_dir / operation_id / "codex_usage_summary.json"
    summary = load_json(summary_path)
    if not summary:
        return False, "missing usage summary"
    if summary.get("returncode") != 0:
        return False, f"returncode={summary.get('returncode')}"
    if not summary.get("thread_id"):
        return False, "missing thread id"
    if int(summary.get("agent_message_count", 0) or 0) <= 0:
        return False, "no agent messages"
    if not str(summary.get("last_agent_message") or "").strip():
        return False, "empty last agent message"
    return True, "ok"


def operation_thread_id_if_cwd_matches(
    runtime: Any, operation_id: str, expected_cwd: Path
) -> str | None:
    invocation = load_json(runtime.operations_dir / operation_id / "codex_invocation.json")
    if not invocation:
        return None
    recorded_cwd = Path(
        invocation.get("codex_cwd") or invocation.get("repo_root") or ""
    )
    if recorded_cwd != expected_cwd:
        return None
    return operation_thread_id(runtime, operation_id)


def resumable_thread_id(
    *,
    runtime: Any,
    operation_id: str,
    expected_cwd: Path,
    allow_unsafe_resume: bool,
) -> str | None:
    safe, reason = operation_safe_to_resume(runtime, operation_id)
    if not safe and not allow_unsafe_resume:
        print(
            "[optimize_case] not resuming "
            f"{operation_id}: previous operation is unsafe ({reason})",
            file=sys.stderr,
        )
        return None
    thread_id = operation_thread_id_if_cwd_matches(runtime, operation_id, expected_cwd)
    if thread_id or not allow_unsafe_resume:
        return thread_id
    return operation_thread_id(runtime, operation_id)


def build_codex_exec_command(
    *,
    run_codex: Path,
    operation_id: str,
    prompt_path: Path,
    sandbox: str,
    add_dirs: list[Path],
    model: str | None,
    reasoning_effort: str | None,
    profile: str | None,
    resume_session_id: str | None = None,
    cwd: Path | None = None,
    skip_git_repo_check: bool = False,
) -> list[str]:
    cmd = [
        sys.executable,
        str(run_codex),
        "--operation-id",
        operation_id,
        "--prompt-file",
        str(prompt_path),
        "--sandbox",
        sandbox,
    ]
    for add_dir in add_dirs:
        cmd.extend(["--add-dir", str(add_dir)])
    if cwd is not None:
        cmd.extend(["--cwd", str(cwd)])
    if skip_git_repo_check:
        cmd.append("--skip-git-repo-check")
    if model:
        cmd.extend(["--model", model])
    if reasoning_effort:
        cmd.extend(["--config", f'model_reasoning_effort="{reasoning_effort}"'])
    if profile:
        cmd.extend(["--profile", profile])
    if resume_session_id:
        cmd.extend(["--resume-session-id", resume_session_id])
    return cmd


def append_lineage(
    *,
    round_dir: Path,
    student_id: str,
    strategy: str,
    iteration: int,
    operation_id: str,
    run_tag: str,
    prompt_path: Path,
) -> None:
    student_dir = round_dir / "students" / student_id
    student_dir.mkdir(parents=True, exist_ok=True)
    lineage_path = student_dir / "lineage.json"
    if lineage_path.exists():
        data = load_json(lineage_path) or {}
    else:
        data = {"student_id": student_id, "strategy": strategy, "iterations": []}
    data.setdefault("iterations", []).append(
        {
            "iteration": iter_name(iteration),
            "strategy": strategy,
            "operation_id": operation_id,
            "run_tag": run_tag,
            "prompt": str(prompt_path),
        }
    )
    lineage_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_commands(
    commands: list[list[str]],
    *,
    max_parallel: int,
    dry_run: bool,
) -> int:
    if dry_run:
        for command in commands:
            print(" ".join(shlex.quote(part) for part in command))
        return 0

    active: list[subprocess.Popen[Any]] = []
    failures = 0
    pending = list(commands)
    while pending or active:
        while pending and len(active) < max_parallel:
            command = pending.pop(0)
            print("[optimize_case] launch:", " ".join(shlex.quote(part) for part in command))
            active.append(subprocess.Popen(command, env=clean_subprocess_env()))
        next_active: list[subprocess.Popen[Any]] = []
        for proc in active:
            rc = proc.poll()
            if rc is None:
                next_active.append(proc)
            elif rc != 0:
                failures += 1
        active = next_active
        if active:
            time.sleep(2)
    return 1 if failures else 0


def backup_child_sources(child_rounds: list[ChildRound]) -> None:
    """Snapshot each child's current source after its iteration.

    The active workspace may be stable across iterations, so the immutable
    review anchor is this source backup plus the per-iteration diff artifact.
    """
    for child in child_rounds:
        if not child.dpl_src.exists():
            print(
                "[optimize_case] warning: cannot backup missing child source "
                f"for {child.student_id}: {child.dpl_src}",
                file=sys.stderr,
            )
            continue
        backup = child.source_backup
        if backup.exists():
            shutil.rmtree(backup)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            child.dpl_src,
            backup,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                "*.o",
                "*.a",
                "*.so",
                "CMakeFiles",
                "cmake_install.cmake",
            ),
        )
        print(f"[optimize_case] backed up {child.student_id} source: {backup}")


def teacher_insight_for_student(text: str, student_id: str, max_chars: int = 1800) -> str:
    """Return the global diagnosis plus one `### student_XX` section."""
    section_markers = ("## Insight Packets", "## Next Insight Packets")
    global_part = text
    for marker in section_markers:
        if marker in text:
            global_part = text.split(marker, 1)[0]
            break
    global_lines = [line.strip() for line in global_part.splitlines() if line.strip()]
    global_excerpt = "\n".join(global_lines[:4]).strip()

    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip().lower().startswith(f"### {student_id}".lower()):
            start = idx
            break
    if start is None:
        fallback = focused_message_excerpt(text, max_chars=max_chars)
        return fallback if len(fallback) <= max_chars else fallback[:max_chars].rstrip()

    end = len(lines)
    for idx in range(start + 1, len(lines)):
        stripped = lines[idx].strip()
        if stripped.startswith("### ") and stripped.lower().startswith("### student_"):
            end = idx
            break
    student_section = "\n".join(lines[start:end]).strip()
    parts = []
    if global_excerpt:
        if global_excerpt.lower().startswith("global diagnosis"):
            parts.extend([global_excerpt, ""])
        else:
            parts.extend(["Global diagnosis:", global_excerpt, ""])
    parts.append(student_section)
    result = "\n".join(parts).strip()
    if len(result) <= max_chars:
        return result
    return result[:max_chars].rstrip() + "\n[truncated]"


def inline_teacher_plan_for_children(
    *, child_rounds: list[ChildRound], teacher_last_message: Path
) -> None:
    """Append each child's assigned Teacher insight after Teacher finishes.

    Child prompt files are created before Teacher runs so commands can be
    assembled, but child workers are launched after Teacher.  Append only the
    relevant `### student_XX` section so children do not waste context on peer
    instructions they are not executing.
    """
    teacher_text = read_text_excerpt(teacher_last_message, max_chars=20000)
    marker = "## Current Teacher Insight Packet"
    for child in child_rounds:
        if not child.prompt_path.exists():
            continue
        assigned = teacher_insight_for_student(teacher_text, child.student_id)
        section = (
            f"\n\n{marker}\n\n"
            "This is your assigned Teacher insight. Execute it with your own "
            "implementation judgment; do not redo Teacher's global review.\n\n"
            f"{assigned}\n"
        )
        prompt_text = child.prompt_path.read_text(encoding="utf-8", errors="replace")
        if marker in prompt_text:
            prompt_text = prompt_text.split(marker, 1)[0].rstrip()
        child.prompt_path.write_text(prompt_text + section, encoding="utf-8")


def seed_elite_children(child_rounds: list[ChildRound]) -> None:
    for child in child_rounds:
        if child.elite_seed_source is None:
            continue
        seed_private_source_from_elite(
            seed_source=child.elite_seed_source,
            target_source=child.dpl_src,
        )
        print(
            "[optimize_case] seeded "
            f"{child.student_id} from elite: {child.elite_seed_source}"
        )
