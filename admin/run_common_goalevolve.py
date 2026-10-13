"""Run authorized U4 native phases through its own EF service and fixed budget."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from qualify_common_toolchain import environment, http
from run_dplevolve_native import digest, now, write_json
from run_goalevolve_native import stop_native_tree

ROOT = Path(__file__).resolve().parents[1]
U1 = ROOT / "var/toolchains/common-u1-20261012-retry6"


def host_environment(profile: dict[str, Any]) -> dict[str, str]:
    env = environment()
    env.update(
        GOALEVOLVE_PLATFORM_PROFILE=profile["profile_path"],
        PYTHONPYCACHEPREFIX=str(Path(profile["state_root"]) / "pycache"),
    )
    env["PATH"] = str(Path(profile["agent_python"]).parent) + os.pathsep + env["PATH"]
    return env


def start_service(state: Path) -> None:
    if (state / "service.json").exists():
        raise FileExistsError("Existing service receipt; inspect before restart")
    profile = json.loads((state / "config.json").read_text())
    python = profile["client_python"]
    subprocess.run(
        [
            python,
            "-m",
            "eda_toolkits",
            "configure",
            "--output",
            str(state / "plugins"),
            "--image",
            profile["image"],
        ],
        env=environment(),
        check=True,
    )
    configure_adapter_ceiling(state, profile)
    capacity = profile["service_capacity"]
    command = [
        python,
        "-m",
        "openroad_platform_gateway",
        "--state-root",
        str(state / "kernel"),
        "--plugins-root",
        str(state / "plugins"),
        "--admissions-root",
        str(U1 / "dependency-sources/execution-foundation/admissions"),
        "--host",
        "127.0.0.1",
        "--port",
        profile["kernel_url"].rsplit(":", 1)[1],
        "--input-root",
        profile["state_root"],
        "--capacity-cpu-cores",
        str(capacity["cpu_cores"]),
        "--capacity-memory-bytes",
        str(capacity["memory_bytes"]),
        "--platform-fraction",
        "1.0",
        "--worker-concurrency",
        str(capacity["workers"]),
    ]
    with (state / "kernel.log").open("a") as log:
        process = subprocess.Popen(
            command, env=environment(), stdout=log, stderr=log, start_new_session=True
        )
    write_json(
        state / "service.json",
        {
            "pid": process.pid,
            "command": command,
            "kernel_url": profile["kernel_url"],
            "started_at": now(),
            "service_capacity": capacity,
            "adapter_timeout_ceiling_seconds": profile[
                "adapter_timeout_ceiling_seconds"
            ],
        },
    )
    deadline = time.monotonic() + 60
    while True:
        try:
            http(profile["kernel_url"] + "/kernel/health")
            return
        except OSError:
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("U4 EF startup failed; see kernel.log")
            time.sleep(0.2)


def configure_adapter_ceiling(state: Path, profile: dict[str, Any]) -> None:
    """Keep the native command timeout below this experiment's adapter cap."""
    path = state / "plugins/openroad-data/openroad-data.plugin.json"
    manifest = json.loads(path.read_text())
    manifest["default_timeout_seconds"] = profile["adapter_timeout_ceiling_seconds"]
    # U4 uses private source/build directories; EF owns its resource admission.
    # The optional host lease would also serialize version queries and parsers.
    manifest.setdefault("environment", {}).pop("EDA_ACTIVITY_LOCK", None)
    write_json(path, manifest)


def cancel_active(state: Path, profile: dict[str, Any]) -> list[str]:
    cancelled = []
    for submission in (state / "operations").glob("*/submission.json"):
        run_id = json.loads(submission.read_text())["run_id"]
        row = http(profile["kernel_url"] + "/kernel/runs/" + run_id)["run"]
        if row["status"] not in {
            "succeeded",
            "failed",
            "cancelled",
            "timed_out",
            "lost",
        }:
            http(profile["kernel_url"] + "/kernel/runs/" + run_id + "/cancel", {})
            cancelled.append(run_id)
    return cancelled


