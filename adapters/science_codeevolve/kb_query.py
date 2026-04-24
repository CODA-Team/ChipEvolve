"""Compile a compact, authoritative packet for loop-driven Codex turns.

The packet is the agent-facing contract for a bounded patch attempt.  It should
be small enough to read quickly, but rich enough that Codex does not need to
rediscover the repository before choosing a mechanism.
"""
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
from memory.family_db import compact_family_record, families_by_id, family_evidence_cards
from memory.knowledge_db import card_prompt_fragment, load_stats, recent_knowledge_cards
from memory.run_db import recent_runs, summarize_recent_failures
from routing.patch_family_router import select_family, startpoint_from_family
from routing.region_selector import select_region

try:
    import yaml
except ModuleNotFoundError:
    reexec_with_module("yaml", __file__, sys.argv)
    raise


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_yaml_optional(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return default if data is None else data


def load_json_optional(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def compact_design_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "design": profile.get("design"),
        "platform": profile.get("platform"),
        "task": profile.get("task"),
        "preferred_track": profile.get("preferred_track"),
        "objective_priority": profile.get("objective_priority", []),
        "recommended_playbooks": profile.get("recommended_playbooks", []),
        "notes": profile.get("notes", [])[:3],
    }


def build_evidence_cards(
    *,
    family_selection: dict[str, Any],
    family_registry: dict[str, Any],
    effective_families: dict[str, Any],
    knowledge_cards: list[dict[str, Any]] | None = None,
) -> list[str]:
    cards: list[str] = []
    for card in knowledge_cards or []:
        fragment = card_prompt_fragment(card)
        if fragment:
            cards.append(f"learned: {fragment}")
    registry_id = str(family_selection.get("registry_id") or family_selection.get("id"))
    family = families_by_id(family_registry).get(registry_id, {})
    if family:
        cards.extend(family_evidence_cards(family, max_cards=4))
    for reason in family_selection.get("reason", [])[:3]:
        cards.append(f"route_reason: {reason}")
    for caution in family_selection.get("watch_out", [])[:3]:
        cards.append(f"watch_out: {caution}")
    for item in effective_families.get("donor_only_families", []):
        if isinstance(item, dict) and item.get("id"):
            cards.append(f"donor_only: {item['id']} is not a default parent; {item.get('reason', [''])[0] if item.get('reason') else ''}")
    return cards[:8]


def build_failures_to_avoid(
    *,
    family_registry: dict[str, Any],
    effective_families: dict[str, Any],
    run_failures: list[str],
    knowledge_cards: list[dict[str, Any]] | None = None,
) -> list[str]:
    failures = list(run_failures)
    for card in knowledge_cards or []:
        if card.get("kind") != "failure_pattern":
            continue
        fragment = card_prompt_fragment(card)
        if fragment:
            failures.append(fragment)
    for item in family_registry.get("families", []):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", ""))
        if status in {"rejected_no_effect", "superseded_base"}:
            summary = str(item.get("summary", "")).strip()
            if summary:
                failures.append(f"{item.get('id')}: {summary}")
            for weakness in item.get("weaknesses", [])[:2]:
                failures.append(f"{item.get('id')} weakness: {weakness}")
    for item in effective_families.get("noise_to_avoid", []):
        if isinstance(item, dict):
            failures.append(f"avoid {item.get('id')}: {item.get('reason', [''])[0] if item.get('reason') else ''}")
    return failures[:8]


def materialized_variant_surface(
    *,
    variant_family: str | None,
    family_component: dict[str, Any],
) -> dict[str, Any] | None:
    if variant_family != "legalm_engine":
        return None
    return {
        "file": "$DPL_EVOLVE_STATE_ROOT/family_variants/legalm_engine/dpl_evolve/src/AlmLegalizer.cpp",
        "symbol": "materialized LEGALM Stage1/Stage2/Stage3 legalizer",
        "signature": "family-specific materialized dpl_evolve source tree",
        "allowed_line_windows": [
            "materialized AlmLegalizer.cpp: Stage1 initialization, Stage2 escape, and Stage3 local refinement",
            "use adjacent materialized ALM headers only when the source patch requires a declaration",
        ],
        "allowed_patch_modes": [
            "legalm_stage_cost_change",
            "legalm_stuck_cell_escape",
            "legalm_local_refinement",
            "legalm_runtime_budgeting",
        ],
        "risk": "high",
        "family_variant_required": True,
        "materialize_with": [
            "$DPL_EVOLVE_AGENT_ROOT/scripts/materialize_family_variant.sh --family legalm_engine"
        ],
        "source_surfaces": family_component.get("source_surfaces", []),
        "family_mode_hints": [
            "materialized_variant_source_patch",
            "do_not_patch_clean_main_tree",
        ],
        "selection_reason": [
            "selected family is a materialized variant",
            "patch the generated family source tree, not tools/OpenROAD/src/dpl_evolve",
            "outer loop owns materialization and dedicated binary build",
        ],
        "excluded_high_value_surfaces": [],
    }


def packet_markdown(packet: dict[str, Any]) -> str:
    surface = packet["selected_patch_surface"]
    family = packet["selected_patch_family"]
    lines = [
        "# Current Run Packet",
        "",
        f"- problem: {packet['problem']}",
        f"- design/platform: {packet['design']} / {packet['platform']}",
        f"- primary objective: {packet['objective']['primary']}",
        f"- track: {packet['track']}",
        f"- selected family: {family['id']}",
        f"- selected surface: {surface.get('symbol')} in {surface.get('file')}",
        "",
        "## Why This Patch Family",
        *[f"- {item}" for item in family.get("reason", [])[:5]],
        "",
        "## Selected Patch Surface",
        f"- file: {surface.get('file')}",
        f"- symbol: {surface.get('symbol')}",
        f"- risk: {surface.get('risk')}",
        "- allowed line windows:",
        *[f"- {item}" for item in surface.get("allowed_line_windows", [])],
        "- allowed patch modes:",
        *[f"- {item}" for item in surface.get("allowed_patch_modes", [])],
        "",
        "## Evidence Cards",
        *[f"- {item}" for item in packet.get("evidence_cards", [])],
        "",
        "## Last Failures To Avoid",
        *[f"- {item}" for item in packet.get("last_failures_to_avoid", [])],
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
        "",
        "## Required Final Note",
        *[f"- {x}" for x in packet["required_final_note"]],
    ]
    excluded = surface.get("excluded_high_value_surfaces", [])
    if excluded:
        lines.extend(["", "## Excluded High-Value Surfaces"])
        lines.extend(
            f"- {item.get('symbol')} in {item.get('file')}: {item.get('reason')}"
            for item in excluded
        )
    family_stats = family.get("posterior_stats") or {}
    region_stats = surface.get("posterior_stats") or {}
    if family_stats or region_stats:
        lines.extend(["", "## Learned Stats"])
        if family_stats:
            lines.append(f"- family posterior: {json.dumps(family_stats, sort_keys=True)}")
        if region_stats:
            lines.append(f"- region posterior: {json.dumps(region_stats, sort_keys=True)}")
    return "\n".join(lines) + "\n"


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
    case_id = f"{problem['design']}_{problem['platform']}"
    knowledge_root = runtime.agent_root / "knowledge"
    design_profile = load_json_optional(
        knowledge_root / "design_profiles" / f"{case_id}.json",
        {},
    )
    patch_surface = load_yaml_optional(
        runtime.agent_root / "adapters" / "science_codeevolve" / "patch_surface.yaml",
        {"surfaces": [], "policy": {}, "notes": []},
    )
    effective_families = load_yaml_optional(
        knowledge_root / "family_components" / "effective_families.yaml",
        {},
    )
    family_registry = load_yaml_optional(
        knowledge_root / "replay_bank" / "family_registry.yaml",
        {"families": []},
    )
    legalm_component = load_yaml_optional(
        knowledge_root / "family_components" / "legalm_engine.yaml",
        {},
    )
    family_selection = select_family(
        problem=problem,
        design_profile=design_profile,
        effective_families=effective_families,
        family_registry=family_registry,
    )
    selected_surface = select_region(
        problem=problem,
        patch_surface=patch_surface,
        family_id=str(family_selection.get("id")),
    )
    variant_surface = materialized_variant_surface(
        variant_family=family_selection.get("variant_family"),
        family_component=legalm_component,
    )
    if variant_surface is not None:
        selected_surface = variant_surface
    registry_id = str(family_selection.get("registry_id") or family_selection.get("id"))
    family = families_by_id(family_registry).get(
        registry_id,
        {},
    )
    run_history = recent_runs(
        runtime.state_root,
        problem=problem["name"],
        family=str(family_selection.get("id")),
        limit=12,
    )
    run_failures = summarize_recent_failures(run_history, limit=4)
    dynamic_stats = load_stats(runtime.state_root)
    family_stats = dynamic_stats.get("families", {}).get(str(family_selection.get("id")), {})
    region_stats = dynamic_stats.get("regions", {}).get(str(selected_surface.get("symbol")), {})
    knowledge_cards = recent_knowledge_cards(
        runtime.state_root,
        problem=problem["name"],
        family=str(family_selection.get("id")),
        limit=5,
    )
    symbol_cards = recent_knowledge_cards(
        runtime.state_root,
        problem=problem["name"],
        symbol=str(selected_surface.get("symbol")),
        limit=3,
    )
    card_by_id = {card.get("id"): card for card in [*knowledge_cards, *symbol_cards]}
    selected_cards = [card for card in card_by_id.values() if card]

    packet = {
        "run_id": f"{problem['name']}__context",
        "problem": problem["name"],
        "design": problem["design"],
        "platform": problem["platform"],
        "design_profile": compact_design_profile(design_profile),
        "objective": {
            "primary": problem["objective"]["primary"],
            "secondary": problem["objective"].get("secondary", []),
            "guardrails": problem["objective"]["guardrails"],
        },
        "track": problem["evaluation_track"],
        "stage_context": {
            "input_stage": problem.get("input_stage"),
            "evaluation_track": problem["evaluation_track"],
            "strict_track_scope": "legalization-only from a fixed placement handoff",
            "agent_scope": "one bounded source patch; no build/eval/checkpoint actions",
            "patch_surface_policy": patch_surface.get("policy", {}),
            "surface_notes": patch_surface.get("notes", []),
        },
        "selected_startpoint": startpoint_from_family(family_selection),
        "selected_patch_family": {
            "id": family_selection.get("id"),
            "registry_id": registry_id,
            "regime": family_selection.get("regime"),
            "variant_family": family_selection.get("variant_family"),
            "source": family_selection.get("source"),
            "reason": family_selection.get("reason", []),
            "watch_out": family_selection.get("watch_out", []),
            "registry_record": compact_family_record(family) if family else {},
            "posterior_stats": family_stats,
        },
        "selected_patch_surface": {
            **selected_surface,
            "posterior_stats": region_stats,
        },
        "code_atlas_excerpt": {
            "target_file": selected_surface.get("file"),
            "target_symbol": selected_surface.get("symbol"),
            "entry_commands": [
                "detailed_placement_evolve",
                "check_placement_evolve",
            ],
            "variant_materialization": selected_surface.get("materialize_with", []),
            "excluded_high_value_surfaces": selected_surface.get(
                "excluded_high_value_surfaces",
                [],
            ),
        },
        "delta_ledger_excerpt": {
            "avoid_known_noise": effective_families.get("noise_to_avoid", []),
            "family_watch_out": family_selection.get("watch_out", []),
        },
        "selected_playbook": {
            "family": family_selection.get("id"),
            "mechanism_modes": selected_surface.get("allowed_patch_modes", []),
            "telemetry_needed": [
                "legality",
                "hpwl_delta_micron",
                "avg_displacement_micron",
                "max_displacement_micron",
                "runtime_seconds",
                "peak_rss_bytes",
                "setup_ws",
                "setup_tns",
            ],
        },
        "evidence_cards": build_evidence_cards(
            family_selection=family_selection,
            family_registry=family_registry,
            effective_families=effective_families,
            knowledge_cards=selected_cards,
        ),
        "last_failures_to_avoid": build_failures_to_avoid(
            family_registry=family_registry,
            effective_families=effective_families,
            run_failures=run_failures,
            knowledge_cards=selected_cards,
        ),
        "target_file": selected_surface.get("file") or problem["patch_surface"][0],
        "allowed_patch_surface": problem["patch_surface"],
        "variant_allowed_patch_surface": selected_surface.get("source_surfaces", []),
        "read_order": [
            "this packet",
            "$DPL_EVOLVE_AGENT_ROOT/skills/patch_rules.md",
            "active problem.yaml",
            "selected target_file and selected symbol only",
        ],
        "allowed_actions": [
            "inspect target_file",
            "inspect selected symbol and nearby helper declarations only",
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
        "run_checklist": [
            "confirm the selected symbol before editing",
            "make a single mechanism-specific source patch",
            "do not edit evaluator, metrics collection, ORFS flow files, or checkpoint logic",
            "leave build and evaluation to the outer loop",
        ],
        "required_final_note": [
            "touched files",
            "touched symbol",
            "patch family",
            "expected metric effect",
            "rollback condition",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "current_run_packet.json").write_text(json.dumps(packet, indent=2))
    (out_dir / "current_run_packet.md").write_text(packet_markdown(packet))
    return packet


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem_dir", required=True, type=Path)
    ap.add_argument("--out_dir", required=True, type=Path)
    args = ap.parse_args()
    build_packet(args.problem_dir, args.out_dir)


if __name__ == "__main__":
    main()
