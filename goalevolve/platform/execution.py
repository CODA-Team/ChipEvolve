"""Opt-in deterministic EF bridge, also runnable in an installed SDK environment.

The standalone delegate/leaf use stdlib and the public EF client only. Native
GoalEvolve imports are restricted to maybe_delegate in the controller process.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from ..execution.execution import ExecutionPolicy, ExecutionReport


TERMINAL = {"succeeded", "failed", "cancelled", "timed_out", "lost"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def source_files(source: Path) -> dict[str, str]:
    return {
        str(p.relative_to(source)): digest(p)
        for root in ("src/rsz", "src/rmp", "src/grt", "src/cut")
        for p in sorted((source / root).rglob("*"))
        if p.is_file()
        and p.suffix in {".cc", ".cpp", ".cxx", ".hh", ".h", ".hpp", ".i", ".tcl"}
    }


def build_root(command: list[str], cwd: Path) -> Path | None:
    # make -B forces a rebuild; only CMake uses -B for a build directory.
    if Path(command[0]).name == "cmake":
        for flag in ("-B", "--build"):
            if flag in command:
                return Path(command[command.index(flag) + 1]).resolve()
    if Path(command[0]).name == "openroad":
        return Path(command[0]).resolve().parent.parent
    for path in (cwd, *cwd.parents):
        if (path / "CMakeCache.txt").is_file():
            return path
    return None


def request_for(
    profile: dict[str, Any], call: dict[str, Any], attempt: int
) -> dict[str, Any]:
    command, cwd = list(call["command"]), Path(call["cwd"])
    build = build_root(command, cwd)
    source = None
    if "-S" in command:
        source = Path(command[command.index("-S") + 1]).resolve()
    elif build and (build / "CMakeCache.txt").is_file():
        for line in (build / "CMakeCache.txt").read_text().splitlines():
            if line.startswith("CMAKE_HOME_DIRECTORY:INTERNAL="):
                source = Path(line.split("=", 1)[1])
    operation = (
        "build"
        if Path(command[0]).name in {"cmake", "make", "gmake", "ninja"}
        else "physical"
        if Path(command[0]).name == "openroad"
        else "analysis"
    )
    if (
        operation == "physical"
        and "-threads" not in command
        and "-version" not in command
    ):
        # OpenROAD defaults to every host CPU, independently of OMP_NUM_THREADS.
        # Bind implicit native evaluations to the same cores reserved by EF.
        command[1:1] = ["-threads", str(profile["resources"]["physical"]["cpu_cores"])]
    inputs = dict(profile["input_files"])
    if command[:3] == ["cmake", "-E", "cmake_link_script"]:
        inputs[command[3]] = digest(Path(command[3]))
    if operation == "physical":
        binary = Path(command[0])
        receipt_path = binary.parent / "platform-build.json"
        receipt = json.loads(receipt_path.read_text())
        source = Path(receipt["source"])
        if (
            digest(binary) != receipt["binary_sha256"]
            or source_files(source) != receipt["source_files"]
        ):
            raise ValueError(
                "Physical evaluation does not match its source/build receipt"
            )
        inputs[str(receipt_path)] = digest(receipt_path)
        inputs[command[0]] = digest(binary)
        if len(command) > 2 and Path(command[-1]).is_file():
            inputs[command[-1]] = digest(Path(command[-1]))
    if operation == "analysis":
        for index, value in enumerate(command[1:], start=1):
            if command[index - 1] == "--csv":
                # The official parser appends to this output on reevaluation.
                continue
            if Path(value).is_file():
                inputs[str(Path(value).resolve())] = digest(Path(value))
    objective_path = profile.get("objective_path") or os.environ.get(
        "EDA_PLATFORM_OBJECTIVE"
    )
    if objective_path:
        objective = Path(objective_path)
        inputs[str(objective)] = digest(objective)
    if os.environ.get("EDA_PLATFORM_CONTEXT"):
        context = Path(os.environ["EDA_PLATFORM_CONTEXT"])
        inputs[str(context)] = digest(context)
    return {
        **call,
        "command": command,
        "design_context": design_context(profile) if operation == "physical" else None,
        "operation": operation,
        "attempt": attempt,
        "source": str(source) if source else None,
        "source_files": source_files(source) if source else {},
        "inputs": inputs,
        "build": str(build) if build else None,
        "image_sha256": profile["toolchain"]["image_sha256"],
        "runtime_identity": {
            key: profile.get(key)
            for key in (
                "toolchain",
                "container_environment",
                "resources",
                "cmake_args",
                "controller_files",
                "deadline_epoch",
            )
        },
    }


def design_context(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Read evidence for a handoff using the installed public data SDK."""
    scope = profile.get("data_context")
    if not scope:
        return None
    from eda_ai_client import EdaAiClient

    client = EdaAiClient(data_url=scope["data_url"], kernel_url=profile["kernel_url"])
    return {
        "scope": client.resolve_scope(snapshot_id=scope["snapshot_id"]),
        "summary": client.get_stage_summary(scope["snapshot_id"]),
        "metrics": client.get_metrics(snapshot_id=scope["metrics_snapshot_id"]),
        "parent_run_id": scope["parent_run_id"],
    }


