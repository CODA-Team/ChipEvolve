"""Shared data structures and small helpers for Teacher/Student rounds."""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any


AGENT_ROOT = Path(__file__).resolve().parents[2]
PROMPT_TEMPLATE_DIR = AGENT_ROOT / "prompt_templates" / "teacher_loop"

START_KINDS = ("framework", "diamond", "prepared")

CANONICAL_LINES = (
    "openroad_dpl_flow",
    "evolve_default",
)

@dataclass(frozen=True)
class MetricSummary:
    tag: str
    metrics_path: Path
    mode: str
    line: str
    run_tag: str
    hpwl_after: float | None
    hpwl_delta: float | None
    runtime_seconds: float | None
    avg_disp: float | None
    max_disp: float | None
    violations: str
    hpwl_delta_percent: float | None = None
    hpwl_global: float | None = None
    hpwl_legalized: float | None = None
    hpwl_after_improve: float | None = None
    hpwl_stage_delta_legalization: float | None = None
    hpwl_stage_delta_improve: float | None = None
    hpwl_stage_delta_final: float | None = None
    hpwl_stage_delta_legalization_percent: float | None = None
    hpwl_stage_delta_improve_percent: float | None = None
    hpwl_stage_delta_final_percent: float | None = None


@dataclass(frozen=True)
class CandidateArtifacts:
    iter_part: str
    iter_number: int | None
    student_id: str
    route_label: str
    operation_id: str
    operation_dir: Path
    last_message: Path
    source_backup: Path
    implementation_diff: Path
    knowledge_card: Path


@dataclass(frozen=True)
class ChildRound:
    student_id: str
    route_label: str
    operation_id: str
    run_tag: str
    prompt_path: Path
    workspace_packet: Path
    operation_dir: Path
    last_message: Path
    usage_summary: Path
    stderr_log: Path
    events_jsonl: Path
    student_workspace: Path
    variant_root: Path
    dpl_src: Path
    private_binary: Path
    implementation_diff: Path
    knowledge_card: Path
    source_backup: Path
    session_state: Path
    session_env_file: Path
    elite_seed_source: Path | None = None


@dataclass(frozen=True)
class StudentWorkspace:
    student_workspace: Path
    variant_root: Path
    dpl_src: Path
    variant_env: Path
    private_binary: Path
    artifact_dir: Path
    implementation_diff: Path
    knowledge_card: Path
    source_backup: Path
    session_state: Path
    session_env_file: Path


@dataclass(frozen=True)
class WorkerSession:
    identity: str
    workspace: Path
    session_state: Path
    session_env_file: Path


def render_prompt_template(name: str, **values: Any) -> str:
    path = PROMPT_TEMPLATE_DIR / name
    text = path.read_text(encoding="utf-8")
    mapping = {key: str(value) for key, value in values.items()}
    return Template(text).safe_substitute(mapping)


def default_round_id(case_id: str) -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"teacher_{case_id}_{stamp}"


def iter_name(iteration: int) -> str:
    return f"iter_{iteration:02d}"


def student_workspace_paths(
    *,
    round_dir: Path,
    iteration: int,
    student_id: str,
    stable_workspace: bool = False,
) -> StudentWorkspace:
    student_root = round_dir / "students" / student_id
    if stable_workspace:
        student_workspace = student_root / "workspace"
        artifact_dir = student_root / iter_name(iteration) / "artifacts"
    else:
        student_workspace = student_root / iter_name(iteration)
        artifact_dir = student_workspace / "artifacts"
    variant_root = student_workspace / "variant"
    dpl_src = variant_root / "dpl_evolve"
    return StudentWorkspace(
        student_workspace=student_workspace,
        variant_root=variant_root,
        dpl_src=dpl_src,
        variant_env=variant_root / "variant_env.sh",
        private_binary=variant_root / "install" / "OpenROAD" / "bin" / "openroad",
        artifact_dir=artifact_dir,
        implementation_diff=artifact_dir / "implementation.diff",
        knowledge_card=artifact_dir / "knowledge_card.md",
        source_backup=student_root / "source_backups" / iter_name(iteration) / "dpl_evolve",
        session_state=student_workspace / ".codex_session_state.json",
        session_env_file=student_workspace / ".codex_identity.env",
    )


def teacher_session_paths(*, round_dir: Path, round_id: str) -> WorkerSession:
    workspace = round_dir / "teacher_workspace"
    return WorkerSession(
        identity=f"{round_id}:teacher",
        workspace=workspace,
        session_state=workspace / ".codex_session_state.json",
        session_env_file=workspace / ".codex_identity.env",
    )


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


class RoundLogger:
    def __init__(self, round_dir: Path) -> None:
        self.round_dir = round_dir
        self.round_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = round_dir / "round.log"
        self.events_path = round_dir / "events.jsonl"

    def event(self, stage: str, message: str, **fields: Any) -> None:
        timestamp = dt.datetime.now().isoformat(timespec="seconds")
        field_text = " ".join(
            f"{key}={json_safe(value)}" for key, value in fields.items()
        )
        line = f"[{timestamp}] [{stage}] {message}"
        if field_text:
            line = f"{line} {field_text}"
        print(
            f"[optimize_case] {stage}: {message}"
            + (f" {field_text}" if field_text else "")
        )
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "time": timestamp,
                        "stage": stage,
                        "message": message,
                        "fields": json_safe(fields),
                    },
                    sort_keys=True,
                )
                + "\n"
            )
