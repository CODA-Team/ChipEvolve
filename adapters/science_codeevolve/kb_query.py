"""Compile a compact, authoritative packet for loop-driven Codex turns."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

AGENT_ROOT = Path(__file__).resolve().parents[2]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from runtime_paths import reexec_with_module, resolve_input_path, resolve_runtime_paths

try:
    import yaml
except ModuleNotFoundError:
    reexec_with_module("yaml", __file__, sys.argv)
    raise


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build_packet(problem_dir: Path, out_dir: Path) -> Dict[str, Any]:
    runtime = resolve_runtime_paths(
        anchor_file=__file__,
        agent_root_levels_up=2,
        script_name="kb_query.py",
    )
    problem_dir = resolve_input_path(
        problem_dir,
        cwd=Path.cwd(),
        agent_root=runtime.agent_root,
        orfs_root=runtime.orfs_root,
    )
    out_dir = resolve_input_path(
        out_dir,
        cwd=Path.cwd(),
        agent_root=runtime.agent_root,
        orfs_root=runtime.orfs_root,
    )
    problem = load_yaml(problem_dir / "problem.yaml")

    packet = {
        "problem": problem["name"],
        "design": problem["design"],
        "platform": problem["platform"],
        "objective": {
            "primary": problem["objective"]["primary"],
            "guardrails": problem["objective"]["guardrails"],
        },
        "track": problem["evaluation_track"],
        "target_file": problem["patch_surface"][0],
        "allowed_patch_surface": problem["patch_surface"],
        "read_order": [
            "this packet",
            "$DPL_EVOLVE_AGENT_ROOT/skills/patch_rules.md",
            "active problem.yaml",
            "target_file",
        ],
        "allowed_actions": [
            "inspect target_file",
            "make one bounded mechanism-specific patch",
            "stop after the patch",
        ],
        "forbidden_actions": [
            "run build",
            "run evaluator",
            "create or restore checkpoints",
            "discover FLOW_VARIANT",
            "inspect flow/Makefile",
            "inspect flow/scripts/*",
            "inspect flow/designs/*/config.mk",
            "inspect tasks/archive/*",
            "inspect knowledge/stage_context/*",
            "inspect knowledge/delta_ledger/*",
            "inspect knowledge/design_profiles/*",
            "inspect git history or broad repo status",
        ],
        "outer_loop_owns": [
            "prepare",
            "snapshot validation",
            "checkpoint restore",
            "build",
            "evaluator",
            "scoring",
            "accept/reject",
        ],
        "hard_gates": [
            "legality clean",
            "metrics.json present",
            "runtime bounded",
            "displacement controlled",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "current_run_packet.json").write_text(json.dumps(packet, indent=2))

    md = [
        "# Current Run Packet",
        "",
        f"- problem: {packet['problem']}",
        f"- design/platform: {packet['design']} / {packet['platform']}",
        f"- primary objective: {packet['objective']['primary']}",
        f"- track: {packet['track']}",
        f"- target file: {packet['target_file']}",
        "",
        "## Read Order",
        *[f"- {x}" for x in packet["read_order"]],
        "",
        "## Allowed Actions",
        *[f"- {x}" for x in packet["allowed_actions"]],
        "",
        "## Forbidden Actions",
        *[f"- {x}" for x in packet["forbidden_actions"]],
        "",
        "## Outer Loop Owns",
        *[f"- {x}" for x in packet["outer_loop_owns"]],
        "",
        "## Hard Gates",
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