def validate_request(profile: dict[str, Any], request: dict[str, Any]) -> None:
    if digest(Path(profile["image"])) != request["image_sha256"]:
        raise ValueError("Common image changed")
    if (
        request["source"]
        and source_files(Path(request["source"])) != request["source_files"]
    ):
        raise ValueError("Professional source changed during execution")
    if request["runtime_identity"] != {
        key: profile.get(key)
        for key in (
            "toolchain",
            "container_environment",
            "resources",
            "cmake_args",
            "controller_files",
            "deadline_epoch",
        )
    }:
        raise ValueError("Frozen execution profile changed")
    for name, sha in (profile.get("controller_files") or {}).items():
        if digest(Path(profile["agent_root"]) / name) != sha:
            raise ValueError("Frozen controller changed: " + name)
    for path, sha in request["inputs"].items():
        if digest(Path(path)) != sha:
            raise ValueError("Frozen input changed: " + path)


def _is_variant_build(request: dict[str, Any]) -> bool:
    """Recognize the existing explicit component rebuild and relink commands."""
    command = request.get("command", [])
    if command[:3] == ["cmake", "-E", "cmake_link_script"]:
        return True
    if (
        not command
        or Path(command[0]).name not in {"make", "gmake"}
        or "-B" not in command
        or "-C" not in command
        or not request.get("build")
    ):
        return False
    target = (
        Path(request.get("cwd", ".")) / command[command.index("-C") + 1]
    ).resolve()
    root = Path(request["build"]).resolve() / "src"
    return any(
        target.is_relative_to(root / name) for name in ("rsz", "rmp", "grt", "cut")
    )


def task_for(
    profile: dict[str, Any], request: dict[str, Any], path: Path, key: str
) -> dict[str, Any]:
    resource_kind = "build" if request["operation"] == "build" else "physical"
    if (
        resource_kind == "build"
        and "variant_build" in profile["resources"]
        and _is_variant_build(request)
    ):
        resource_kind = "variant_build"
    if request["operation"] == "analysis" and "analysis" in profile["resources"]:
        resource_kind = "analysis"
    spec = {
        "schema_version": 3,
        "task_id": profile["experiment_id"] + "-" + key,
        "project_id": "goalevolve-common-u4",
        "experiment_id": profile["experiment_id"],
        "design_id": profile.get("design_id", profile["design"]),
        "plugin_id": "openroad-data",
        "labels": {
            "memory_approval": "manual",
            **(
                {
                    "parent_run_id": profile["data_context"]["parent_run_id"],
                    "input_snapshot_id": profile["data_context"]["snapshot_id"],
                }
                if profile.get("data_context")
                else {}
            ),
        },
        "inputs": {
            "adapter": "command",
            "extractor_command": [
                profile["client_python"],
                str(Path(__file__).resolve()),
                "leaf",
                "--profile",
                profile["profile_path"],
                "--request",
                "inputs/request.json",
            ],
        },
        "staged_inputs": [{"source": str(path), "destination": "inputs/request.json"}],
        "timeout_seconds": min(
            request["policy"]["timeout_s"] + 60,
            max(1, int(profile["deadline_epoch"] - time.time())),
        ),
        "resources": profile["resources"][resource_kind],
        "max_attempts": 1,
        "expected_artifacts": ["data_snapshot"],
    }
    if profile.get("objective_path") or os.environ.get("EDA_PLATFORM_OBJECTIVE"):
        from eda_toolkits.objectives import bind_task_objective

        bind_task_objective(spec, profile.get("objective_path"))
    if os.environ.get("EDA_PLATFORM_CONTEXT"):
        from eda_toolkits.context import bind_task_context

        bind_task_context(spec)
    return spec


