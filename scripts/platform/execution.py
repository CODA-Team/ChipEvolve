"""Opt-in EF delegation for native DPLEvolve deterministic entrypoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

TERMINAL = {"succeeded", "failed", "cancelled", "timed_out", "lost"}
SCRIPTS = {
    "core_build": "scripts/workspace/build_openroad_only.sh",
    "variant_build": "scripts/workspace/build_openroad_variant_relink.py",
    "baseline": "baseline/run_baseline.sh",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def tree_files(root: Path) -> dict[str, str]:
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root,
        )
        .decode()
        .split("\0")
    )
    return {
        n: digest(root / n)
        for n in sorted(set(filter(None, names)))
        if (root / n).is_file() and not n.endswith(".pyc")
    }


def option(argv: list[str], name: str, default: str) -> str:
    return argv[argv.index(name) + 1] if name in argv else default


def request_for(
    profile: dict[str, Any], operation: str, argv: list[str]
) -> dict[str, Any]:
    if operation not in SCRIPTS and operation != "placement":
        raise ValueError("Unknown deterministic operation: " + operation)
    orfs = Path(profile["orfs_root"])
    core = Path(profile["core_root"])
    agent = Path(profile["agent_root"])
    source = orfs / "tools/OpenROAD/src/dpl_evolve"
    outputs: list[str] = []
    inputs: dict[str, str] = {}
    binary = ""
    if operation == "core_build":
        install = Path(option(argv, "--install-root", str(core / "install/OpenROAD")))
        binary = str(install / "bin/openroad")
        outputs = [binary, str(install / "bin/sta")]
    elif operation == "variant_build":
        if "--core-root" not in argv:
            argv = [*argv, "--core-root", str(core)]
        variant = Path(
            option(
                argv,
                "--variant-root",
                str(Path(profile["state_root"]) / "variants/default"),
            )
        )
        source = Path(option(argv, "--dpl-src", str(variant / "dpl_evolve"))).resolve()
        install = Path(
            option(argv, "--install-root", str(variant / "install/OpenROAD"))
        )
        binary = str(install / "bin/openroad")
        outputs = [binary]
        for item in (
            core / "build/compile_commands.json",
            core / "build/src/CMakeFiles/openroad.dir/link.txt",
            core / "install/OpenROAD/bin/openroad",
        ):
            inputs[str(item)] = digest(item)
    elif operation == "baseline":
        variant_name = option(argv, "--flow-variant", profile["flow_variant"])
        tag = option(argv, "--run-tag", "")
        if not tag or Path(tag).name != tag or variant_name != profile["flow_variant"]:
            raise ValueError(
                "Platform evaluation requires a stable run tag and the frozen flow variant"
            )
        binary = option(argv, "--openroad-binary", profile["core_binary"])
        if "--openroad-binary" not in argv:
            argv = [*argv, "--openroad-binary", binary]
        build_receipt = Path(binary).parent / "platform-build.json"
        build = json.loads(build_receipt.read_text())
        if build["binary_sha256"] != digest(Path(binary)):
            raise ValueError("Evaluation binary differs from its build receipt")
        source = Path(build["source"])
        if tree_files(source) != build["source_files"]:
            raise ValueError(
                "Candidate source changed after build; rebuild before evaluating"
            )
        case_id = option(argv, "--case", profile["case"])
        for field in ("design", "platform"):
            actual = subprocess.check_output(
                [
                    sys.executable,
                    str(agent / "scripts/repo/case_registry.py"),
                    "--case",
                    case_id,
                    "--field",
                    field,
                ],
                text=True,
            ).strip()
            if actual != profile[field]:
                raise ValueError(
                    f"Native case {case_id} {field} differs from platform binding"
                )
        inputs[binary] = digest(Path(binary))
        inputs[str(build_receipt)] = digest(build_receipt)
        result = (
            orfs
            / "flow/results"
            / profile["platform"]
            / profile["design"]
            / variant_name
        )
        for item in (
            result / (option(argv, "--input-stage", "3_4_place_resized") + ".odb"),
            result / "2_floorplan.sdc",
        ):
            inputs[str(item)] = digest(item)
        reports = (
            orfs
            / "flow/reports"
            / profile["platform"]
            / profile["design"]
            / variant_name
            / "dpl_evolve_baseline"
            / tag
        )
        logs = (
            orfs
            / "flow/logs"
            / profile["platform"]
            / profile["design"]
            / variant_name
            / "dpl_evolve_baseline"
            / tag
        )
        outputs = [str(reports), str(logs), str(result / "dpl_evolve_baseline" / tag)]
    else:
        result = (
            orfs
            / "flow/results"
            / profile["platform"]
            / profile["design"]
            / profile["flow_variant"]
        )
        outputs = [str(result)]
    objective_path = profile.get("objective_path") or os.environ.get(
        "EDA_PLATFORM_OBJECTIVE"
    )
    if objective_path:
        objective = Path(objective_path)
        inputs[str(objective)] = digest(objective)
    if os.environ.get("EDA_PLATFORM_CONTEXT"):
        context = Path(os.environ["EDA_PLATFORM_CONTEXT"])
        inputs[str(context)] = digest(context)
    cache = Path(profile["core_root"]) / "build/CMakeCache.txt"
    if cache.is_file():
        inputs[str(cache)] = digest(cache)
    return {
        "design_context": design_context(profile) if operation == "baseline" else None,
        "operation": operation,
        "attempt": os.environ.get("DPL_EVOLVE_OPERATION_ATTEMPT", "initial"),
        "argv": argv,
        "cwd": str(agent),
        "toolchain": profile["toolchain"],
        "source": str(source),
        "source_files": tree_files(source),
        "inputs": inputs,
        "outputs": outputs,
        "binary": binary,
        "controller_files": profile["controller_files"],
        "prepared_source_sha256": profile["prepared_source_sha256"],
        "runtime_identity": {
            "cmake_args": profile["cmake_args"],
            "container_environment": profile["container_environment"],
            "resources": profile["resources"],
            "core_root": profile["core_root"],
        },
    }


def design_context(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Consume the optional registered handoff through the public data SDK."""
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
    if digest(Path(profile["image"])) != request["toolchain"]["image_sha256"]:
        raise ValueError("Common image identity changed")
    for name, sha in request["controller_files"].items():
        if digest(Path(profile["agent_root"]) / name) != sha:
            raise ValueError("Frozen controller changed: " + name)
    if tree_files(Path(request["source"])) != request["source_files"]:
        raise ValueError("Source changed during deterministic operation")
    for name, sha in request["inputs"].items():
        if digest(Path(name)) != sha:
            raise ValueError("Input changed: " + name)