def step(state: Path, name: str, command: list[str], timeout: int) -> None:
    profile = json.loads((state / "config.json").read_text())
    folder = state / "steps" / name
    folder.mkdir(parents=True, exist_ok=False)
    receipt: dict[str, Any] = {
        "command": command,
        "started_at": now(),
        "status": "running",
        "profile_sha256": digest(state / "config.json"),
    }
    write_json(folder / "receipt.json", receipt)
    with (folder / "output.log").open("x") as log:
        process = subprocess.Popen(
            command,
            cwd=profile["agent_root"],
            env=host_environment(profile),
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        receipt["pid"] = process.pid
        write_json(folder / "receipt.json", receipt)
        try:
            code = process.wait(
                timeout=min(timeout, max(1, profile["deadline_epoch"] - time.time()))
            )
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            stop_native_tree(process)
            receipt.update(
                status="cancelled",
                cancelled_runs=cancel_active(state, profile),
                ended_at=now(),
            )
            write_json(folder / "receipt.json", receipt)
            raise
    receipt.update(
        status="succeeded" if code == 0 else "failed", exit_code=code, ended_at=now()
    )
    write_json(folder / "receipt.json", receipt)
    if code:
        raise RuntimeError("Native phase failed: " + name)


def prepare_replay(
    state: Path, candidate_path: Path | None = None
) -> tuple[dict[str, Any], Path]:
    """Freeze a real native result and a source-only independent build input."""
    profile = json.loads((state / "config.json").read_text())
    campaign = state / "campaigns/aes_cipher_top/u4/campaign"
    if candidate_path:
        candidate_path = candidate_path.resolve()
        candidate_path.relative_to(campaign / "rounds")
        round_root = candidate_path.parents[3]
    else:
        rounds = sorted(campaign.glob("rounds/round_*/round.json"))
        if not rounds:
            raise ValueError("No completed native round")
        round_root = rounds[-1].parent
    summary_path = round_root / "round.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    candidates = []
    candidate_paths = (
        [candidate_path]
        if candidate_path
        else list((round_root / "students").glob("*/artifacts/candidate.json"))
    )
    for path in candidate_paths:
        row = json.loads(path.read_text())
        if (
            row["evaluation_error"] is None
            and row["implementation_diff"]
            and all(check["passed"] for check in row["checks"])
            and float(row["metrics"].get("drv_count", -1)) == 0
        ):
            candidates.append((path, row))
    if candidate_path:
        candidates = [
            (path, row)
            for path, row in candidates
            if path.resolve() == candidate_path.resolve()
        ]
    if not candidates:
        raise ValueError("No genuinely new, valid native candidate to replay")
    promoted = summary.get("promoted_student")
    path, row = next(
        ((path, row) for path, row in candidates if row["student_id"] == promoted),
        min(candidates, key=lambda pair: pair[1]["student_id"]),
    )
    folder = state / "replay"
    folder.mkdir(exist_ok=False)
    code = r"""from pathlib import Path
import json, os
from dataclasses import replace
from goalevolve.config import load_config
from goalevolve.core.contracts import build_contract
from goalevolve.evaluation.contest2026 import Contest2026Config, Contest2026OpenROADEvaluator, _project_toolchain
from goalevolve.execution.execution import ExecutionPolicy
from goalevolve.core.models import Parent
from goalevolve.evaluation.contest2026 import _tree_hash
from goalevolve.execution.workspace import clone_source_tree
p=json.load(open(os.environ['GOALEVOLVE_PLATFORM_PROFILE']))
s=Path(p['state_root']); folder=s/'replay'
receipt=json.load(open(folder/'replay.json'))
candidate=json.load(open(receipt['candidate_json']))
source=Path(candidate['artifacts']['candidate_source'])
cfg=load_config(s/'campaigns/aes_cipher_top/u4/config/evolve.json')
assert _tree_hash(source,allowed_roots=cfg.allowed_patch_roots)==candidate['source_commit'], 'Candidate source no longer matches its measured content'
snapshot=folder/'snapshot/source'; clone_source_tree(source,snapshot)
assert _tree_hash(snapshot,allowed_roots=cfg.allowed_patch_roots)==candidate['source_commit']
private=folder/'private-source'; clone_source_tree(snapshot,private)
replay_cfg=replace(cfg,source_root=snapshot,build_seed_root=None)
contract=build_contract(design=cfg.design,baseline_metrics=cfg.baseline_metrics,target_metrics=cfg.target_metrics,weights=cfg.metric_weights,hard_metrics=cfg.hard_metrics,maximize_metrics=cfg.maximize_metrics)
tool_env,cmake_args=_project_toolchain()
evaluator=Contest2026OpenROADEvaluator(Contest2026Config(design=cfg.design,benchmark_root=cfg.benchmark_root,source_seed=snapshot,build_seed_root=None,allowed_patch_roots=cfg.allowed_patch_roots,require_cpp_patch=cfg.require_cpp_patch,power_reclaim_phase=cfg.power_reclaim_phase,power_reclaim_proportion_percent=cfg.power_reclaim_proportion_percent,power_reclaim_max_moves=cfg.power_reclaim_max_moves,power_stage_tns_ceiling_ns=cfg.power_stage_tns_ceiling_ns,build_jobs=cfg.build_jobs,execution_policy=ExecutionPolicy(cfg.command_timeout_s,cfg.command_retries,cfg.min_free_gb),toolchain_environment=tool_env,toolchain_cmake_args=cmake_args))
parent=Parent('u4_independent_replay',candidate['metrics'],candidate['source_commit'],candidate['source_commit'],0.0)
hypothesis=candidate['hypothesis']
measurement=evaluator.evaluate_parent(contract=contract,parent=parent,source=private,output=folder/'measurement',optimization_mode=hypothesis['evaluation_mode'],timing_recipe_id=hypothesis['timing_recipe_id'])
result=folder/'measurement.json';result.write_text(json.dumps(measurement,indent=2)+'\n')
receipt.update(snapshot=str(snapshot),snapshot_source_commit=_tree_hash(snapshot,allowed_roots=cfg.allowed_patch_roots),private_source=str(private),measurement_json=str(result))
(folder/'replay.json').write_text(json.dumps(receipt,indent=2)+'\n')
assert measurement['ok'], measurement
assert float(measurement['metrics']['drv_count'])==0, measurement
"""
    script = folder / "run.py"
    script.write_text(code)
    write_json(
        folder / "replay.json",
        {
            "candidate_json": str(path),
            "student_id": row["student_id"],
            "source_commit": row["source_commit"],
            "native_promoted_student": promoted,
            "used_build_donor": False,
            "native_round_completed_at_selection": summary_path.exists(),
            "selection_for_replay": (
                "explicit valid engineering witness; does not change native promotion"
                if candidate_path
                else "native promoted candidate when valid, otherwise first valid candidate; does not change native promotion"
            ),
        },
    )
    return profile, script


def run(
    state: Path, phase: str, name: str | None, *, candidate_path: Path | None = None
) -> None:
    profile = json.loads((state / "config.json").read_text())
    python = profile["agent_python"]
    campaign = state / "campaigns/aes_cipher_top/u4"
    if phase == "build":
        code = 'from pathlib import Path; from goalevolve.execution.execution import *; import os,json; p=json.load(open(os.environ["GOALEVOLVE_PLATFORM_PROFILE"])); s=Path(p["source_seed"]); r=ResilientCommandRunner(ExecutionPolicy(timeout_s=5400,retries=1,min_free_gb=20)); a=r.run(command=["cmake","-S",str(s),"-B",str(s/"build"),"-DCMAKE_BUILD_TYPE=Release","-DCMAKE_SUPPRESS_REGENERATION=ON",*p["cmake_args"]],cwd=s,output_log=s.parent/"configure.log"); assert a.ok,a; b=r.run(command=["cmake","--build",str(s/"build"),"--target","openroad","--parallel","8"],cwd=s,output_log=s.parent/"build.log"); assert b.ok,b'
        command = [python, "-c", code]
    elif phase == "ast":
        command = [
            python,
            "-c",
            'from pathlib import Path; import os,json; from goalevolve.planning.repository_graph import RepositoryGraphIndex; p=json.load(open(os.environ["GOALEVOLVE_PLATFORM_PROFILE"])); g=RepositoryGraphIndex(state_root=Path(p["state_root"])/"ast-preparation").build_p0(); print(json.dumps({"source_hash":g.source_hash,"files":len(g.files),"symbols":len(g.symbols),"root":str(g.artifact_root)}))',
        ]
    elif phase == "model-smoke":
        code = 'from pathlib import Path; import os,json; from goalevolve.agents.codex_runtime import *; p=json.load(open(os.environ["GOALEVOLVE_PLATFORM_PROFILE"])); s=Path(p["state_root"]); r=PersistentCodexRunner(CodexRuntimeConfig(model="gpt-6.1-sol",reasoning_effort="xhigh",retries=3,timeout_s=1800)); t=r.run(state_root=s/"model-smoke",identity="teacher",operation_id="u4_smoke",cwd=s/"model-smoke",artifact_root=s/"model-smoke/turn",prompt="Do not run tools or inspect files. Return exactly {\\"u4_model_smoke\\":true} as JSON."); print(json.dumps(t.to_dict())); assert t.ok,t'
        (state / "model-smoke").mkdir(exist_ok=True)
        command = [python, "-c", code]
    elif phase == "replay":
        _, script = prepare_replay(state, candidate_path)
        command = [python, str(script)]
    elif phase == "init":
        command = [
            python,
            "-m",
            "goalevolve.cli",
            "p0",
            "init",
            "--design",
            "aes_cipher_top",
            "--run-id",
            "u4",
            "--output-root",
            str(state / "campaigns"),
            "--planning-mode",
            "ast_graph",
            "--max-rounds",
            "1",
        ]
    elif phase in {"baseline", "evolve"}:
        command = [
            python,
            "-m",
            "goalevolve.cli",
            "p0",
            "baseline" if phase == "baseline" else "run",
            "--campaign",
            str(campaign),
        ]
        if phase == "evolve":
            command += ["--rounds", "1"]
    else:
        raise ValueError("Unknown phase")
    step(state, name or phase, command, 7200 if phase != "evolve" else 18000)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument(
        "phase",
        choices=(
            "service",
            "build",
            "model-smoke",
            "ast",
            "init",
            "baseline",
            "evolve",
            "replay",
        ),
    )
    parser.add_argument("--name")
    parser.add_argument("--candidate", type=Path)
    args = parser.parse_args()
    state = args.state.resolve()
    if args.phase == "service":
        start_service(state)
    else:
        if args.candidate and args.phase != "replay":
            parser.error("--candidate is only used with replay")
        run(state, args.phase, args.name, candidate_path=args.candidate)


if __name__ == "__main__":
    main()
