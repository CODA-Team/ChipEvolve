from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
    mounted_parent = agent_root.parent
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


def resolve_input_path(
    value: str | Path,
    *,
    cwd: Path | None,
    agent_root: Path,
    orfs_root: Path,
) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()

    if cwd is not None:
        cwd_candidate = (cwd / path).resolve()
        if cwd_candidate.exists():
            return cwd_candidate

    if path.parts and path.parts[0] == "evolve_agent":
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