def task_for(
    profile: dict[str, Any], request: dict[str, Any], request_path: Path, key: str
) -> dict[str, Any]:
    operation = request["operation"]
    extras = (
        [
            "outputs/0/metrics.json",
            "outputs/0/run_manifest.json",
            "outputs/0/post_metrics_summary.json",
            "outputs/1/3_5_place_dp.json",
            "outputs/2/legalized.odb",
        ]
        if operation == "baseline"
        else []
    )
    if operation.endswith("build"):
        extras = [
            "outputs/" + str(i) + "/" + Path(p).name
            for i, p in enumerate(request["outputs"])
        ]
    spec = {
        "schema_version": 3,
        "task_id": profile["experiment_id"] + "-" + key,
        "project_id": "dplevolve-common-u3",
        "experiment_id": profile["experiment_id"],
        "design_id": profile["design"],
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
                str(Path(profile["agent_root"]) / "scripts/platform/execution.py"),
                "leaf",
                "--profile",
                profile["profile_path"],
                "--request",
                "inputs/request.json",
            ],
            "native_extra_paths": extras,
        },
        "staged_inputs": [
            {"source": str(request_path), "destination": "inputs/request.json"}
        ],
        "timeout_seconds": 5400 if operation.endswith("build") else 900,
        "resources": profile["resources"][
            "build" if operation.endswith("build") else "physical"
        ],
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


