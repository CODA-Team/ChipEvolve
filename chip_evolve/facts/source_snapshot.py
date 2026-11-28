"""Freeze source bytes and the explicit environment of a native controller."""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
from pathlib import Path

from chip_evolve.core.jobs import digest


def freeze(
    source: Path,
    destination: Path,
    *,
    paths: list[str] | None = None,
    git_metadata: bool = False,
) -> None:
    destination.mkdir(parents=True)
    archive = destination.parent / (destination.name + "-source.tar")
    archived_paths = []
    if paths:
        tracked = subprocess.check_output(
            ["git", "ls-tree", "-r", "-z", "--name-only", "HEAD"], cwd=source
        ).split(b"\0")
        archived_paths = [
            name
            for name in paths
            if any(
                path == os.fsencode(name) or path.startswith(os.fsencode(name + "/"))
                for path in tracked
            )
        ]
    if not paths or archived_paths:
        with archive.open("wb") as output:
            subprocess.run(
                ["git", "archive", "HEAD", "--", *archived_paths],
                cwd=source,
                stdout=output,
                check=True,
                env=dict(os.environ, GIT_LFS_SKIP_SMUDGE="1"),
            )
        with tarfile.open(archive) as bundle:
            bundle.extractall(destination, filter="data")
    # Own authorized edits are frozen with their real hashes for this run.
    names = (
        subprocess.check_output(
            ["git", "diff", "--no-renames", "--name-only", "-z", "HEAD"], cwd=source
        )
        .decode()
        .split("\0")
    )
    names += (
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=source
        )
        .decode()
        .split("\0")
    )
    selected = [
        name
        for name in dict.fromkeys(filter(None, names))
        if not paths
        or any(name == prefix or name.startswith(prefix + "/") for prefix in paths)
    ]
    for name in selected:
        target = destination / name
        if target.is_symlink() or target.is_file():
            target.unlink()
            # A tracked directory can be replaced with a working-tree file.
            for parent in target.parents:
                if (
                    parent == destination
                    or not parent.is_dir()
                    or any(parent.iterdir())
                ):
                    break
                parent.rmdir()
    for name in selected:
        original = source / name
        if original.is_file():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
    if git_metadata:
        subprocess.run(["git", "init", "--quiet"], cwd=destination, check=True)
        subprocess.run(["git", "add", "-A"], cwd=destination, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=ChipEvolve",
                "-c",
                "user.email=local@chipevolve.invalid",
                "commit",
                "--quiet",
                "--allow-empty",
                "-m",
                "Freeze explicit Code source snapshot",
            ],
            cwd=destination,
            check=True,
        )


def inventory(source: Path) -> dict[str, str]:
    return {
        str(p.relative_to(source)): digest(p)
        for p in source.rglob("*")
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts
    }


def environment(objective: Path, context: Path) -> dict[str, str]:
    env = dict(
        os.environ,
        EDA_PLATFORM_OBJECTIVE=str(objective),
        EDA_PLATFORM_CONTEXT=str(context),
        NO_PROXY="127.0.0.1,localhost",
        no_proxy="127.0.0.1,localhost",
        PYTHONNOUSERSITE="1",
    )
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"):
        env.pop(key, None)
    return env
