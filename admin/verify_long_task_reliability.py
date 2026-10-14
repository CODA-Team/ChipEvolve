"""Finite A6 deployment and saved-source checks using public platform interfaces."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from chip_evolve.config import Deployment, read, write
from chip_evolve.jobs import Jobs, digest


def require_idle(health: dict[str, Any], queued: list, running: list) -> None:
    if queued or running or any(w.get("active_attempt_ids") for w in health["workers"]):
        raise RuntimeError("Execution service has active consumers; preserve it")


def verify_source(source: Path, files: dict[str, str]) -> None:
    if not files:
        raise ValueError("A saved build needs a nonempty source identity")
    for name, expected in files.items():
        if digest(source / name) != expected:
            raise ValueError("Saved source changed: " + name)


def linked_binary(request: dict[str, Any], private_build: Path) -> Path:
    command = shlex.split(Path(request["command"][3]).read_text())
    output = (Path(request["cwd"]) / command[command.index("-o") + 1]).resolve()
    return private_build / output.relative_to(Path(request["build"]).resolve())


def preserve_incumbents(previous: dict[str, Any], output: Path) -> None:
    for design_id in previous["designs"]:
        pointer = (
            Path(previous["state_root"]) / "designs" / design_id / "incumbent.json"
        )
        if pointer.exists():
            chosen = read(pointer)
            frame = read(chosen["result"])
            if (
                frame["design_id"] != design_id
                or frame["objective_id"] != chosen["objective_id"]
            ):
                raise ValueError("Incumbent pointer belongs to another design or goal")
            write(output / "designs" / design_id / "incumbent.json", chosen)


def upgrade(base: Path, output: Path, wheel: Path) -> Path:
    """Change only the idle, previously dedicated business EF service."""
    from openroad_platform_client import KernelClient, KernelUnavailable

    previous = read(base)
    client = KernelClient(previous["kernel_url"], timeout=60)
    require_idle(
        client.health(), client.runs(status="queued"), client.runs(status="running")
    )
    output.mkdir(parents=True, exist_ok=False)
    env = output / "envs/client"
    shutil.copytree(Path(previous["client_python"]).parent.parent, env, symlinks=True)
    python = str(env / "bin/python")
    subprocess.run(
        [
            previous["builder_python"],
            "-m",
            "pip",
            "--python",
            python,
            "install",
            "--no-deps",
            "--force-reinstall",
            str(wheel.resolve()),
        ],
        check=True,
    )
    # The public client, Toolkit and professional environments remain the
    # qualified installed versions. Only the EF runtime wheel is replaced.
    identity = subprocess.check_output(
        [
            python,
            "-c",
            "from importlib.metadata import distribution; print(distribution('openroad-platform-runtime').locate_file('openroad_platform_runtime/lease.py'))",
        ],
        text=True,
    ).strip()
    if not Path(identity).is_relative_to(env):
        raise RuntimeError("The installed runtime is outside the isolated environment")
    service = previous["services"]["execution"]
    process_args = Path(f"/proc/{service['pid']}/cmdline").read_bytes().split(b"\0")
    if [p.decode() for p in process_args if p] != service["command"]:
        raise RuntimeError("Execution PID no longer identifies the recorded service")
    require_idle(
        client.health(), client.runs(status="queued"), client.runs(status="running")
    )
    write(
        output / "before-upgrade.json",
        {
            "base": str(base.resolve()),
            "service": service,
            "health": client.health(),
            "wheel": str(wheel.resolve()),
            "wheel_sha256": digest(wheel),
        },
    )
    os.kill(service["pid"], signal.SIGTERM)
    deadline = time.monotonic() + 30
    while Path(f"/proc/{service['pid']}/cmdline").exists():
        if not Path(f"/proc/{service['pid']}/cmdline").read_bytes():
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("Idle execution service did not stop cleanly")
        time.sleep(0.1)
    command = [python, *service["command"][1:]]
    environment = dict(
        os.environ,
        PYTHONNOUSERSITE="1",
        NO_PROXY="127.0.0.1,localhost",
        no_proxy="127.0.0.1,localhost",
    )
    environment.pop("PYTHONPATH", None)
    with (output / "execution.log").open("x") as log:
        process = subprocess.Popen(
            command, stdout=log, stderr=log, env=environment, start_new_session=True
        )
    config = {
        **previous,
        "state_root": str(output.resolve()),
        "client_python": python,
        "services": {
            **previous["services"],
            "execution": {"pid": process.pid, "command": command},
        },
    }
    path = output / "local.json"
    write(path, config)
    preserve_incumbents(previous, output)
    deadline = time.monotonic() + 30
    while True:
        try:
            health = client.health()
            break
        except KernelUnavailable:
            if process.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("Updated execution service failed to start")
            time.sleep(0.2)
    write(
        output / "upgrade.json",
        {
            "runtime_module": identity,
            "health": health,
            "wheel_sha256": digest(wheel),
            "service": config["services"]["execution"],
        },
    )
    return path


def replay_goal_build(
    deployment: Deployment, request_path: Path, key: str
) -> dict[str, Any]:
    """Relink a saved Goal candidate in private copies at its CMake paths."""
    request = read(request_path)
    if request["operation"] != "build" or request["command"][:3] != [
        "cmake",
        "-E",
        "cmake_link_script",
    ]:
        raise ValueError("Choose the original saved CMake link operation")
    original_source, original_build = Path(request["source"]), Path(request["build"])
    verify_source(original_source, request["source_files"])
    experiment = deployment.experiment("gcd", key)
    source, build = experiment / "source", experiment / "build"
    for original, target in [(original_source, source), (original_build, build)]:
        subprocess.run(
            ["cp", "--reflink=auto", "-a", str(original), str(target)], check=True
        )
    verify_source(source, request["source_files"])
    private_binary = linked_binary(request, build)
    private_binary.unlink(missing_ok=True)
    command = [deployment.value["runtime"]["executable"], "exec"]
    for root in deployment.value["runtime"]["bind_roots"]:
        command += ["--bind", root + ":" + root]
    command += [
        "--bind",
        f"{source}:{original_source}:ro",
        "--bind",
        f"{build}:{original_build}",
        deployment.value["runtime"]["image"],
        "bash",
        "-c",
        'cd "$1" && shift && exec "$@"',
        "saved-goal-build",
        request["cwd"],
        *request["command"],
    ]
    write(
        experiment / "saved-source.json",
        {
            "original_request": str(request_path.resolve()),
            "source_files": request["source_files"],
            "source": str(source),
            "private_build": str(build),
            "original_source": str(original_source),
            "original_build": str(original_build),
            "immutable_cmake_paths": True,
        },
    )
    jobs = Jobs(deployment, "gcd", experiment)
    record = jobs.command(
        "link",
        command,
        capture=[
            private_binary,
            experiment / "saved-source.json",
            build / "CMakeCache.txt",
            build / "src/CMakeFiles/openroad.dir/link.txt",
        ],
        seconds=5400,
        memory_gib=64,
    )
    verify_source(original_source, request["source_files"])
    verify_source(source, request["source_files"])
    result = {
        "run_id": record["run"]["run_id"],
        "binary": str(private_binary),
        "binary_sha256": digest(private_binary),
        "original_request": str(request_path),
        "source_files": request["source_files"],
        "resources": record["resources"],
    }
    write(experiment / "build-replay.json", result)
    return result


def replay_goal_physical(
    deployment: Deployment,
    build_result: Path,
    request_path: Path,
    reference_path: Path,
    key: str,
) -> dict[str, Any]:
    from chip_evolve.physical import container, qualify

    request_path = request_path.resolve()
    built, request, reference = (
        read(build_result),
        read(request_path),
        read(reference_path),
    )
    binary = Path(built["binary"])
    if digest(binary) != built["binary_sha256"] or request["operation"] != "physical":
        raise ValueError(
            "Choose the qualified private binary and original physical recipe"
        )
    experiment = deployment.experiment(reference["design_id"], key)
    output = experiment / "native"
    output.mkdir()
    original_script = Path(request["command"][-1])
    script = output / "evaluate.tcl"
    script.write_text(
        original_script.read_text().replace(str(original_script.parent), str(output))
    )
    objective = Path(reference["objective"])
    jobs = Jobs(deployment, reference["design_id"], experiment)
    record = jobs.command(
        "native",
        container(
            deployment,
            [
                str(binary),
                "-metrics",
                str(output / "metrics.json"),
                *request["command"][1:-1],
                str(script),
            ],
        ),
        capture=[
            script,
            output / "metrics.json",
            output / "post_route.odb",
            output / "post_route.v",
        ],
        seconds=3600,
        parent=built["run_id"],
        objective=objective,
    )
    result = qualify(
        jobs,
        output / "post_route.odb",
        record["run"]["run_id"],
        objective,
        request_path.parent.parent.parent / "inputs/asap7",
    )
    result["native_method"] = {
        "kind": "fixed-source-replay",
        "original_physical_request": str(request_path),
        "build_replay": str(build_result),
        "recipe_sha256": digest(original_script),
        "changes": "output directory only; same original professional Tcl operations",
    }
    write(experiment / "result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    deploy = sub.add_parser("upgrade")
    deploy.add_argument("--base", type=Path, required=True)
    deploy.add_argument("--output", type=Path, required=True)
    deploy.add_argument("--wheel", type=Path, required=True)
    goal = sub.add_parser("replay-goal-build")
    goal.add_argument("--config", type=Path, required=True)
    goal.add_argument("--request", type=Path, required=True)
    goal.add_argument("--key", required=True)
    physical = sub.add_parser("replay-goal-physical")
    physical.add_argument("--config", type=Path, required=True)
    physical.add_argument("--build-result", type=Path, required=True)
    physical.add_argument("--request", type=Path, required=True)
    physical.add_argument("--reference", type=Path, required=True)
    physical.add_argument("--key", required=True)
    args = parser.parse_args()
    if args.command == "upgrade":
        result: Any = str(upgrade(args.base, args.output, args.wheel))
    elif args.command == "replay-goal-build":
        result = replay_goal_build(Deployment(args.config), args.request, args.key)
    else:
        result = replay_goal_physical(
            Deployment(args.config),
            args.build_result,
            args.request,
            args.reference,
            args.key,
        )
    if isinstance(result, dict):
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "run_id",
                        "binary",
                        "binary_sha256",
                        "design_id",
                        "metrics",
                    )
                    if k in result
                }
            )
        )
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
