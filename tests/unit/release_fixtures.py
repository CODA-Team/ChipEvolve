"""Synthetic unit inputs for private assets absent from the public release.

Nothing here is a recovered experiment or a research lesson. Fixtures exist
only inside TemporaryDirectory and never populate the runtime knowledge base.
"""

from __future__ import annotations

import functools
import json
import tempfile
from pathlib import Path
from unittest.mock import patch


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _profiles(root: Path, published: Path) -> None:
    from goalevolve.config import _load_raw_config

    source = root / "artifact_evaluation/lineage/openroad_power/p0/source"
    source.mkdir(parents=True)
    (source / "CMakeLists.txt").write_text("# synthetic unit source; never built\n")
    for original in published.glob("experiments/*/*.json"):
        if original.name not in {"evolve.json", "baseline.json"}:
            continue
        raw = _load_raw_config(original)
        design = raw["design"]
        mode = "ae3" if original.name == "evolve.json" else "baseline"
        raw.update(
            source_root=str(source),
            state_root=str(root / "outputs" / mode / design),
            benchmark_root=str(root / "benchmarks"),
        )
        raw.pop("initial_parent_source_root", None)
        raw.pop("initial_parent_id", None)
        _write(root / "experiments" / design / original.name, raw)
        benchmark = root / "benchmarks" / design
        benchmark.mkdir(parents=True, exist_ok=True)
        for name in (f"{design}.def.gz", f"{design}.v", f"{design}.sdc", "metrics.csv"):
            (benchmark / name).write_text(
                "synthetic existence fixture; never evaluated\n"
            )

    ids = [
        "repair_power_early_electrical_commit",
        "repair_power_early_bounded_tail",
        "repair_power_late_second_pass",
        "power_recovery_plus_late_profile",
        "setup_mt1_deep_batch_guard",
    ]
    extended = ids[:4] + [
        "repair_power_critical_cone_persistence",
        ids[4],
        "repair_power_compound_vt_reserve",
        "repair_power_compound_vt_halo",
        "repair_power_critical_halo_vt_guard",
        "repair_power_commit_boundary_halo_guard",
    ]
    cards = []
    for seed in extended:
        reference = root / "fixtures" / (seed + ".diff")
        reference.parent.mkdir(exist_ok=True)
        reference.write_text(
            "# synthetic reference existence fixture; not a research patch\n"
        )
        cards.append(
            {
                "seed_id": seed,
                "source_anchors": [
                    "src/rsz/src/policy/RepairPowerPolicy.cc::synthetic"
                ],
                "decision_boundary": "synthetic unit contract",
                "summary": "synthetic fixture, not historical evidence",
                "expected_signals": ["synthetic"],
                "reference_diff_paths": [str(reference)],
            }
        )
    catalog = root / "fixtures/cards.json"
    _write(catalog, {"cards": cards})
    short_catalog = root / "fixtures/short-cards.json"
    _write(
        short_catalog,
        {
            "cards": [
                next(card for card in cards if card["seed_id"] == seed) for seed in ids
            ]
        },
    )
    base = _load_raw_config(published / "experiments/aes_cipher_top/evolve.json")
    for key in list(base):
        if key.startswith("initial_parent_"):
            base.pop(key)
    base.update(
        source_root=str(source),
        campaign_ready=True,
        max_campaign_rounds=10,
        max_consecutive_no_promotion_rounds=10,
        power_reclaim_phase="early_forced_reclaim",
        power_reclaim_proportion_percent=80.0,
        power_reclaim_max_moves=0,
        power_stage_protected_rounds=8,
        power_stage_tns_ceiling_ns=80.0,
        repository_graph_enabled=True,
        historical_seed_cards=str(short_catalog),
    )
    names = [
        "p0_revalidation_20260805",
        "p0_original_power_8r_20260805",
        "p0_original_power_8r_20260805_rerun1",
        "p0_original_power_8r_20260805_rerun3",
        "p0_original_power_8r_20260806",
        "p0_ast_recovery_20260810_baseline",
        "p0_ast_recovery_20260810",
    ]
    for name in names:
        raw = dict(base)
        raw["state_root"] = str(
            root
            / "outputs"
            / (
                "aes_" + name.removeprefix("p0_")
                if name.startswith("p0_ast_recovery")
                else "aes_" + name
            )
            / "campaign"
        )
        raw["baseline_evaluation_root"] = raw["state_root"]
        seeds = extended if name.startswith("p0_ast_recovery") else ids
        raw["historical_seed_cards"] = str(
            catalog if name.startswith("p0_ast_recovery") else short_catalog
        )
        raw["historical_seed_revalidation_schedule"] = [
            {
                "round_index": index + 1,
                "seed_ids": [seed],
                "stages": ["power_reclaim" if index < 3 else "timing_recovery"],
            }
            for index, seed in enumerate(seeds)
        ]
        if name == "p0_revalidation_20260805":
            raw.update(
                power_stage_tns_ceiling_ns=60.0,
                baseline_metrics={
                    "tns_abs_ns": 12.69,
                    "dynamic_power_pw": 411904600000.0,
                    "leakage_power_pw": 95400000.0,
                },
            )
        if name == "p0_ast_recovery_20260810":
            raw["baseline_evaluation_root"] = str(
                root / "outputs/aes_ast_recovery_20260810_baseline/campaign"
            )
        _write(root / "experiments/aes_cipher_top" / (name + ".local.json"), raw)


def released_unit_assets(kind: str):
    """Run unchanged behavior assertions against explicit synthetic inputs."""

    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            published = Path(function.__globals__["__file__"]).resolve().parents[2]
            with tempfile.TemporaryDirectory(
                prefix="goalevolve-unit-assets-"
            ) as temporary:
                root = Path(temporary)
                if kind == "profiles":
                    _profiles(root, published)
                    with patch.dict(
                        function.__globals__,
                        {"__file__": str(root / "tests/unit/test_core.py")},
                    ):
                        return function(*args, **kwargs)
                from goalevolve.planning import cross_design_experience as experience

                lessons = root / "synthetic-lessons.json"
                _write(
                    lessons,
                    {
                        "lessons": [
                            {
                                "lesson_id": identifier,
                                "scope": {"stages": stages},
                                "evidence_summary": "synthetic unit input; not research evidence",
                                "planning_rule": "synthetic planning rule",
                                "student_rule": "synthetic student rule",
                            }
                            for identifier, stages in [
                                ("XDES_POWER_CELLSET_EFFECT_001", ["power_reclaim"]),
                                (
                                    "XDES_POWER_STAGE_OBJECTIVE_ALIGNMENT_001",
                                    ["power_reclaim"],
                                ),
                                (
                                    "XDES_SOURCE_ANCHOR_COVERAGE_001",
                                    ["power_reclaim", "timing_recovery"],
                                ),
                            ]
                        ]
                    },
                )
                loader = functools.partial(
                    experience.load_cross_design_experience, path=lessons
                )
                with patch.object(experience, "load_cross_design_experience", loader):
                    return function(*args, **kwargs)

        return wrapped

    return decorate
