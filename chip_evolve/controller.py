"""Freeze the professional inputs and supervise its controller process."""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import time
from pathlib import Path

from .config import write
from .jobs import digest


def freeze(
    source: Path,
    destination: Path,
    *,
    paths: list[str] | None = None,
    git_metadata: bool = False,
) -> None:
    destination.mkdir(parents=True)
    archive = destination.parent / (destination.name + "-source.tar")
    roots = (
        subprocess.check_output(["git", "ls-tree", "--name-only", "HEAD"], cwd=source)
        .decode()
        .splitlines()
    )
    archived_paths = [name for name in paths or [] if name.split("/")[0] in roots]
    with archive.open("wb") as output:
        subprocess.run(
            ["git", "archive", "HEAD", *archived_paths],
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
            ["git", "diff", "--name-only", "-z", "HEAD"], cwd=source
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
    for name in filter(None, names):
        if paths and not any(
            name == prefix or name.startswith(prefix + "/") for prefix in paths
        ):
            continue
        original = source / name
        if original.is_file():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
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
    return dict(
        os.environ,
        EDA_PLATFORM_OBJECTIVE=str(objective),
        EDA_PLATFORM_CONTEXT=str(context),
        NO_PROXY="127.0.0.1,localhost",
        no_proxy="127.0.0.1,localhost",
        PYTHONNOUSERSITE="1",
    )


def invoke(
    command: list[str], source: Path, env: dict[str, str], folder: Path, seconds: int
) -> None:
    timeout = float(seconds)
    if "EDA_PLATFORM_DEADLINE_EPOCH" in env:
        timeout = min(timeout, float(env["EDA_PLATFORM_DEADLINE_EPOCH"]) - time.time())
        if timeout <= 0:
            raise subprocess.TimeoutExpired(command, seconds)
    with (folder / "controller.log").open("x") as log:
        process = subprocess.Popen(
            command,
            cwd=source,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            code = process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
            from .native_process import stop

            cleanup = stop(process)
            cleanup["reason"] = type(error).__name__
            write(folder / "native-frontend-cleanup.json", cleanup)
            raise
    if code:
        raise RuntimeError(
            "Native professional controller failed; evidence retained at " + str(folder)
        )
