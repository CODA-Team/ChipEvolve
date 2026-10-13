"""One EF-owned persistent ECO session, preserving the native interactive loop."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path


def submit(profile_path: Path) -> dict:
    from eda_ai_client import EdaAiClient
    from openroad_platform_client import KernelClient

    profile = json.loads(profile_path.read_text())
    source = Path(__file__).resolve().parents[1]
    facts = EdaAiClient(data_url=profile["data_url"], kernel_url=profile["kernel_url"])
    context = {
        "scope": facts.resolve_scope(snapshot_id=profile["snapshot_id"]),
        "summary": facts.get_stage_summary(profile["snapshot_id"]),
        "metrics": facts.get_metrics(snapshot_id=profile["metrics_snapshot_id"]),
    }
    state = Path(profile["state_root"])
    state.mkdir(parents=True, exist_ok=True)
    (state / "input-context.json").write_text(json.dumps(context, indent=2) + "\n")
    staged = [{"source": str(profile_path), "destination": "inputs/profile.json"}]
    staged += [
        {"artifact_id": aid, "destination": "inputs/6_final." + suffix}
        for suffix, aid in profile["input_artifacts"].items()
    ]
    spec = {
        "schema_version": 3,
        "task_id": profile["experiment_id"] + "-eco-session",
        "project_id": "timing-eco",
        "design_id": "gcd",
        "experiment_id": profile["experiment_id"],
        "plugin_id": "openroad-data",
        "labels": {
            "memory_approval": "manual",
            "parent_run_id": profile["parent_run_id"],
        },
        "inputs": {
            "adapter": "command",
            "extractor_command": [
                profile["python"],
                str(source / "src/platform_execution.py"),
                "leaf",
                "--profile",
                "inputs/profile.json",
            ],
            "native_extra_paths": [
                "session-output/final_eco." + ext
                for ext in ("odb", "def", "v", "sdc", "spef")
            ],
        },
        "staged_inputs": staged,
        "timeout_seconds": profile.get("timeout_seconds", 14400),
        "resources": {"cpu_cores": 8, "memory_bytes": 24 << 30, "processes": 2048},
        "max_attempts": 1,
        "expected_artifacts": ["data_snapshot"],
    }
    client = KernelClient(profile["kernel_url"], timeout=60)
    (state / "spec.json").write_text(json.dumps(spec, indent=2) + "\n")
    response = client.submit(spec, idempotent=True, idempotency_key=spec["task_id"])
    (state / "submission.json").write_text(json.dumps(response, indent=2) + "\n")
    run_id = response["run"]["run_id"]
    while True:
        run = client.run(run_id)
        if run["status"] in {"succeeded", "failed", "cancelled", "timed_out", "lost"}:
            break
        time.sleep(2)
    record = {
        "run": run,
        "artifacts": client.artifacts(run_id),
        "resources": client.resources(run_id),
    }
    (state / "execution.json").write_text(json.dumps(record, indent=2) + "\n")
    if run["status"] != "succeeded":
        raise RuntimeError("EF ECO session failed: " + run_id)
    return record


def leaf(profile_path: Path) -> int:
    profile = json.loads(profile_path.read_text())
    source = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment.update(profile["environment"])
    environment.update(
        DESIGN_DIR=str(Path.cwd() / "inputs"), TOP="6_final", TIMINGECO_EF_LEAF="1"
    )
    code = subprocess.call(
        [profile["python"], str(source / "src/main_orch.py")],
        cwd=source,
        env=environment,
    )
    native_code = code
    if environment.get("TIMINGECO_MODEL_BACKEND") == "codex" and code == 0:
        receipts = list((source / "prompts/dynamic/codex_logs").glob("*/receipt.json"))
        if not receipts:
            print(
                "ECO has no successful model decision; native no-op is not a passing session.",
                flush=True,
            )
            code = 2
    if code == 0:
        # Upstream keeps its authoritative best routed ODB in dynamic snapshots.
        # Export it deterministically; some upstream early-stop paths omit DEF/V.
        best = source / "prompts/dynamic/snapshots/best_drt.odb"
        destination = source / "outputs"
        script = Path.cwd() / "export_best.tcl"
        pdk = Path(environment["ASAP7_PDK"])
        libraries = [
            pdk
            / "lib/NLDM"
            / ("asap7sc7p5t_" + group + "_" + vt + "_FF_nldm_" + version)
            for vt in ("RVT", "LVT", "SLVT")
            for group, version in (
                ("AO", "211120.lib.gz"),
                ("INVBUF", "220122.lib.gz"),
                ("OA", "211120.lib.gz"),
                ("SIMPLE", "211120.lib.gz"),
                ("SEQ", "220123.lib"),
            )
        ]
        script.write_text(
            "\n".join(
                [
                    *[f"read_liberty {{{path}}}" for path in libraries],
                    f"read_db {{{best}}}",
                    f"read_sdc {{{Path.cwd() / 'inputs/6_final.sdc'}}}",
                    f"write_db {{{destination / 'final_eco.odb'}}}",
                    f"write_def {{{destination / 'final_eco.def'}}}",
                    f"write_verilog {{{destination / 'final_eco.v'}}}",
                    f"write_sdc {{{destination / 'final_eco.sdc'}}}",
                    "exit",
                ]
            )
            + "\n"
        )
        code = subprocess.call(
            [environment["OPENROAD_BIN"], "-exit", str(script)], env=environment
        )
    output = Path.cwd() / "query-data"
    output.mkdir()
    for folder in ("outputs", "prompts/dynamic"):
        shutil.copytree(source / folder, output / folder, dirs_exist_ok=True)
    raw = Path.cwd() / "session-output"
    shutil.copytree(source / "outputs", raw, dirs_exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "evidence_only": True,
                "returncode": code,
                "native_returncode": native_code,
                "parent_run_id": profile["parent_run_id"],
                "input_snapshot_id": profile["snapshot_id"],
                "session_owned_by": "Execution Foundation",
            },
            indent=2,
        )
        + "\n"
    )
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["submit", "leaf"])
    parser.add_argument("--profile", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "leaf":
        raise SystemExit(leaf(args.profile))
    print(json.dumps(submit(args.profile.resolve())["run"]))


if __name__ == "__main__":
    main()
