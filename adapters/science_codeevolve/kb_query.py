"""Compile a compact, authoritative packet for loop-driven Codex turns."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ModuleNotFoundError:
    for candidate in (
        "/opt/conda/miniforge3/envs/dreamplace/bin/python",
        "/opt/conda/miniforge3/bin/python",
        "python3",
        "python",
    ):
        resolved = shutil.which(candidate)
        if not resolved or resolved == sys.executable:
            continue
        probe = subprocess.run([resolved, "-c", "import yaml"], capture_output=True)
        if probe.returncode == 0:
            os.execv(resolved, [resolved, __file__, *sys.argv[1:]])
    raise


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text())


def build_packet(problem_dir: Path, out_dir: Path) -> Dict[str, Any]:
    problem = load_yaml(problem_dir / "problem.yaml")
    repo_root = Path(__file__).resolve().parents[3]
    if not (
        (repo_root / "flow").is_dir()
        and (repo_root / "tools" / "OpenROAD").is_dir()
        and (repo_root / "evolve_agent").is_dir()
    ):
        env_root = os.environ.get("ORFS_ROOT")
        if env_root:
            repo_root = Path(env_root).resolve()
    if not (
        (repo_root / "flow").is_dir()
        and (repo_root / "tools" / "OpenROAD").is_dir()
        and (repo_root / "evolve_agent").is_dir()
    ):
        raise SystemExit(
            "kb_query.py must run inside an ORFS workspace with this repo mounted as evolve_agent/. "
            "Re-run from the mounted workspace or set ORFS_ROOT to that workspace."
        )
    kb_root = repo_root / "evolve_agent" / "knowledge"

    packet = {
        "run_id": "TODO_FILL_RUN_ID",
        "problem": problem["name"],
        "objective": {
            "primary": problem["objective"]["primary"],
            "guardrails": problem["objective"]["guardrails"],
        },
        "selected_track": problem["evaluation_track"],
        "selected_patch_surface": {
            "file": problem["patch_surface"][0],
            "allowed_functions_or_regions": [
                "negotiation cost / history / search / refinement"
            ],
        },
        "outer_loop_contract": {
            "owns": [
                "flow_variant selection",
                "snapshot validation",
                "build",
                "evaluator",
                "scoring",
                "checkpointing",
            ],
            "codex_should_only": [
                "read the packet",
                "patch one approved target-plane file",
                "stop after the patch",
            ],
            "do_not_recheck": [
                "whether 3_4_place_resized.odb exists",
                "whether config changes would retrigger place",
                "flow defaults or runner behavior outside the target plane",
            ],
        },
        "do_not_read": [
            "tasks/archive/*",
            "knowledge/stage_context/*",
            "knowledge/delta_ledger/*",
            "knowledge/design_profiles/*",
            "flow/Makefile",
            "flow/scripts/*",
            "flow/designs/*/config.mk",
        ],
        "preferred_start": {
            "file": problem["patch_surface"][0],
            "first_action": "inspect one target-plane file, apply one bounded patch, then stop",
        },
        "hard_gates": [
            "legality",
            "metrics.json present",
            "runtime bounded",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "current_run_packet.json").write_text(json.dumps(packet, indent=2))

    md = [
        "# Current Run Packet",
        "",
        f"- problem: {packet['problem']}",
        f"- primary objective: {packet['objective']['primary']}",
        f"- selected track: {packet['selected_track']}",
        f"- patch surface: {packet['selected_patch_surface']['file']}",
        "",
        "## Outer loop contract",
        *[f"- outer loop owns: {x}" for x in packet["outer_loop_contract"]["owns"]],
        *[f"- do not recheck: {x}" for x in packet["outer_loop_contract"]["do_not_recheck"]],
        "",
        "## Do not read for this turn",
        *[f"- {x}" for x in packet["do_not_read"]],
        "",
        "## Preferred start",
        f"- file: {packet['preferred_start']['file']}",
        f"- action: {packet['preferred_start']['first_action']}",
        "",
        "## Hard gates",
        *[f"- {x}" for x in packet["hard_gates"]],
        "",
        "## This turn only",
        *[f"- {x}" for x in packet["outer_loop_contract"]["codex_should_only"]],
    ]
    (out_dir / "current_run_packet.md").write_text("\n".join(md) + "\n")
    return packet


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem_dir", required=True, type=Path)
    ap.add_argument("--out_dir", required=True, type=Path)
    args = ap.parse_args()
    build_packet(args.problem_dir, args.out_dir)


if __name__ == "__main__":
    main()
