"""Install the workspace into isolated environments from a wheel directory."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PLATFORM_CLIENT = ["openroad-platform-contracts", "openroad-platform-client"]
TOOLKIT = [*PLATFORM_CLIENT, "eda-toolkits"]
PACKAGES = {
    "execution-foundation": [
        "openroad-platform-" + p
        for p in (
            "contracts",
            "client",
            "runtime",
            "registry",
            "evaluator",
            "provenance",
            "gateway",
        )
    ],
    "data-foundation": [
        "openroad-app-data-foundation",
        *TOOLKIT,
        "openroad-platform-runtime",
    ],
    "data-interface": ["eda-ai-client"],
    "toolkits": [*TOOLKIT, "openroad-platform-runtime"],
    "agent/query-agent": ["agentic-eda-query-agent", "eda-ai-client", *TOOLKIT],
    "agent/flow-agent": TOOLKIT,
    "agent/dplevolve": [*TOOLKIT, "eda-ai-client"],
    "agent/goalevolve": [*TOOLKIT, "eda-ai-client"],
    "agent/timing-eco-agent": [*TOOLKIT, "eda-ai-client"],
    "admin": [*TOOLKIT, "eda-ai-client", "openroad-platform-runtime"],
}
CPU_TORCH = "torch"
CONSTRAINTS = Path(__file__).resolve().with_name("requirements-constraints.txt")
ENVIRONMENT_DEPENDENCIES = {
    "execution-foundation": ["mypy", "black"],
    "agent/query-agent": [
        "pydantic",
        "pyright",
        "import-linter",
    ],
    "agent/flow-agent": [
        "networkx",
        "numpy",
        "openai",
        "pandas",
        "pyyaml",
        "scikit-learn",
        "scipy",
        CPU_TORCH,
    ],
    "agent/dplevolve": ["pyyaml"],
    "agent/goalevolve": [
        "numpy",
        "pyyaml",
        "tree-sitter",
        "tree-sitter-cpp",
    ],
    "agent/timing-eco-agent": ["matplotlib", "numpy"],
}
BUILD_TOOLS = ("setuptools", "wheel")
TEST_TOOLS = ("pytest", "ruff")
EXTERNAL_DEPENDENCIES = (
    *BUILD_TOOLS,
    *TEST_TOOLS,
    *dict.fromkeys(
        requirement
        for requirements in ENVIRONMENT_DEPENDENCIES.values()
        for requirement in requirements
    ),
)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--packages", type=Path, required=True)
    p.add_argument("--dependencies", type=Path, required=True)
    p.add_argument("--evidence", type=Path, required=True)
    a = p.parse_args()
    a.workspace = a.workspace.resolve()
    a.evidence = a.evidence.resolve()
    a.evidence.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((a.packages / "manifest.json").read_text())
    wheels = {}
    for name, expected in manifest["wheels"].items():
        path = (a.packages / name).resolve()
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Wheel digest differs: {name}")
        distribution = name.split("-", 1)[0].replace("_", "-").lower()
        if distribution in wheels:
            raise ValueError(f"Multiple candidate wheels for {distribution}")
        wheels[distribution] = str(path)
    env = dict(
        os.environ,
        PYTHONNOUSERSITE="1",
        PIP_DISABLE_PIP_VERSION_CHECK="1",
        NO_PROXY="localhost,127.0.0.1,::1",
        no_proxy="localhost,127.0.0.1,::1",
    )
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"):
        env.pop(key, None)
    started = time.monotonic()
    records = []
    with (a.evidence / "terminal.log").open("w") as terminal:
        for project, distributions in PACKAGES.items():
            directory = a.workspace / project
            if not directory.is_dir() or (
                project != "admin" and not (directory / ".git").exists()
            ):
                raise RuntimeError(f"Project checkout missing: {directory}")
            venv = directory / ".venv"
            assert not venv.exists(), "installation requires a clean venv destination"
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv)],
                env=env,
                check=True,
                stdout=terminal,
                stderr=subprocess.STDOUT,
            )
            python = venv / "bin/python"
            install = [
                str(python),
                "-m",
                "pip",
                "install",
                "--pre",
                "--no-index",
                "--constraint",
                str(CONSTRAINTS),
                "--find-links",
                str(a.dependencies.resolve()),
                *BUILD_TOOLS,
                *TEST_TOOLS,
                *(wheels[name] for name in distributions),
                *ENVIRONMENT_DEPENDENCIES.get(project, []),
            ]
            terminal.write(json.dumps(install) + "\n")
            terminal.flush()
            subprocess.run(
                install, env=env, check=True, stdout=terminal, stderr=subprocess.STDOUT
            )
            subprocess.run(
                [str(python), "-m", "pip", "check"],
                env=env,
                check=True,
                stdout=terminal,
                stderr=subprocess.STDOUT,
            )
            lock = subprocess.check_output(
                [str(python), "-m", "pip", "freeze", "--all"], env=env, text=True
            )
            evidence_name = directory.name
            (a.evidence / (evidence_name + "-environment.lock.txt")).write_text(lock)
            inspect = json.loads(
                subprocess.check_output(
                    [str(python), "-m", "pip", "inspect"], env=env, text=True
                )
            )
            if any(
                "dir_info" in row.get("direct_url", {}) for row in inspect["installed"]
            ):
                raise RuntimeError(
                    "A source checkout leaked into the installed environment"
                )
            (a.evidence / (evidence_name + "-pip-inspect.json")).write_text(
                json.dumps(inspect, indent=2) + "\n"
            )
            commits = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=directory, text=True
            ).strip()
            records.append(
                {
                    "project": project,
                    "commit": commits,
                    "python": str(python),
                    "installed_distributions": distributions,
                    "editable_dependencies": False,
                }
            )
    result = {
        "installed": records,
        "seconds": time.monotonic() - started,
        "wheel_hashes": manifest["wheels"],
        "runtime_source_dependencies": False,
        "validation": "Installation only; service/business replay is a separate acceptance.",
    }
    (a.evidence / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
