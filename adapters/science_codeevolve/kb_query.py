#!/usr/bin/env python3
"""Build a compact packet for constrained DPL-Evolve framework edits.

The old packet builder routed among many historical patch families.  The
current project direction is different: `detailed_placement_evolve` is a stable
entrypoint, and agents should evolve one stage of the constrained top-level
framework while using archived algorithms only as references.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[2]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from memory.knowledge_db import card_prompt_fragment, recent_knowledge_cards
from memory.run_db import recent_runs, summarize_recent_failures
from runtime_paths import resolve_runtime_paths

try:
    import yaml  # type: ignore[import-not-found]
except ModuleNotFoundError:  # Keep packet generation usable in minimal envs.
    yaml = None


FRAMEWORK_SURFACE = {
    "file": "tools/OpenROAD/src/dpl_evolve/src/EvolveLegalizer.cpp",
    "header_files": [
        "tools/OpenROAD/src/dpl_evolve/src/EvolveLegalizer.h",
        "tools/OpenROAD/src/dpl_evolve/src/EvolveContext.h",
        "tools/OpenROAD/src/dpl_evolve/src/EvolveTelemetry.h",
        "tools/OpenROAD/src/dpl_evolve/src/EvolvePluginApi.h",
    ],
    "symbol": "dpl_evolve::EvolveLegalizer::run",
    "allowed_patch_modes": [
        "stage_ordering",
        "stage_guarding",
        "relaxed_guidance_stage",
        "assignment_donor_stage",
        "diamond_compatible_stage",
        "negotiation_repair_stage",
        "bounded_polish_stage",
        "telemetry_only",
        "plugin_abi_extension",
    ],
    "risk": "medium",
}


REFERENCE_FILES = [
    "family_variants/REFERENCE_INDEX.yaml",
    "family_variants/reference_sources/README.md",
    "family_variants/reference_sources/openroad_diamond/README.md",
    "family_variants/reference_sources/openroad_negotiation_nblg/README.md",
    "family_variants/reference_sources/legalm/README.md",
    "family_variants/reference_sources/dreamplace_abacus/README.md",
    "family_variants/negotiation_parallel_frontier/README.md",
    "family_variants/legalm_engine/README.md",
    "knowledge/reference/papers/paper_sources.yaml",
]


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def load_simple_yaml(path: Path) -> dict[str, Any]:
    """Tiny YAML subset reader for repo-local problem/index files.

    It supports top-level mappings, one-level nested mappings, and block lists.
    This is not a general YAML parser; it only keeps lightweight packet
    generation working when PyYAML is unavailable.
    """

    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    last_key_for_indent: dict[int, str] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1]

        if line.startswith("- "):
            value = parse_scalar(line[2:])
            if not isinstance(container, list):
                parent = stack[-2][1] if len(stack) >= 2 else root
                key = last_key_for_indent.get(stack[-1][0])
                if isinstance(parent, dict) and key:
                    parent[key] = []
                    container = parent[key]
                    stack[-1] = (stack[-1][0], container)
            if isinstance(container, list):
                container.append(value)
            continue

        if ":" not in line or not isinstance(container, dict):
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if raw_value:
            container[key] = parse_scalar(raw_value)
        else:
            container[key] = {}
            stack.append((indent, container[key]))
            last_key_for_indent[indent] = key
    return root


def load_yaml(path: Path) -> Any:
    if yaml is not None:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return {} if data is None else data
    return load_simple_yaml(path)


def maybe_load_yaml(path: Path) -> Any:
    if not path.exists():
        return {}
    return load_yaml(path)


def compact_problem(problem: dict[str, Any]) -> dict[str, Any]:
    objective = problem.get("objective") or {}
    return {
        "name": problem.get("name"),
        "design": problem.get("design"),
        "platform": problem.get("platform"),
        "task_type": problem.get("task_type"),
        "input_stage": problem.get("input_stage"),
        "evaluation_track": problem.get("evaluation_track", "strict_legalizer"),
        "objective": {
            "primary": objective.get("primary", "legalization_hpwl"),
            "secondary": objective.get("secondary", []),
            "guardrails": objective.get("guardrails", ["legality", "runtime"]),
        },
    }


def packet_markdown(packet: dict[str, Any]) -> str:
    surface = packet["selected_patch_surface"]
    lines = [
        "# Current Run Packet",
        "",
        f"- problem: {packet['problem']['name']}",
        f"- design/platform: {packet['problem']['design']} / {packet['problem']['platform']}",
        f"- track: {packet['problem']['evaluation_track']}",
        f"- primary objective: {packet['problem']['objective']['primary']}",
        f"- selected surface: {surface['symbol']} in {surface['file']}",
        "",
        "## Direction",
        "- Keep `detailed_placement_evolve` as the only evolved entrypoint.",
        "- Patch the constrained framework or a plugin-compatible stage, not classic `dpl` or evaluator scripts.",
        "- Use reference algorithms as donors, then implement a clean staged mechanism in `dpl_evolve`.",
        "",
        "## Selected Patch Surface",
        f"- file: {surface['file']}",
        "- headers:",
        *[f"- {item}" for item in surface["header_files"]],
        f"- risk: {surface['risk']}",
        "- allowed patch modes:",
        *[f"- {item}" for item in surface["allowed_patch_modes"]],
        "",
        "## Reference Shelf",
        *[f"- {item}" for item in packet["reference_files"]],
        "",
        "## Evidence Cards",
        *[f"- {item}" for item in packet["evidence_cards"]],
        "",
        "## Last Failures To Avoid",
        *[f"- {item}" for item in packet["last_failures_to_avoid"]],
        "",
        "## Read Order",
        *[f"- {item}" for item in packet["read_order"]],
        "",
        "## Allowed Actions",
        *[f"- {item}" for item in packet["allowed_actions"]],
        "",
        "## Forbidden Actions",
        *[f"- {item}" for item in packet["forbidden_actions"]],
        "",
        "## Hard Gates",
        *[f"- {item}" for item in packet["hard_gates"]],
        "",
        "## Required Final Note",
        *[f"- {item}" for item in packet["required_final_note"]],
    ]
    return "\n".join(lines) + "\n"


def build_packet(problem_dir: Path, out_dir: Path) -> dict[str, Any]:
    runtime = resolve_runtime_paths(
        anchor_file=__file__,
        agent_root_levels_up=2,
        script_name="kb_query.py",
    )
    problem_path = problem_dir / "problem.yaml"
    problem = compact_problem(load_yaml(problem_path))
    problem_name = str(problem.get("name") or problem_dir.name)
    cards = [
        card_prompt_fragment(card)
        for card in recent_knowledge_cards(
            runtime.state_root,
            problem=problem_name,
            status="active",
            limit=6,
        )
    ]
    cards = [card for card in cards if card]
    recent = recent_runs(runtime.state_root, problem=problem_name, limit=12)
    failures = summarize_recent_failures(recent, limit=6)

    reference_index = maybe_load_yaml(AGENT_ROOT / "family_variants" / "REFERENCE_INDEX.yaml")
    packet = {
        "schema_version": 2,
        "packet_type": "constrained_framework_patch",
        "problem": problem,
        "reference_index": reference_index,
        "selected_patch_surface": FRAMEWORK_SURFACE,
        "reference_files": REFERENCE_FILES,
        "evidence_cards": cards,
        "last_failures_to_avoid": failures,
        "read_order": [
            "adapters/science_codeevolve/current_run_packet.md",
            "skills/patch_rules.md",
            str(problem_path.relative_to(AGENT_ROOT)),
            FRAMEWORK_SURFACE["file"],
            "family_variants/REFERENCE_INDEX.yaml",
        ],
        "allowed_actions": [
            "Edit only `tools/OpenROAD/src/dpl_evolve` in a prepared private variant source.",
            "Use reference algorithms to implement one bounded framework-stage mechanism.",
            "Add or refine `EvolveTelemetry` counters that explain stage behavior.",
            "Optionally implement a V1 plugin shared object against `EvolvePluginApi.h`.",
        ],
        "forbidden_actions": [
            "Do not edit classic `tools/OpenROAD/src/dpl` as part of an evolve attempt.",
            "Do not edit evaluator, scoring, baseline Tcl, or benchmark selection.",
            "Do not introduce fallback-to-default as a success path.",
            "Do not optimize only for AES; JPEG and larger cases are promotion gates.",
        ],
        "hard_gates": [
            "Private OpenROAD binary or plugin builds successfully.",
            "`detailed_placement_evolve` remains the invoked command.",
            "Strict evaluator reports legal placement.",
            "Telemetry identifies which stages ran and whether repair/polish was needed.",
            "Runtime must be comparable to diamond baseline before large-case promotion.",
        ],
        "required_final_note": [
            "Touched files and stage owner.",
            "Mechanism implemented and reference donor used.",
            "Build command and private binary or plugin path.",
            "AES/JPEG result paths when available.",
            "Telemetry snippet and rollback condition.",
        ],
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "current_run_packet.json").write_text(
        json.dumps(packet, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "current_run_packet.md").write_text(
        packet_markdown(packet),
        encoding="utf-8",
    )
    return packet


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem_dir", type=Path, required=True)
    parser.add_argument("--out_dir", type=Path, required=True)
    args = parser.parse_args()
    packet = build_packet(args.problem_dir.resolve(), args.out_dir.resolve())
    print(json.dumps({"packet": str(args.out_dir / "current_run_packet.md"), "type": packet["packet_type"]}))


if __name__ == "__main__":
    main()
