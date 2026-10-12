"""Run frozen A2 scripts with explicitly identified tools inside a local image."""

import hashlib
import json
import os
import subprocess
from pathlib import Path


def binary_identity(profile):
    """Inspect the tools that the physical stage will actually execute."""
    runtime = profile["runtime"]
    if runtime["kind"] != "apptainer":
        raise ValueError("unsupported A2 runtime")
    declared = profile["toolchain"]
    manifest = Path(declared["source_manifest_path"])
    if (
        hashlib.sha256(manifest.read_bytes()).hexdigest()
        != declared["source_manifest_sha256"]
    ):
        raise ValueError("common source manifest changed")
    binaries = declared["binaries"]
    for name in ("openroad", "yosys"):
        if profile[name + "_bin"] != binaries[name]["path"]:
            raise ValueError("A2 command differs from the declared binary: " + name)
    script = (
        "import hashlib,json;from pathlib import Path;"
        'paths=json.loads(__import__("sys").argv[1]);'
        'print(json.dumps({name:{"path":path,"sha256":hashlib.sha256('
        "Path(path).read_bytes()).hexdigest()} for name,path in paths.items()}))"
    )
    command = [
        runtime["executable"],
        "exec",
        "--cleanenv",
        "--containall",
        runtime["image"],
        "/usr/bin/python3",
        "-c",
        script,
        json.dumps({name: row["path"] for name, row in binaries.items()}),
    ]
    observed = json.loads(
        subprocess.check_output(
            command, env=runtime_environment(), text=True, timeout=60
        )
    )
    if observed != binaries:
        raise ValueError("actual common tools differ from the frozen profile")
    return {**declared, "binaries": observed, "runtime": runtime}


def runtime_environment():
    """Do not forward model credentials or host container overrides to EDA."""
    return {
        name: value
        for name, value in os.environ.items()
        if name in {"HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL", "PATH"}
    }


def stage_command(command, workspace, profile, environment):
    runtime = profile["runtime"]
    scratch = workspace / "scratch"
    scratch.mkdir(exist_ok=True)
    args = [
        runtime["executable"],
        "exec",
        "--cleanenv",
        "--containall",
        "--bind",
        f"{Path(profile['flow_dir']).resolve()}:{profile['flow_dir']}:ro",
        "--bind",
        f"{workspace}:{workspace}",
        "--bind",
        f"{scratch}:/tmp",
        "--pwd",
        str(workspace),
    ]
    names = (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "PYTHONNOUSERSITE",
        "CP0",
        "CLK_PORT",
        "LIB_FILES",
        "ODB_PATH",
        "SPEF_PATH",
    )
    for name in names:
        if name in environment:
            args.extend(["--env", name + "=" + environment[name]])
    args.extend([runtime["image"], *command])
    return args