def link_command(command: list[str]) -> list[str]:
    """Honor explicit single-worker LTO rather than the seed's automatic flag."""
    if command[:3] != ["cmake", "-E", "cmake_link_script"]:
        return command
    lines = Path(command[3]).read_text().strip().splitlines()
    if len(lines) != 1:
        return command
    arguments = shlex.split(lines[0])
    if "-flto=auto" in arguments and "-flto=1" in arguments:
        return [argument for argument in arguments if argument != "-flto=auto"]
    return command


def container_command(
    profile: dict[str, Any], request: dict[str, Any], workspace: Path
) -> list[str]:
    scratch = workspace / "tmp"
    scratch.mkdir(exist_ok=True)
    command = ["apptainer", "exec", "--cleanenv", "--containall", "--no-home"]
    for path in profile["read_roots"]:
        command += ["--bind", path + ":" + path + ":ro"]
    for path in profile["write_roots"]:
        command += ["--bind", path + ":" + path]
    command += ["--bind", str(scratch) + ":/tmp", "--pwd", request["cwd"]]
    for key, value in profile["container_environment"].items():
        command += ["--env", key + "=" + value]
    return [*command, profile["image"], *link_command(request["command"])]


def _forward_logs(stdout: Path, stderr: Path, stop: threading.Event) -> None:
    """Mirror original file bytes into EF's live log, without buffering the run."""
    with stdout.open("rb") as out, stderr.open("rb") as err:

        def drain():
            for stream in (out, err):
                while chunk := stream.read(65536):
                    print(chunk.decode("utf-8", errors="replace"), end="", flush=True)

        while not stop.wait(0.1):
            drain()
        drain()


