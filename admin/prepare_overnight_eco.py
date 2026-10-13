"""Freeze a private ECO run consuming an existing public design snapshot."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from run_dplevolve_native import digest, write_json

ROOT = Path(__file__).resolve().parents[1]


def prepare(state: Path, key: str, data_key: str) -> Path:
    run = state / "agents" / key
    run.mkdir(parents=True, exist_ok=False)
    source = run / "source"
    shutil.copytree(
        ROOT / "timing-eco-agent",
        source,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache"),
    )
    runtime = json.loads((state / "runtime.json").read_text())
    data = json.loads((state / (data_key + "-data.json")).read_text())
    objects = data["opendb"]
    artifacts = {
        Path(a["store_key"]).suffix[1:]: a["artifact_id"]
        for a in objects["execution"]["artifacts"]
        if a["kind"] in {"raw_design_database", "raw_constraints", "raw_parasitics"}
    }
    if set(artifacts) != {"odb", "sdc", "spef"}:
        raise ValueError("ECO needs one actual ODB, matching SDC and SPEF")
    wrapper = run / "openroad"
    wrapper.write_text(
        "#!/usr/bin/python3\nimport os,sys\n"
        + "args="
        + repr(
            [
                "apptainer",
                "exec",
                "--cleanenv",
                "--no-home",
                "--bind",
                str(state) + ":" + str(state),
                "--pwd",
                str(source),
                runtime["image"],
                "env",
            ]
        )
        + "\n"
        + "for key in ('ASAP7_PDK','DESIGN_DIR','TOP','BACKTRACE_ODB'):\n"
        + " if key in os.environ: args.append(key+'='+os.environ[key])\n"
        + "args += ['/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad']+sys.argv[1:]\n"
        + "os.execvp(args[0],args)\n"
    )
    wrapper.chmod(0o755)
    codex = shutil.which("codex")
    if not codex:
        raise FileNotFoundError("Use the installed official Codex CLI")
    profile = {
        "kernel_url": runtime["kernel_url"],
        "data_url": runtime["data_url"],
        "state_root": str(run / "session"),
        "snapshot_id": objects["snapshot_id"],
        "metrics_snapshot_id": data["orfs"]["snapshot_id"],
        "input_artifacts": artifacts,
        "parent_run_id": objects["execution"]["run"]["labels"]["analysis_of_run_id"],
        "python": str(ROOT / "timing-eco-agent/.venv/bin/python"),
        "experiment_id": state.name + "-" + key,
        "environment": {
            "OPENROAD_BIN": str(wrapper),
            "ASAP7_PDK": str(source / "asap7"),
            "ASAP7_PDK_LIB": str(source / "asap7/lib/NLDM"),
            "TIMINGECO_LIB_CORNER": "FF",
            "TIMINGECO_MODEL_BACKEND": "codex",
            "TIMINGECO_CODEX_BIN": codex,
            "DRT_EVERY_ITER": "1",
            "OMP_NUM_THREADS": "8",
            "OPENBLAS_NUM_THREADS": "8",
            "PYTHONNOUSERSITE": "1",
            "MPLBACKEND": "Agg",
            "PATH": str(ROOT / "timing-eco-agent/.venv/bin")
            + ":"
            + str(Path(codex).parent)
            + ":"
            + os.environ["PATH"],
        },
        "toolchain": runtime["toolchain"],
        "source_files": {
            str(p.relative_to(source)): digest(p) for p in (source / "src").glob("*.py")
        },
    }
    # EF intentionally strips the host environment. Carry only the local model
    # connection settings; no credential files are staged or copied.
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    ):
        if name in os.environ:
            profile["environment"][name] = os.environ[name]
    path = run / "profile.json"
    write_json(path, profile)
    environment = dict(os.environ, **profile["environment"])
    with (run / "liberty-reference.log").open("w") as log:
        subprocess.run(
            [profile["python"], str(source / "src/extract_liberty_tables.py")],
            env=environment,
            stdout=log,
            stderr=log,
            check=True,
        )
    command = [
        profile["python"],
        str(source / "src/platform_execution.py"),
        "submit",
        "--profile",
        str(path),
    ]
    with (run / "session.log").open("w") as log:
        process = subprocess.Popen(
            command, env=environment, stdout=log, stderr=log, start_new_session=True
        )
    write_json(
        run / "launch.json",
        {"pid": process.pid, "command": command, "started_epoch": time.time()},
    )
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--data-key", required=True)
    args = parser.parse_args()
    print(prepare(args.state.resolve(), args.key, args.data_key))
