"""Shared source checkout and compiler settings for the Code Agents."""

import os
import subprocess

if __package__:
    from .profile_bridge import invoke
else:
    from profile_bridge import invoke


def checkout(destination, url, commit, *, submodules=()):
    destination.mkdir()
    git = ["git", "-C", str(destination)]
    environment = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_LFS_SKIP_SMUDGE="1")
    subprocess.run([*git, "init", "--quiet"], check=True)
    subprocess.run([*git, "remote", "add", "origin", url], check=True)
    subprocess.run(
        [*git, "fetch", "--depth", "1", "origin", commit], env=environment, check=True
    )
    subprocess.run([*git, "checkout", "--detach", commit], env=environment, check=True)
    subprocess.run(
        [
            *git,
            "submodule",
            "update",
            "--init",
            "--recursive",
            "--depth",
            "1",
            "--",
            *submodules,
        ],
        env=environment,
        check=True,
    )


def openroad_build_args(source, *, workspace):
    layout = invoke(workspace, "layout")
    return [
        "-DBUILD_GUI=OFF",
        "-DBUILD_PYTHON=ON",
        "-DBoost_DIR=" + layout["boost_cmake"],
        "-Dortools_ROOT=" + layout["ortools"],
        "-DABSL_ROOT=" + layout["ortools"],
        f"-DFETCHCONTENT_SOURCE_DIR_FMT={source / 'third-party/slang-elab/third_party/fmt'}",
        "-DFETCHCONTENT_FULLY_DISCONNECTED=ON",
        "-DCMAKE_EXE_LINKER_FLAGS=-flto=1",
    ]
