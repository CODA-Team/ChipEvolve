"""Build and install the candidate into clean, separate project environments."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from install_workspace import BUILD_TOOLS, EXTERNAL_DEPENDENCIES, PACKAGES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new directory for wheels and installation receipts",
    )
    parser.add_argument(
        "--dependencies",
        type=Path,
        help="offline directory containing third-party wheels",
    )
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        parser.error("Use Python 3.12 for the candidate environments")
    root = Path(__file__).resolve().parents[1]
    for project in PACKAGES:
        path = root / project
        if not (path / ".git").exists() or (path / ".venv").exists():
            parser.error(
                f"{project} needs an initialized submodule without an existing .venv"
            )
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONNOUSERSITE="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"):
        env.pop(key, None)
    builder = output / "builder"
    subprocess.run([sys.executable, "-m", "venv", builder], env=env, check=True)
    python = builder / "bin/python"
    dependencies = (
        args.dependencies.resolve() if args.dependencies else output / "dependencies"
    )
    if args.dependencies is None:
        subprocess.run(
            [
                python,
                "-m",
                "pip",
                "download",
                "--only-binary=:all:",
                "-d",
                dependencies,
                *EXTERNAL_DEPENDENCIES,
            ],
            env=env,
            check=True,
        )
    subprocess.run(
        [
            python,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            dependencies,
            *BUILD_TOOLS,
        ],
        env=env,
        check=True,
    )
    packages = output / "packages"
    subprocess.run(
        [python, root / "admin/package_release.py", "--output", packages],
        env=env,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            root / "admin/install_workspace.py",
            "--workspace",
            root,
            "--packages",
            packages,
            "--dependencies",
            dependencies,
            "--evidence",
            output / "install-evidence",
        ],
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