def delegate(profile: dict[str, Any], operation: str, argv: list[str]) -> int:
    from openroad_platform_client import KernelClient

    request = request_for(profile, operation, argv)
    key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[:24]
    folder = Path(profile["operations_root"]) / key
    request_path = folder / "request.json"
    if request_path.exists() and json.loads(request_path.read_text()) != request:
        raise ValueError("Operation identity collision")
    write_json(request_path, request)
    client = KernelClient(profile["kernel_url"], timeout=60)
    submitted = client.submit(
        task_for(profile, request, request_path, key),
        idempotent=True,
        idempotency_key=profile["experiment_id"] + ":" + key,
    )
    run_id = submitted["run"]["run_id"]
    write_json(folder / "submission.json", {"run_id": run_id, "key": key})
    try:
        while True:
            row = client.run(run_id)
            if row["status"] in TERMINAL:
                break
            if time.time() >= profile["deadline_epoch"]:
                client.cancel(run_id)
                raise TimeoutError("U3 supervision budget exhausted")
            time.sleep(1)
    except KeyboardInterrupt:
        client.cancel(run_id)
        raise
    artifacts = client.artifacts(run_id)
    write_json(folder / "execution.json", {"run": row, "artifacts": artifacts})
    if row["status"] != "succeeded":
        print(
            json.dumps(
                {"operation": operation, "run_id": run_id, "status": row["status"]}
            )
        )
        leaf_receipt = folder / "leaf.json"
        native_code = (
            json.loads(leaf_receipt.read_text()).get("exit_code", 1)
            if leaf_receipt.is_file()
            else 1
        )
        return native_code if isinstance(native_code, int) and native_code > 0 else 1
    validate_request(profile, request)
    for value in artifacts:
        if value["kind"] == "data_snapshot":
            client.materialize_artifact(
                run_id, value["artifact_id"], str(folder / "evidence.zip")
            )
    print(json.dumps({"operation": operation, "run_id": run_id, "status": "succeeded"}))
    return 0


def maybe_delegate(operation: str, argv: list[str]) -> int | None:
    path = os.environ.get("DPL_EVOLVE_PLATFORM_PROFILE")
    if not path or os.environ.get("DPL_EVOLVE_EXECUTION_LEAF") == "1":
        return None
    profile = json.loads(Path(path).read_text())
    command = [
        profile["client_python"],
        str(Path(__file__).resolve()),
        "delegate",
        operation,
        "--",
        *argv,
    ]
    return subprocess.run(command, check=False).returncode


def container_command(
    profile: dict[str, Any], request: dict[str, Any], workspace: Path
) -> list[str]:
    scratch = workspace / "tmp"
    scratch.mkdir(exist_ok=True)
    command = ["apptainer", "exec", "--cleanenv", "--containall", "--no-home"]
    for path in (profile["agent_root"], profile["orfs_root"]):
        command += ["--bind", path + ":" + path + ":ro"]
    for path in (profile["state_root"], str(workspace), *profile["flow_output_roots"]):
        command += ["--bind", path + ":" + path]
    if request["operation"] != "core_build":
        command += ["--bind", profile["core_root"] + ":" + profile["core_root"] + ":ro"]
    generated_source = Path(profile["core_root"]) / "generated-source"
    if request["operation"] == "core_build" and not generated_source.exists():
        shutil.copytree(
            Path(profile["orfs_root"]) / "tools/OpenROAD",
            generated_source,
            symlinks=True,
        )
    # Upstream CMake generates Version.hh, messages.txt and STA documentation
    # in source paths. Compile from a private copy at the same container path.
    targets = dict.fromkeys(
        [profile["orfs_root"] + "/tools/OpenROAD", compiled_source_root(profile)]
    )
    for target in targets:
        command += [
            "--bind",
            str(generated_source)
            + ":"
            + target
            + (":ro" if request["operation"] != "core_build" else ""),
        ]
    command += ["--bind", str(scratch) + ":/tmp", "--pwd", request["cwd"]]
    environment = dict(profile["container_environment"])
    environment.update(DPL_EVOLVE_EXECUTION_LEAF="1", DPL_EVOLVE_SKIP_ENV_SH="1")
    for name, value in environment.items():
        command += ["--env", name + "=" + value]
    operation = request["operation"]
    if operation == "placement":
        native = request["argv"]
    else:
        script = str(Path(profile["agent_root"]) / SCRIPTS[operation])
        native = (
            [profile["container_python"], script]
            if script.endswith(".py")
            else ["bash", script]
        )
        native += request["argv"]
        if operation == "core_build":
            native += ["--disable-gui", "--generator", "Unix Makefiles"]
            for argument in profile["cmake_args"]:
                native += ["--cmake-arg", argument]
    return [*command, profile["image"], *native]


