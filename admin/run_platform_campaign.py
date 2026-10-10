"""Run one frozen full A2 campaign with actual controller fault injection."""

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path

from flow_native_baseline import FORMAL, WORKSPACE, call, digest, now, write_json
from openroad_platform_client import KernelClient
from run_a2_stage_acceptance import capture_environment


def port():
    with socket.socket() as endpoint:
        endpoint.bind(("127.0.0.1", 0))
        return endpoint.getsockname()[1]


def wait_service(process, number):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Service exited before opening its endpoint.")
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", number)) == 0:
                return
        time.sleep(0.1)
    raise TimeoutError("Service failed to become ready.")


def process_identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {
            "pid": pid,
            "start_ticks": fields[19],
            "process_group": int(fields[2]),
            "state": fields[0],
        }
    except (FileNotFoundError, ProcessLookupError):
        return None


def stop_controller(process):
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=30)
    # Reap the whole native publisher group; EF workers belong to the gateway.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        living = [
            row
            for path in Path("/proc").iterdir()
            if path.name.isdigit()
            for row in [process_identity(int(path.name))]
            if row and row["process_group"] == process.pid and row["state"] != "Z"
        ]
        if not living:
            return
        time.sleep(0.1)
    raise RuntimeError("Interrupted controller still has live publishers.")


def prepare(run, reference):
    if run.exists():
        raise RuntimeError(
            "Preserve existing evidence; use a fresh campaign directory."
        )
    if call(["git", "status", "--porcelain"], FORMAL):
        raise RuntimeError(
            "Freeze a committed Flow revision before physical acceptance."
        )
    run.mkdir(parents=True)
    source = run / "source"
    subprocess.run(
        ["git", "clone", "--no-hardlinks", str(FORMAL), str(source)], check=True
    )
    shutil.copy2(
        reference / "source/config/env.local.sh", source / "config/env.local.sh"
    )
    names = call(["git", "ls-files"], source).splitlines()
    files = {name: digest(source / name) for name in names if (source / name).is_file()}
    files["config/env.local.sh"] = digest(source / "config/env.local.sh")
    dependencies = call([str(FORMAL / ".venv/bin/python"), "-m", "pip", "freeze"])
    (run / "installed-requirements.txt").write_text(dependencies + "\n")
    tools = Path("/opt/EDAs/OpenROAD-flow-scripts/versions/20260409/tools/install")
    profile = {
        "flow_dir": str(source / "flow"),
        "source_commit": call(["git", "rev-parse", "HEAD"], source),
        "makefile_sha256": digest(source / "flow/Makefile"),
        "eval_tns_sha256": digest(source / "flow/eval_tns.tcl"),
        "openroad_bin": str(tools / "OpenROAD/bin/openroad"),
        "yosys_bin": str(tools / "yosys/bin/yosys"),
        "python_bin": str(FORMAL / ".venv/bin/python"),
    }
    write_json(run / "profile.json", profile)
    write_json(
        run / "source-manifest.json",
        {
            "commit": profile["source_commit"],
            "files": files,
            "tools": {
                name: digest(Path(profile[name]))
                for name in ("openroad_bin", "yosys_bin")
            },
            "packages_sha256": digest(run / "installed-requirements.txt"),
            "created_at": now(),
            "reference_native": str(reference),
            "model_and_algorithm_changed": False,
        },
    )


def snapshot(client, run):
    backup = run / "source/flow/backup_dir/nangate45/aes"
    events = backup / "llm_usage_events.jsonl"
    ledger = (
        [json.loads(line) for line in events.read_text().splitlines()]
        if events.exists()
        else []
    )
    tasks = {
        str(path.relative_to(run / "platform-state")): json.loads(path.read_text())
        for path in (run / "platform-state").glob("iteration-*/*.json")
    }
    return {
        "runs": client.runs(project_id="a2-flow", limit=500),
        "tasks": tasks,
        "ledger": ledger,
        "manifest_sha256": digest(backup / "campaign_manifest.json"),
        "checkpoint": json.loads((run / "platform-state/campaign.json").read_text()),
    }


