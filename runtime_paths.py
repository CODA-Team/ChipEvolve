from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def _is_orfs_root(path: Path) -> bool:
    return (path / "flow").is_dir() and (path / "tools" / "OpenROAD").is_dir()


def _default_mount_root(agent_root: Path) -> Path:
    return agent_root / ".mounted_orfs"


def resolve_agent_root(anchor_file: str | Path, *, levels_up: int) -> Path:
    env_root = os.environ.get("DPL_EVOLVE_AGENT_ROOT")
    if env_root:
        candidate = Path(env_root).resolve()
        if candidate.is_dir():
            return candidate
        raise SystemExit(
            f"DPL_EVOLVE_AGENT_ROOT does not exist or is not a directory: {candidate}"
        )
    return Path(anchor_file).resolve().parents[levels_up]


def resolve_orfs_root(
    *,
    agent_root: Path,
    script_name: str,
) -> Path:
    env_root = os.environ.get("ORFS_ROOT")
    if env_root:
        candidate = Path(env_root).resolve()
        if _is_orfs_root(candidate):
            return candidate
        raise SystemExit(
            f"{script_name} expected ORFS_ROOT to point at an ORFS workspace, got: {candidate}"
        )

    mounted_local = _default_mount_root(agent_root)
    if _is_orfs_root(mounted_local):
        return mounted_local

    raise SystemExit(
        f"{script_name} could not locate an ORFS workspace.\n"
        "Set ORFS_ROOT to a workspace containing flow/ and tools/OpenROAD/.\n"
        "Or attach one under $DPL_EVOLVE_AGENT_ROOT/.mounted_orfs."
    )


def resolve_state_root(*, orfs_root: Path, agent_root: Path) -> Path:
    env_root = os.environ.get("DPL_EVOLVE_STATE_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return (orfs_root / ".dpl_evolve_state").resolve()


def candidate_python_interpreters(
    *,
    extra_env_var: str = "DPL_EVOLVE_PYTHON_CANDIDATES",
) -> Iterable[str]:
    """Return user-configured Python candidates followed by portable defaults."""

    seen: set[str] = set()
    env_value = os.environ.get(extra_env_var, "")
    for raw in env_value.split(os.pathsep):
        candidate = raw.strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            yield candidate
    for candidate in ("python3", "python"):
        if candidate not in seen:
            seen.add(candidate)
            yield candidate


def reexec_with_module(module_name: str, script_file: str | Path, argv: list[str]) -> None:
    """Re-exec with a configured Python that can import module_name, if any."""

    for candidate in candidate_python_interpreters():
        resolved = shutil.which(candidate)
        if not resolved or resolved == sys.executable:
            continue
        probe = subprocess.run(
            [resolved, "-c", f"import {module_name}"],
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            os.execv(resolved, [resolved, str(script_file), *argv[1:]])


def resolve_input_path(
    value: str | Path,
    *,
    cwd: Path | None,
    agent_root: Path,
    orfs_root: Path,
) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(str(value))))
    if path.is_absolute():
        return path.resolve()

    if cwd is not None:
        cwd_candidate = (cwd / path).resolve()
        if cwd_candidate.exists():
            return cwd_candidate

    if path.parts and path.parts[0] in {"evolve_agent", "dpl_evolve_agent"}:
        return (agent_root / Path(*path.parts[1:])).resolve()

    if path.parts and path.parts[0] in {"flow", "tools"}:
        return (orfs_root / path).resolve()

    agent_candidate = (agent_root / path).resolve()
    if agent_candidate.exists():
        return agent_candidate

    return (cwd / path).resolve() if cwd is not None else path.resolve()


@dataclass(frozen=True)
class RuntimePaths:
    orfs_root: Path
    agent_root: Path
    state_root: Path

    @property
    def packet_dir(self) -> Path:
        return self.state_root / "packets"

    @property
    def checkpoints_dir(self) -> Path:
        return self.state_root / "checkpoints"

    @property
    def operations_dir(self) -> Path:
        return self.checkpoints_dir / "operations"


def resolve_runtime_paths(
    *,
    anchor_file: str | Path,
    agent_root_levels_up: int,
    script_name: str,
    cwd: Path | None = None,
) -> RuntimePaths:
    agent_root = resolve_agent_root(anchor_file, levels_up=agent_root_levels_up)
    orfs_root = resolve_orfs_root(
        agent_root=agent_root,
        script_name=script_name,
    )
    state_root = resolve_state_root(orfs_root=orfs_root, agent_root=agent_root)
    return RuntimePaths(orfs_root=orfs_root, agent_root=agent_root, state_root=state_root)
