"""
Compile a compact packet for Codex.

Input:
- problem.yaml
- selected patch surface
- selected playbook
Output:
- current_run_packet.md
- current_run_packet.json

This first version is intentionally simple and deterministic.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def build_packet(problem_dir: Path, out_dir: Path) -> Dict[str, Any]:
    problem = load_yaml(problem_dir / "problem.yaml")
    repo_root = Path(__file__).resolve().parents[3]
    kb_root = repo_root / "evolve_agent" / "knowledge"

    stage = load_yaml(kb_root / "stage_context" / "detail_place_stack.yaml")
    nblg = load_yaml(kb_root / "delta_ledger" / "nblg_to_openroad.yaml")
    legalm = load_yaml(kb_root / "delta_ledger" / "legalm_to_openroad.yaml")
    design = problem.get("design", "gcd")
    platform = problem.get("platform", "nangate45")
    profile = load_json(kb_root / "design_profiles" / f"{design}_{platform}.json")

    packet = {
        "run_id": "TODO_FILL_RUN_ID",
        "problem": problem["name"],
        "design_profile": profile,
        "objective": {
            "primary": problem["objective"]["primary"],
            "guardrails": problem["objective"]["guardrails"],
        },
        "stage_context": {
            "selected_track": problem["evaluation_track"],
            "key_includes": stage["tracks"]["strict_legalizer"]["include"],
            "key_excludes": stage["tracks"]["strict_legalizer"]["exclude"],
        },
        "selected_patch_surface": {
            "file": problem["patch_surface"][0],
            "allowed_functions_or_regions": [
                "negotiation cost / history / search / refinement"
            ],
        },
        "code_atlas_excerpt": {
            "commands": ["detailed_placement", "check_placement"],
            "cpp_entries": ["Opendp::detailedPlacement"],
        },
        "delta_ledger_excerpt": {
            "implemented_or_partial": nblg["delta_assessment"]["likely_present_or_partially_present"],
            "missing_or_disabled": nblg["delta_assessment"]["likely_missing_or_incomplete_or_disabled"],
            "implications": [
                "Prefer NBLG-informed mutation first.",
                "Use LEGALM ideas mainly for initialization/escape/refinement."
            ],
        },
        "selected_playbook": {
            "family": "negotiation_cost_family",
            "mechanisms": [
                "max-displacement penalty rebalance",
                "adaptive penalty schedule tweak",
            ],
            "telemetry_needed": [
                "HPWL before/after",
                "avg displacement",
                "max displacement",
                "runtime",
            ],
        },
        "hard_gates": [
            "legality",
            "metrics.json present",
            "runtime bounded",
        ],
        "run_checklist": [
            "Read packet and patch_rules.md",
            "Apply bounded patch",
            "Build OpenROAD",
            "Run single baseline on strict track",
            "Read evaluator output",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "current_run_packet.json").write_text(json.dumps(packet, indent=2))

    md = [
        "# Current Run Packet",
        "",
        f"- problem: {packet['problem']}",
        f"- primary objective: {packet['objective']['primary']}",
        f"- selected track: {packet['stage_context']['selected_track']}",
        f"- patch surface: {packet['selected_patch_surface']['file']}",
        "",
        "## Key includes",
        *[f"- {x}" for x in packet["stage_context"]["key_includes"]],
        "",
        "## Key excludes",
        *[f"- {x}" for x in packet["stage_context"]["key_excludes"]],
        "",
        "## NBLG / OpenROAD delta highlights",
        *[f"- {x}" for x in packet["delta_ledger_excerpt"]["missing_or_disabled"]],
        "",
        "## Selected playbook",
        f"- family: {packet['selected_playbook']['family']}",
        *[f"- {x}" for x in packet["selected_playbook"]["mechanisms"]],
        "",
        "## Hard gates",
        *[f"- {x}" for x in packet["hard_gates"]],
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