def supervise(run):
    receipt_path = run / "receipt.json"
    if receipt_path.exists():
        raise RuntimeError(
            "This supervisor cannot overwrite an earlier campaign receipt."
        )
    source = run / "source"
    manifest = json.loads((run / "source-manifest.json").read_text())
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.update(
        VIRTUAL_ENV=str(FORMAL / ".venv"),
        PATH=str(FORMAL / ".venv/bin") + os.pathsep + environment["PATH"],
        PYTHONNOUSERSITE="1",
        NO_PROXY="127.0.0.1,localhost",
        no_proxy="127.0.0.1,localhost",
        DRP_LLM_TRANSPORT="codex",
        DRP_EXECUTION_BACKEND="platform",
        DRP_PLATFORM_CONFIG=str(run / "platform.json"),
        DRP_CODEX_AUDIT_DIR=str(run / "model-audit"),
        OMP_NUM_THREADS="8",
        OPENBLAS_NUM_THREADS="8",
        MKL_NUM_THREADS="8",
    )
    for name in list(environment):
        if name.startswith("DRP_ACCEPTANCE_"):
            environment.pop(name)
    kernel_port, data_port = port(), port()
    kernel_url, data_url = (
        f"http://127.0.0.1:{kernel_port}",
        f"http://127.0.0.1:{data_port}",
    )
    write_json(
        run / "platform.json",
        {
            "kernel_url": kernel_url,
            "data_url": data_url,
            "state_root": str(run / "platform-state"),
            "profile_path": str(run / "profile.json"),
            "threads": 8,
            "timeout_seconds": 5400,
        },
    )
    plugins = run / "plugins"
    subprocess.run(
        [
            str(WORKSPACE / "toolkits/.venv/bin/python"),
            "-m",
            "eda_toolkits",
            "configure",
            "--output",
            str(plugins),
        ],
        env=environment,
        check=True,
    )
    initial = capture_environment(run / "environment-start", environment)
    kernel_command = [
        str(WORKSPACE / "execution-foundation/.venv/bin/python"),
        "-m",
        "openroad_platform_gateway",
        "--state-root",
        str(run / "kernel"),
        "--plugins-root",
        str(plugins),
        "--admissions-root",
        str(WORKSPACE / "execution-foundation/admissions"),
        "--port",
        str(kernel_port),
        "--input-root",
        str(run),
        "--capacity-cpu-cores",
        "8",
        "--capacity-memory-bytes",
        str(12 << 30),
    ]
    data_command = [
        str(WORKSPACE / "data-foundation/.venv/bin/python"),
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
    ]
    command = [
        "./run.sh",
        "-p",
        "nangate45",
        "-d",
        "aes",
        "-o",
        "TNS_EVAL",
        "-i",
        "2",
        "-r",
        "3",
        "-k",
        "1",
        "-s",
        "elitist",
        "-A",
        "-P",
        "-F",
        "--seed",
        "42",
        "--cpus",
        "24",
        "--max-concurrent-runs",
        "1",
        "-t",
        "90m",
    ]
    receipt = {
        "status": "starting",
        "started_at": now(),
        "source_commit": manifest["commit"],
        "kernel_command": kernel_command,
        "data_command": data_command,
        "command": command,
        "epochs": [],
        "wall_budget_seconds": 10800,
    }
    write_json(receipt_path, receipt)
    processes, controller = [], None
    client = KernelClient(kernel_url, timeout=60)
    deadline = time.monotonic() + receipt["wall_budget_seconds"]
    with (
        (run / "kernel.log").open("x") as kernel_log,
        (run / "data.log").open("x") as data_log,
        (run / "campaign.log").open("x") as campaign_log,
    ):
        try:
            kernel = subprocess.Popen(
                kernel_command, env=environment, stdout=kernel_log, stderr=kernel_log
            )
            processes.append(kernel)
            wait_service(kernel, kernel_port)
            data = subprocess.Popen(
                data_command, env=environment, stdout=data_log, stderr=data_log
            )
            processes.append(data)
            wait_service(data, data_port)
            receipt.update(status="running", gateway_pid=kernel.pid, data_pid=data.pid)
            write_json(receipt_path, receipt)
            gates = [
                (
                    "DRP_ACCEPTANCE_SUBMIT_GATE",
                    "1:1:place",
                    "submit-acceptance-gate.json",
                ),
                (
                    "DRP_ACCEPTANCE_MODEL_GATE",
                    "1:cts:direct_parameter_proposal",
                    "model-acceptance-gate.json",
                ),
                ("DRP_ACCEPTANCE_GATE", "1:2", "acceptance-gate.json"),
                ("DRP_ACCEPTANCE_GATE", "1:7", "acceptance-gate.json"),
                (None, None, None),
            ]
            for epoch, (gate_name, gate_value, marker_name) in enumerate(gates):
                epoch_env = dict(environment)
                if gate_name:
                    epoch_env[gate_name] = gate_value
                epoch_command = list(command)
                if epoch:
                    epoch_command[epoch_command.index("-F")] = "--resume"
                marker = (
                    None
                    if marker_name is None
                    else run / "platform-state" / marker_name
                )
                if marker and marker.exists():
                    marker.unlink()
                controller = subprocess.Popen(
                    epoch_command,
                    cwd=source,
                    env=epoch_env,
                    stdout=campaign_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                identity = process_identity(controller.pid)
                row = {
                    "epoch": epoch,
                    "started_at": now(),
                    "command": epoch_command,
                    "controller": identity,
                    "gate": gate_value,
                    "status": "running",
                }
                receipt["epochs"].append(row)
                write_json(receipt_path, receipt)
                while controller.poll() is None:
                    if time.monotonic() > deadline:
                        raise TimeoutError(
                            "Full campaign exhausted its wall-clock budget."
                        )
                    if marker and marker.exists():
                        evidence = json.loads(marker.read_text())
                        row["gate_evidence"] = evidence
                        before = snapshot(client, run)
                        write_json(run / f"interruption-{epoch}-before.json", before)
                        if epoch == 0:
                            lost = json.loads(Path(evidence["record_path"]).read_text())
                            if "run_id" in lost or lost["status"] != "prepared":
                                raise RuntimeError(
                                    "Submit-loss gate did not cover the intended window."
                                )
                        stop_controller(controller)
                        row.update(
                            status="interrupted",
                            exit_code=controller.returncode,
                            stopped_at=now(),
                            process_group_stopped=True,
                        )
                        write_json(
                            run / f"interruption-{epoch}-after.json",
                            snapshot(client, run),
                        )
                        write_json(receipt_path, receipt)
                        print(
                            json.dumps(
                                {"epoch": epoch, "actual_interruption": gate_value}
                            ),
                            flush=True,
                        )
                        break
                    time.sleep(0.5)
                if row["status"] == "running":
                    row.update(
                        status="completed" if controller.returncode == 0 else "failed",
                        exit_code=controller.returncode,
                        finished_at=now(),
                    )
                    write_json(receipt_path, receipt)
                    if gate_name or controller.returncode != 0:
                        raise RuntimeError(
                            "Campaign exited before the required gate or failed."
                        )
                controller = None
            write_json(run / "final-execution.json", snapshot(client, run))
            final = capture_environment(run / "environment-finish", environment)
            receipt.update(
                status="completed",
                exit_code=0,
                finished_at=now(),
                source_changed=[
                    name
                    for name, sha in manifest["files"].items()
                    if digest(source / name) != sha
                ],
                execution_environment_unchanged=all(
                    initial[name]["files"] == final[name]["files"]
                    and initial[name]["packages"] == final[name]["packages"]
                    for name in initial
                ),
            )
            write_json(receipt_path, receipt)
        except Exception as error:
            receipt.update(
                status="failed",
                error=type(error).__name__ + ": " + str(error),
                finished_at=now(),
            )
            write_json(receipt_path, receipt)
            raise
        finally:
            if controller is not None and controller.poll() is None:
                stop_controller(controller)
            # These are exclusively this experiment's newly created services.
            for process in reversed(processes):
                process.terminate()
                process.wait(timeout=120)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "supervise"])
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument(
        "--reference",
        type=Path,
        default=WORKSPACE / "var/flow-agent/p1-native-20261010-retry2",
    )
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.run_root.resolve(), args.reference.resolve())
    else:
        supervise(args.run_root.resolve())
