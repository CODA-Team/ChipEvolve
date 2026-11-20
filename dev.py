#!/usr/bin/env python3
"""Project commands that do not inherit other projects' Python or local proxies."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECTS = (
    "execution-foundation",
    "query-agent",
    "data-foundation",
    "data-interface",
    "toolkits",
    "flow-agent",
    "dplevolve",
    "goalevolve",
    "timing-eco-agent",
    "root",
)
AGENTS = {"query-agent", "flow-agent", "dplevolve", "goalevolve", "timing-eco-agent"}
STATIC_TARGETS = {
    "execution-foundation": ["contracts", "core", "gateway/src", "tests"],
    "data-foundation": ["src", "tests", "test_data_foundation.py", "smoke.py"],
    "data-interface": ["src", "tests"],
    "dplevolve": ["scripts", "validation", "baseline", "adapters", "learning"],
    "goalevolve": ["goalevolve", "tests"],
    "timing-eco-agent": ["."],
    "root": [
        "chip-evolve.py",
        "chip_evolve",
        "dev.py",
        "admin/bootstrap.py",
        "admin/install_workspace.py",
        "admin/package_release.py",
        "admin/release/stack.py",
    ],
}
parser = argparse.ArgumentParser()
parser.add_argument("--python", type=Path, help="installed environment for one project")
parser.add_argument("project", choices=(*PROJECTS, "all"))
parser.add_argument("command", choices=("check", "smoke", "python", "shell", "serve"))
parser.add_argument("args", nargs=argparse.REMAINDER)
args = parser.parse_args()
if args.project == "all":
    if args.command != "check" or args.python or args.args:
        parser.error("Use all with check and the default project environments")
    failed = []
    for name in PROJECTS:
        print(f"\nChecking {name}", flush=True)
        result = subprocess.run(
            [sys.executable, str(ROOT / "dev.py"), name, "check"], check=False
        )
        if result.returncode:
            failed.append(name)
    if failed:
        print("Failed checks: " + ", ".join(failed), file=sys.stderr)
    raise SystemExit(bool(failed))
project = ROOT if args.project == "root" else ROOT / args.project
if args.project in AGENTS:
    project = ROOT / "agent" / args.project
default_env = ROOT / "admin/.venv" if args.project == "root" else project / ".venv"
python = args.python.absolute() if args.python else default_env / "bin/python"
if args.project == "root" and args.command != "check":
    parser.error("Use root with check")
venv = python.parent.parent
env = dict(os.environ)
for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"):
    env.pop(key, None)
env.update(
    PYTHONNOUSERSITE="1",
    NO_PROXY="localhost,127.0.0.1,::1",
    no_proxy="localhost,127.0.0.1,::1",
    VIRTUAL_ENV=str(venv),
)
env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
if args.command == "check":
    commands = [[str(python), "-m", "pip", "check"]]
    static_targets = STATIC_TARGETS.get(args.project, [])
    if args.project == "flow-agent":
        static_targets = sorted(path.name for path in (project / "flow").glob("*.py"))
        static_targets.append("test")
    if static_targets:
        commands += [
            [
                str(python.parent / "ruff"),
                "check",
                "--isolated",
                "--select",
                "E9,F63,F7,F82",
                *static_targets,
            ]
        ]
    if args.project == "query-agent":
        commands += [
            [str(python.parent / tool), *options]
            for tool, options in (
                ("ruff", ["check", "src", "tests"]),
                ("ruff", ["format", "--check", "src", "tests"]),
                ("pyright", []),
                ("lint-imports", []),
            )
        ]
    elif args.project == "execution-foundation":
        sources = [
            str(path.relative_to(project))
            for area in ("contracts", "core", "gateway")
            for path in sorted((project / area).glob("*/src"))
        ]
        sources += ["contracts/src", "gateway/src"]
        commands += [[str(python), "-m", "mypy", "--ignore-missing-imports", *sources]]
    elif args.project == "toolkits":
        commands += [
            [str(python.parent / "ruff"), "check", "src", "tests", "--select", "F"]
        ]
    elif args.project == "data-foundation":
        commands += [
            [
                str(python.parent / "ruff"),
                "check",
                "--isolated",
                "--select",
                "E4,E7,E9,F",
                "src",
            ]
        ]
    tests = {
        # Check the module's own checkout against installed dependency wheels.
        "data-foundation": ["-o", "pythonpath=src"],
        "data-interface": ["-o", "pythonpath=src"],
        "flow-agent": ["test"],
        "dplevolve": ["validation"],
        "goalevolve": ["tests/unit"],
        "timing-eco-agent": ["."],
        "root": [
            str(path.relative_to(ROOT))
            for path in sorted((ROOT / "admin").glob("test_*.py"))
        ],
    }.get(args.project, [])
    commands += [[str(python), "-m", "pytest", *tests, *args.args]]
elif args.command == "smoke":
    commands = (
        [[str(python), "smoke.py", *args.args]]
        if args.project == "data-foundation"
        else [
            [
                str(python),
                "-m",
                "pytest",
                *(
                    ["tests/test_local_kernel_http.py"]
                    if args.project == "execution-foundation"
                    else ["test"]
                    if args.project == "flow-agent"
                    else ["validation"]
                    if args.project == "dplevolve"
                    else ["tests/unit"]
                    if args.project == "goalevolve"
                    else ["."]
                    if args.project == "timing-eco-agent"
                    else ["tests"]
                ),
                *args.args,
            ]
        ]
    )
elif args.command == "python":
    commands = [[str(python), *args.args]]
elif args.command == "shell":
    commands = [["bash", "--noprofile", "--norc", *args.args]]
elif args.project == "data-foundation":
    state = ROOT / "var/data-foundation"
    state.mkdir(parents=True, exist_ok=True)
    commands = [
        [
            str(python),
            "-m",
            "openroad_app_data_foundation",
            "--host",
            "127.0.0.1",
            "--port",
            "18924",
            "--db",
            str(state / "snapshots.sqlite"),
            "--no-auto-import",
            "--kernel-url",
            "http://127.0.0.1:18700",
            "--native-root",
            str(state / "native-flow"),
            *args.args,
        ]
    ]
elif args.project == "execution-foundation":
    state = ROOT / "var/execution-foundation"
    state.mkdir(parents=True, exist_ok=True)
    plugin_root = ROOT / "var/toolkits/plugins"
    commands = [
        [
            str(ROOT / "toolkits/.venv/bin/python"),
            "-m",
            "eda_toolkits",
            "configure",
            "--output",
            str(plugin_root),
        ],
        [
            str(python),
            "-m",
            "openroad_platform_gateway",
            "--host",
            "127.0.0.1",
            "--port",
            "18700",
            "--state-root",
            str(state),
            "--plugins-root",
            str(plugin_root),
            "--admissions-root",
            str(project / "admissions"),
            *args.args,
        ],
    ]
else:
    parser.error(
        "此项目没有独立 HTTP 服务；Query Agent 使用 CLI，Data Interface 是 SDK。"
    )
for command in commands:
    working_directory = (
        project
        / {"flow-agent": "flow", "timing-eco-agent": "src"}.get(args.project, ".")
        if args.command in {"check", "smoke"}
        else project
    )
    try:
        result = subprocess.run(command, cwd=working_directory, env=env, check=False)
    except FileNotFoundError as error:
        parser.error(
            f"Required executable for {args.project} is missing: {error.filename}"
        )
    if result.returncode:
        raise SystemExit(result.returncode)
