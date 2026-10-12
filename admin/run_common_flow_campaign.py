"""Prepare and run U2 using qualified wheels and the common physical tools."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import tarfile
import time
from pathlib import Path

from flow_native_baseline import FORMAL, WORKSPACE, call, digest, now, write_json
from qualify_common_toolchain import IMAGE_SHA, OPENROAD, ORFS, environment

OCI = "212127afc6538596e9c819ecea4830ec7edb76e2fca51f8dcd741c772558d4e0"
TOOLS = {
    "openroad": "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad",
    "yosys": "/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys",
}


def image_identity(runtime, image):
    script = (
        "import json,hashlib;from pathlib import Path;import sys;"
        'print(json.dumps({name:{"path":path,"sha256":hashlib.sha256('
        "Path(path).read_bytes()).hexdigest()} "
        "for name,path in json.loads(sys.argv[1]).items()}))"
    )
    return json.loads(
        subprocess.check_output(
            [
                runtime,
                "exec",
                "--cleanenv",
                "--containall",
                str(image),
                "/usr/bin/python3",
                "-c",
                script,
                json.dumps(TOOLS),
            ],
            env=environment(),
            text=True,
            timeout=60,
        )
    )


def qualification(qualified):
    config = json.loads((qualified / "config.json").read_text())
    accepted = json.loads((qualified / "u1-acceptance.json").read_text())
    if not accepted.get("engineering_accepted"):
        raise ValueError("U1 engineering qualification is required")
    if (config["image_sha256"], config["openroad_commit"], config["orfs_commit"]) != (
        IMAGE_SHA,
        OPENROAD,
        ORFS,
    ):
        raise ValueError("Use the qualified common toolchain")
    if digest(Path(config["image"])) != IMAGE_SHA:
        raise ValueError("The qualified image changed")
    if digest(qualified / "source-manifest.json") != config["source_manifest_sha256"]:
        raise ValueError("The qualified source evidence changed")
    return config


def install_toolkit(run, qualified):
    """Build only the changed committed Toolkit; reuse qualified base wheels."""
    source = run / "dependency-sources/toolkits"
    source.mkdir(parents=True)
    archive = run / "preparation/toolkits.tar"
    archive.write_bytes(
        subprocess.check_output(["git", "archive", "HEAD"], cwd=WORKSPACE / "toolkits")
    )
    with tarfile.open(archive) as bundle:
        bundle.extractall(source, filter="data")
    wheels = run / "wheels"
    wheels.mkdir()
    for wheel in (qualified / "wheels").glob("*.whl"):
        if not wheel.name.startswith("eda_toolkits-"):
            shutil.copy2(wheel, wheels / wheel.name)
    builder = str(WORKSPACE / "execution-foundation/.venv/bin/python")
    subprocess.run(
        [
            builder,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheels),
            str(source),
        ],
        check=True,
        env=environment(),
        timeout=300,
    )
    venv = run / "envs/toolkits"
    subprocess.run(
        [
            str(WORKSPACE / "admin/.venv/bin/python"),
            "-m",
            "venv",
            "--without-pip",
            str(venv),
        ],
        check=True,
        timeout=60,
    )
    subprocess.run(
        [
            builder,
            "-m",
            "pip",
            "--python",
            str(venv / "bin/python"),
            "install",
            "--pre",
            "--no-index",
            "--find-links",
            str(WORKSPACE / "wheelhouse"),
            *map(str, sorted(wheels.glob("*.whl"))),
        ],
        check=True,
        env=environment(),
        timeout=180,
    )
    return str(venv / "bin/python")


def prepare(run, qualified):
    if run.exists():
        raise FileExistsError("Preserve previous experiments; use a new directory")
    config = qualification(qualified)
    for project in (FORMAL, WORKSPACE / "toolkits"):
        if call(["git", "status", "--porcelain"], project):
            raise ValueError("Freeze committed Flow and Toolkit before preparation")
    runtime = shutil.which("apptainer")
    if runtime is None:
        raise ValueError("apptainer is unavailable")
    run.mkdir(parents=True)
    (run / "preparation").mkdir()
    subprocess.run(
        ["git", "clone", "--no-hardlinks", str(FORMAL), str(run / "source")], check=True
    )
    binaries = image_identity(runtime, config["image"])
    shutil.copy2(
        qualified / "source-manifest.json", run / "common-source-manifest.json"
    )
    toolchain = {
        "image_sha256": IMAGE_SHA,
        "oci_digest": OCI,
        "orfs_commit": ORFS,
        "openroad_commit": OPENROAD,
        "source_manifest_path": str(run / "common-source-manifest.json"),
        "source_manifest_sha256": config["source_manifest_sha256"],
        "binaries": binaries,
    }
    flow = run / "source/flow"
    profile = {
        "flow_dir": str(flow),
        "source_commit": call(["git", "rev-parse", "HEAD"], flow),
        "makefile_sha256": digest(flow / "Makefile"),
        "eval_tns_sha256": digest(flow / "eval_tns.tcl"),
        "openroad_bin": TOOLS["openroad"],
        "yosys_bin": TOOLS["yosys"],
        "python_bin": "/usr/bin/python3",
        "runtime": {
            "kind": "apptainer",
            "executable": runtime,
            "image": config["image"],
        },
        "toolchain": toolchain,
    }
    write_json(run / "profile.json", profile)
    # Native startup checks need executable host paths; these cannot run EDA.
    wrappers = run / "identity-tools"
    wrappers.mkdir()
    for name in TOOLS:
        wrapper = wrappers / name
        wrapper.write_text(
            '#!/bin/sh\ncase "$1" in -version|-V|--version)\n'
            'printf "%s\\n" '
            + shlex.quote(name + " sha256=" + binaries[name]["sha256"])
            + ';; *) echo "EDA execution must use EF" >&2; exit 1;; esac\n'
        )
        wrapper.chmod(0o755)
    (run / "source/config/env.local.sh").write_text(
        "export OPENROAD_EXE=" + shlex.quote(str(wrappers / "openroad")) + "\n"
        "export YOSYS_EXE=" + shlex.quote(str(wrappers / "yosys")) + "\n"
    )
    toolkit_python = install_toolkit(run, qualified)
    execution = {
        "threads": 8,
        "capacity_memory_bytes": 32 << 30,
        "resources": {"memory_bytes": 24 << 30, "processes": 2048},
        "interpreters": {
            "controller": str(FORMAL / ".venv/bin/python"),
            "toolkits": toolkit_python,
            **{
                name: str(qualified / "envs" / name / "bin/python")
                for name in (
                    "execution-foundation",
                    "data-foundation",
                    "data-interface",
                )
            },
        },
    }
    names = call(["git", "ls-files"], run / "source").splitlines()
    files = {
        name: digest(run / "source" / name)
        for name in names
        if (run / "source" / name).is_file()
    }
    files["config/env.local.sh"] = digest(run / "source/config/env.local.sh")
    write_json(
        run / "source-manifest.json",
        {
            "commit": profile["source_commit"],
            "files": files,
            "tools": binaries,
            "toolchain": toolchain,
            "created_at": now(),
            "model_and_algorithm_changed": False,
        },
    )
    write_json(
        run / "common.json",
        {
            "qualification_root": str(qualified),
            "qualification_sha256": digest(qualified / "u1-acceptance.json"),
            "execution": execution,
            "profile_sha256": digest(run / "profile.json"),
            "toolkit_commit": call(
                ["git", "rev-parse", "HEAD"], WORKSPACE / "toolkits"
            ),
            "wheels": {p.name: digest(p) for p in (run / "wheels").glob("*.whl")},
            "created_at": now(),
        },
    )
    return execution


def configure(run, execution):
    plugins = run / "plugins"
    subprocess.run(
        [
            execution["interpreters"]["toolkits"],
            "-m",
            "eda_toolkits",
            "configure",
            "--output",
            str(plugins),
        ],
        env=environment(),
        check=True,
    )
    return plugins


def precheck(run, execution):
    """One full deterministic native baseline chain, with a separate EF state."""
    from openroad_platform_client import KernelClient
    from run_platform_campaign import gateway_command, port, wait_service

    state = run / "precheck"
    state.mkdir()
    controller_env = environment()
    controller_env["PATH"] = (
        str(Path(execution["interpreters"]["controller"]).parent)
        + os.pathsep
        + controller_env["PATH"]
    )
    controller_env["DRP_SEED"] = "42"
    flow = run / "source/flow"
    subprocess.run(
        ["bash", "run_sequential.sh", "nangate45", "aes", "1", "1"],
        cwd=flow,
        env=controller_env,
        check=True,
        timeout=60,
    )
    profile = run / "profile.json"
    config = flow / "designs/nangate45/aes/config_1.mk"
    sdc = flow / "designs/nangate45/aes/constraint_1.sdc"
    plugins = configure(run, execution)
    number = port()
    client = KernelClient(f"http://127.0.0.1:{number}", timeout=60)
    receipt = {
        "status": "running",
        "jobs": {},
        "started_at": now(),
        "not_a_campaign": True,
    }
    write_json(state / "receipt.json", receipt)
    command = gateway_command(state, plugins, number, execution)
    with (state / "kernel.log").open("x") as log:
        service = subprocess.Popen(command, env=environment(), stdout=log, stderr=log)
        try:
            wait_service(service, number)
            checkpoint = None
            for stage in ("place", "cts", "route_finish", "eval_final"):
                inputs = {
                    "adapter": "a2_stage",
                    "stage": stage,
                    "threads": execution["threads"],
                    "profile_path": "inputs/profile.json",
                }
                staged = []
                for path, destination in [(profile, "inputs/profile.json")] + (
                    []
                    if stage.startswith("eval_")
                    else [
                        (config, "inputs/candidate.mk"),
                        (sdc, "inputs/candidate.sdc"),
                    ]
                ):
                    uploaded = client.upload_input(path.read_bytes())
                    staged.append(
                        {"input_id": uploaded["input_id"], "destination": destination}
                    )
                if checkpoint:
                    inputs["checkpoint_path"] = "inputs/checkpoint.zip"
                    staged.append(
                        {
                            "artifact_id": checkpoint["artifact_id"],
                            "destination": "inputs/checkpoint.zip",
                        }
                    )
                if stage.startswith("eval_"):
                    inputs["evaluation"] = {
                        "cp0_ns": 0.82,
                        "clock_port": "clk",
                        "library_patterns": [
                            str(
                                flow
                                / "platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
                            )
                        ],
                    }
                else:
                    inputs.update(
                        config_path="inputs/candidate.mk",
                        sdc_path="inputs/candidate.sdc",
                    )
                task = {
                    "schema_version": 3,
                    "task_id": "u2-precheck-" + stage,
                    "project_id": "u2-common-precheck",
                    "design_id": "aes",
                    "plugin_id": "openroad-data",
                    "inputs": inputs,
                    "staged_inputs": staged,
                    "labels": {"memory_approval": "manual"},
                    "timeout_seconds": 5400,
                    "resources": {
                        "cpu_cores": execution["threads"],
                        **execution["resources"],
                    },
                }
                job = client.submit(task, idempotency_key=state.name + ":" + stage)[
                    "run"
                ]
                receipt["jobs"][stage] = {"run_id": job["run_id"], "task": task}
                write_json(state / "receipt.json", receipt)
                deadline = time.monotonic() + 5400
                while job["status"] not in {
                    "succeeded",
                    "failed",
                    "cancelled",
                    "timed_out",
                    "lost",
                }:
                    if time.monotonic() > deadline:
                        client.cancel(job["run_id"])
                        raise TimeoutError(stage)
                    time.sleep(0.5)
                    job = client.run(job["run_id"])
                artifacts = client.artifacts(job["run_id"])
                entry = receipt["jobs"][stage]
                entry.update(run=job, artifacts=artifacts)
                for kind, suffix in (
                    ("extractor_receipt", "receipt.json"),
                    ("extractor_log", "log"),
                ):
                    evidence = next((a for a in artifacts if a["kind"] == kind), None)
                    if evidence is not None:
                        client.materialize_artifact(
                            job["run_id"],
                            evidence["artifact_id"],
                            str(state / (stage + "-" + suffix)),
                        )
                write_json(state / "receipt.json", receipt)
                if job["status"] != "succeeded":
                    raise RuntimeError(
                        "Common Flow compatibility check failed: " + stage
                    )
                checkpoint = next(a for a in artifacts if a["kind"] == "flow_archive")
            receipt.update(status="completed", finished_at=now())
            write_json(state / "receipt.json", receipt)
        except Exception as error:
            receipt.update(status="failed", error=str(error), finished_at=now())
            write_json(state / "receipt.json", receipt)
            raise
        finally:
            service.terminate()
            service.wait(timeout=30)


def query(run, execution):
    """Reopen completed state API-only; check every feedback through the SDK."""
    from openroad_platform_client import KernelClient
    from run_platform_campaign import gateway_command, port, wait_service

    output = run / "query-completion"
    output.mkdir()
    kernel_port, data_port = port(), port()
    kernel_url, data_url = (
        f"http://127.0.0.1:{kernel_port}",
        f"http://127.0.0.1:{data_port}",
    )
    commands = [
        gateway_command(run, run / "plugins", kernel_port, execution) + ["--api-only"],
        [
            execution["interpreters"]["data-foundation"],
            "-m",
            "openroad_app_data_foundation",
            "--host",
            "127.0.0.1",
            "--port",
            str(data_port),
            "--db",
            str(run / "data/facts.sqlite"),
            "--kernel-url",
            kernel_url,
            "--no-auto-import",
            "--native-root",
            str(run / "data/native"),
        ],
    ]
    processes = []
    try:
        for name, command, number in zip(
            ("kernel", "data"), commands, (kernel_port, data_port)
        ):
            with (output / (name + ".log")).open("x") as log:
                process = subprocess.Popen(
                    command, env=environment(), stdout=log, stderr=log
                )
            processes.append(process)
            wait_service(process, number)
        client = KernelClient(kernel_url, timeout=60)
        before = client.runs(project_id="a2-flow", limit=500)
        stages = run / "stage-receipts"
        stages.mkdir()
        records = []
        for path in sorted((run / "platform-state").glob("iteration-*/slot-*.json")):
            value = json.loads(path.read_text())
            if path.name.endswith("-feedback.json"):
                continue
            artifact = next(
                a for a in value["artifacts"] if a["kind"] == "extractor_receipt"
            )
            destination = stages / (path.parent.name + "-" + path.name)
            client.materialize_artifact(
                value["run_id"], artifact["artifact_id"], str(destination)
            )
            records.append(
                {
                    "path": str(destination.relative_to(run)),
                    "artifact": artifact,
                    "run_id": value["run_id"],
                }
            )
        write_json(stages / "index.json", records)
        result = subprocess.check_output(
            [
                execution["interpreters"]["data-interface"],
                str(WORKSPACE / "admin/query_campaign_feedback.py"),
                "--run-root",
                str(run),
                "--data-url",
                data_url,
                "--kernel-url",
                kernel_url,
            ],
            env=environment(),
            text=True,
            timeout=180,
        )
        if client.runs(project_id="a2-flow", limit=500) != before:
            raise ValueError("Data verification changed physical run state")
        write_json(
            output / "receipt.json",
            {**json.loads(result), "api_only": True, "original_runs_unchanged": True},
        )
    finally:
        for process in reversed(processes):
            process.terminate()
            process.wait(timeout=30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "precheck", "supervise", "query"])
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--qualification-root", type=Path)
    args = parser.parse_args()
    run = args.run_root.resolve()
    if args.action == "prepare":
        if args.qualification_root is None:
            parser.error("prepare requires --qualification-root")
        prepare(run, args.qualification_root.resolve())
    else:
        common = json.loads((run / "common.json").read_text())
        execution = common["execution"]
        if digest(run / "profile.json") != common["profile_sha256"]:
            raise ValueError("Frozen profile changed")
        if args.action == "supervise":
            if (
                json.loads((run / "precheck/receipt.json").read_text())["status"]
                != "completed"
            ):
                raise ValueError("Complete compatibility precheck first")
            from run_platform_campaign import supervise

            supervise(run, execution)
        elif args.action == "precheck":
            precheck(run, execution)
        else:
            query(run, execution)


if __name__ == "__main__":
    main()