def compiled_source_root(profile: dict[str, Any]) -> str:
    """CMake's qualified recipes keep their original absolute source prefix."""
    cache = Path(profile["core_root"]) / "build/CMakeCache.txt"
    if cache.is_file():
        for line in cache.read_text().splitlines():
            if line.startswith("CMAKE_HOME_DIRECTORY:INTERNAL="):
                return line.split("=", 1)[1]
    return profile["orfs_root"] + "/tools/OpenROAD"


def leaf(profile: dict[str, Any], request: dict[str, Any]) -> int:
    workspace = Path.cwd()
    validate_request(profile, request)
    command = container_command(profile, request, workspace)
    started = time.time()
    result = subprocess.run(command, check=False)
    validate_request(profile, request)
    if request["operation"] == "core_build":
        compiled_source = Path(profile["core_root"]) / "generated-source/src/dpl_evolve"
        if tree_files(compiled_source) != request["source_files"]:
            raise ValueError("Build altered the private copy of algorithm source")
    receipt: dict[str, Any] = {
        "request": request,
        "command": command,
        "exit_code": result.returncode,
        "elapsed_seconds": time.time() - started,
        "output_files": {},
    }
    for i, output in enumerate(request["outputs"]):
        path = Path(output)
        if path.is_dir():
            files = sorted(p for p in path.rglob("*") if p.is_file())
        else:
            files = [path] if path.is_file() else []
        for item in files:
            target = (
                workspace
                / "outputs"
                / str(i)
                / (item.relative_to(path) if path.is_dir() else item.name)
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, target)
            receipt["output_files"][str(item)] = digest(target)
            if not request["operation"].endswith("build"):
                evidence = workspace / "query-data" / target.relative_to(workspace)
                evidence.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(target, evidence)
    if (
        result.returncode == 0
        and request["binary"]
        and request["operation"].endswith("build")
    ):
        binary = Path(request["binary"])
        write_json(
            binary.parent / "platform-build.json",
            {
                "binary_sha256": digest(binary),
                "source": request["source"],
                "source_files": request["source_files"],
                "request": request,
            },
        )
    write_json(
        workspace / "query-data/manifest.json",
        {"evidence_only": True, "receipt": receipt},
    )
    write_json(
        Path(profile["operations_root"])
        / hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[:24]
        / "leaf.json",
        receipt,
    )
    print(
        json.dumps(
            {"native_exit_code": result.returncode, "outputs": receipt["output_files"]}
        )
    )
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    dispatch = commands.add_parser("delegate")
    dispatch.add_argument("operation")
    dispatch.add_argument("argv", nargs=argparse.REMAINDER)
    run = commands.add_parser("leaf")
    run.add_argument("--profile", type=Path, required=True)
    run.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    profile_path = (
        args.profile
        if args.command == "leaf"
        else Path(os.environ["DPL_EVOLVE_PLATFORM_PROFILE"])
    )
    profile = json.loads(profile_path.read_text())
    if (
        args.command == "delegate"
        and str(Path(sys.executable).absolute()) != profile["client_python"]
    ):
        os.execv(
            profile["client_python"],
            [profile["client_python"], str(Path(__file__).resolve()), *sys.argv[1:]],
        )
    if args.command == "leaf":
        return leaf(profile, json.loads(args.request.read_text()))
    return delegate(
        profile, args.operation, args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    )


if __name__ == "__main__":
    raise SystemExit(main())