def leaf(profile: dict[str, Any], request: dict[str, Any]) -> int:
    workspace = Path.cwd()
    validate_request(profile, request)
    command = (
        container_command(profile, request, workspace)
        if request["operation"] != "analysis"
        else request["command"]
    )
    if request["operation"] == "analysis" and Path(command[0]).name in {
        "python",
        "python3",
    }:
        command = [profile["agent_python"], *command[1:]]
    folder = Path(request["receipt_root"])
    stdout, stderr = folder / "stdout.log", folder / "stderr.log"
    env = dict(request["environment"] or os.environ)
    env["GOALEVOLVE_EXECUTION_LEAF"] = "1"
    started = time.time()
    timed_out = False
    with stdout.open("w") as out, stderr.open("w") as err:
        process = subprocess.Popen(
            command,
            cwd=request["cwd"],
            env=env,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
        forwarding_stop = threading.Event()
        forwarding = threading.Thread(
            target=_forward_logs, args=(stdout, stderr, forwarding_stop), daemon=True
        )
        forwarding.start()
        try:
            code = process.wait(timeout=request["policy"]["timeout_s"])
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass
            # Kill any pipe/file-holding descendants even if the direct
            # child has already exited. This group belongs to this leaf only.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            code = process.wait()
        finally:
            forwarding_stop.set()
            forwarding.join()
    validate_request(profile, request)
    output_log = request["output_log"]
    if output_log:
        target = Path(output_log)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as output:
            for stream in (stdout, stderr):
                with stream.open("rb") as input_stream:
                    shutil.copyfileobj(input_stream, output)
    outputs: dict[str, str] = {}
    evidence = workspace / "query-data"
    evidence.mkdir(exist_ok=True)
    if request["operation"] == "build":
        files = [Path(request["build"]) / "bin/openroad"] if request["build"] else []
    else:
        files = sorted(Path(request["cwd"]).glob("*"))
    files += [stdout, stderr]
    for index, item in enumerate(files):
        if item.is_file() and item.suffix not in {".o", ".a", ".so"}:
            target = evidence / str(index) / item.name
            target.parent.mkdir(parents=True)
            shutil.copyfile(item, target)
            outputs[str(item)] = digest(target)
    receipt = {
        "request": request,
        "command": command,
        "returncode": code,
        "timed_out": timed_out,
        "elapsed_seconds": time.time() - started,
        "output_files": outputs,
    }
    write_json(folder / "leaf.json", receipt)
    write_json(evidence / "manifest.json", {"evidence_only": True, "receipt": receipt})
    return code if code else int(timed_out)


def observe_run(
    client: Any, run_id: str, deadline: float, folder: Path
) -> dict[str, Any]:
    """Retry only a failed read, without resubmitting or extending the experiment."""
    from openroad_platform_client import KernelUnavailable

    for attempt in range(3):
        if time.time() >= deadline:
            raise TimeoutError("U4 supervision budget exhausted")
        try:
            return client.run(run_id)
        except KernelUnavailable as exc:
            with (folder / "observation-errors.jsonl").open("a") as log:
                log.write(
                    json.dumps(
                        {"run_id": run_id, "time": time.time(), "error": str(exc)}
                    )
                    + "\n"
                )
            if attempt == 2:
                raise
            time.sleep(min(1, max(0, deadline - time.time())))
    raise AssertionError("unreachable")


def delegate(profile: dict[str, Any], call: dict[str, Any]) -> dict[str, Any]:
    from openroad_platform_client import KernelClient

    client = KernelClient(profile["kernel_url"], timeout=60)
    last: dict[str, Any] = {}
    for attempt in range(1, call["policy"]["retries"] + 2):
        if time.time() >= profile["deadline_epoch"]:
            raise TimeoutError("U4 original supervision budget exhausted")
        request = request_for(profile, call, attempt)
        key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[
            :24
        ]
        folder = Path(profile["operations_root"]) / key
        request["receipt_root"] = str(folder)
        request_path = folder / "request.json"
        write_json(request_path, request)
        submitted = client.submit(
            task_for(profile, request, request_path, key),
            idempotent=True,
            idempotency_key=profile["experiment_id"] + ":" + key,
        )
        run_id = submitted["run"]["run_id"]
        write_json(folder / "submission.json", {"run_id": run_id, "key": key})
        try:
            while True:
                row = observe_run(client, run_id, profile["deadline_epoch"], folder)
                if row["status"] in TERMINAL:
                    break
                if time.time() >= profile["deadline_epoch"]:
                    client.cancel(run_id)
                    raise TimeoutError("U4 supervision budget exhausted")
                time.sleep(1)
        except BaseException:
            client.cancel(run_id)
            raise
        artifacts = client.artifacts(run_id)
        write_json(folder / "execution.json", {"run": row, "artifacts": artifacts})
        receipt_path = folder / "leaf.json"
        receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
        for value in artifacts:
            if value["kind"] == "data_snapshot":
                client.materialize_artifact(
                    run_id, value["artifact_id"], str(folder / "evidence.zip")
                )
        code = receipt.get("returncode", 1)
        timeout = receipt.get("timed_out", False) or row["status"] == "timed_out"
        last = {
            "ok": row["status"] == "succeeded" and code == 0 and not timeout,
            "attempts": attempt,
            "returncode": None if timeout else code,
            "stdout_tail": (
                (folder / "stdout.log").read_text(errors="replace")[-4000:]
                if (folder / "stdout.log").exists()
                else ""
            ),
            "stderr_tail": (
                (folder / "stderr.log").read_text(errors="replace")[-4000:]
                if (folder / "stderr.log").exists()
                else json.dumps(row)
            ),
            "resource_error": (
                "timeout"
                if timeout
                else (
                    None
                    if code == 0 and row["status"] == "succeeded"
                    else "command_failed"
                )
            ),
        }
        if timeout:
            client.cancel(run_id)
        if last["ok"] or timeout:
            return last
    return last


def record_build(source: Path, binary: Path) -> None:
    """Bind the completed native build or exact-source donor to its binary."""
    from .profile import load_platform_profile

    profile = load_platform_profile()
    if profile:
        write_json(
            binary.parent / "platform-build.json",
            {
                "source": str(source.resolve()),
                "source_files": source_files(source),
                "binary_sha256": digest(binary),
                "toolchain": profile["toolchain"],
                "cmake_args": profile["cmake_args"],
            },
        )


def toolchain_evidence(source_root: Path | None) -> dict[str, Any] | None:
    """Get native fingerprint fields through EF for a container-built seed."""
    from ..execution.execution import ExecutionPolicy, ResilientCommandRunner
    from .profile import load_platform_profile

    profile = load_platform_profile()
    if not profile:
        return None
    seed = Path(profile["source_seed"])
    binary = seed / "build/bin/openroad"
    result: dict[str, Any] = {
        "openroad_bin": None,
        "openroad_version": None,
        "openroad_sha256": None,
        "source_git_commit": None,
    }
    if binary.is_file():
        record_build(seed, binary)
        folder = Path(profile["state_root"]) / "toolchain-info"
        folder.mkdir(exist_ok=True)
        report = ResilientCommandRunner(
            ExecutionPolicy(timeout_s=30, retries=0, min_free_gb=0)
        ).run(
            command=[str(binary), "-version"],
            cwd=folder,
            output_log=folder / "version.log",
        )
        if not report.ok:
            raise RuntimeError("EF common binary identity query failed")
        result.update(
            openroad_bin=str(binary),
            openroad_version=report.stdout_tail.strip(),
            openroad_sha256=digest(binary),
        )
    source = source_root or seed
    top_level = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=source,
        capture_output=True,
        text=True,
        check=False,
    )
    if (
        top_level.returncode == 0
        and Path(top_level.stdout.strip()).resolve() == source.resolve()
    ):
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=source,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            result["source_git_commit"] = completed.stdout.strip()
    return result


def maybe_delegate(
    *,
    command: list[str],
    cwd: Path,
    policy: ExecutionPolicy,
    output_log: Path | None,
    environment: dict[str, str] | None,
) -> ExecutionReport | None:
    from dataclasses import asdict

    from ..execution.execution import ExecutionReport
    from .profile import load_platform_profile

    profile = load_platform_profile()
    if not profile or os.environ.get("GOALEVOLVE_EXECUTION_LEAF") == "1":
        return None
    call = {
        "invocation_id": uuid4().hex,
        "command": command,
        "cwd": str(cwd.resolve()),
        "policy": asdict(policy),
        "output_log": str(output_log.resolve()) if output_log else None,
        "environment": {
            k: v
            for k, v in (environment or os.environ).items()
            if k
            in {
                "PATH",
                "LANG",
                "LC_ALL",
                "NO_PROXY",
                "no_proxy",
                "PYTHONNOUSERSITE",
                "PYTHONPYCACHEPREFIX",
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
            }
        },
    }
    identity = hashlib.sha256(json.dumps(call, sort_keys=True).encode()).hexdigest()
    call_path = Path(profile["operations_root"]) / "calls" / (identity + ".json")
    result_path = call_path.with_suffix(".result.json")
    write_json(call_path, call)
    result = subprocess.run(
        [
            profile["client_python"],
            str(Path(__file__).resolve()),
            "delegate",
            "--profile",
            profile["profile_path"],
            "--request",
            str(call_path),
            "--result",
            str(result_path),
        ],
        check=False,
    )
    if result.returncode:
        return ExecutionReport(
            False,
            0,
            result.returncode,
            "",
            "EF delegation failed; see operation receipts",
            "delegation_failed",
        )
    return ExecutionReport(**json.loads(result_path.read_text()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("delegate", "leaf"))
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text())
    request = json.loads(args.request.read_text())
    if args.mode == "leaf":
        return leaf(profile, request)
    write_json(args.result, delegate(profile, request))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
