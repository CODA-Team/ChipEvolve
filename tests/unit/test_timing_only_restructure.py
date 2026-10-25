"""Selected timing recipes must execute their native restructuring steps."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from goalevolve.evaluation.contest2026 import (
    Contest2026Config,
    Contest2026OpenROADEvaluator,
)


class TimingOnlyRestructureTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        benchmark = self.root / "benchmarks/unit"
        benchmark.mkdir(parents=True)
        for suffix in ("def", "v", "sdc"):
            (benchmark / f"unit.{suffix}").write_text("", encoding="utf-8")
        pdk = self.root / "asap7"
        (pdk / "lef").mkdir(parents=True)
        (pdk / "lib").mkdir()
        (pdk / "lef/unit.lef").write_text("", encoding="utf-8")
        (pdk / "setRC.tcl").write_text("", encoding="utf-8")
        (pdk / "lib/unit.lib").write_text(
            "library(unit) { cell(A) { area : 1; } }", encoding="utf-8"
        )
        self.evaluator = Contest2026OpenROADEvaluator(
            Contest2026Config("unit", self.root / "benchmarks", self.root)
        )

    def render(self, recipe: str, mode: str = "timing_only") -> str:
        tcl = self.root / "evaluate.tcl"
        with patch.dict(os.environ, {}, clear=True):
            self.evaluator._write_tcl(
                tcl=tcl,
                output=self.root / "out",
                goal_tns_abs_ns=0,
                optimization_mode=mode,
                timing_recipe_id=recipe,
            )
        return tcl.read_text(encoding="utf-8")

    def assert_timing_restructure(self, rendered: str, *, before: bool) -> None:
        self.assertEqual(rendered.count("\nrestructure -liberty_file"), 1)
        self.assertIn("-target timing -slack_threshold 0 -depth_threshold 16", rendered)
        self.assertIn("set ::env(RSZ_GOAL_TNS_ABS_S) 0", rendered)
        self.assertIn("set ::env(RMP_MAX_TRIED_CLOUDS) 4", rendered)
        self.assertIn("set ::env(RMP_MAX_ACCEPTED_CLOUDS) 1", rendered)
        self.assertIn("set ::env(RMP_ENDPOINT_PATH_COUNT) 4", rendered)
        self.assertIn("set ::env(RMP_GUARD_MIN_TNS_IMPROVE_NS) 0.001", rendered)
        self.assertIn("set ::env(RMP_GUARD_MIN_WNS_IMPROVE_NS) 0.0", rendered)
        restructure = rendered.index("\nrestructure -liberty_file")
        timing = rendered.index("\nrepair_timing -setup")
        if before:
            self.assertLess(restructure, timing)
            self.assertEqual(rendered.count("\nrepair_timing -setup"), 1)
        else:
            self.assertLess(timing, restructure)
            self.assertLess(restructure, rendered.rindex("\nrepair_timing -setup"))
            self.assertEqual(rendered.count("\nrepair_timing -setup"), 2)

    def test_timing_only_executes_all_selected_native_rmp_recipes(self) -> None:
        for recipe in (
            "rmp_delay_timing",
            "rmp_path_cone_timing",
            "rmp_path_cone_halo_timing",
            "rmp_post_timing_halo",
        ):
            with self.subTest(recipe=recipe):
                rendered = self.render(recipe)
                self.assert_timing_restructure(
                    rendered, before=recipe != "rmp_post_timing_halo"
                )
                self.assertNotIn("\nrepair_power ", rendered)
                self.assertNotIn("RSZ_POWER_STAGE_TNS_CEILING_S", rendered)
                self.assertNotIn(
                    "GOALEVOLVE_CHECKPOINT_BEGIN post_repair_power", rendered
                )

    def test_timing_only_retains_selected_path_cone_limits(self) -> None:
        rendered = self.render("rmp_path_cone_halo_timing")
        self.assertIn("set ::env(RMP_UNION_ENDPOINT_PATHS) 1", rendered)
        self.assertIn("set ::env(RMP_PATH_CONE_ONLY) 1", rendered)
        self.assertIn("set ::env(RMP_EXPAND_SIDE_FANIN_LEVELS) 1", rendered)
        self.assertIn("set ::env(RMP_EXPAND_SIDE_FANIN_MAX_ADD) 16", rendered)
        rendered = self.render("rmp_post_timing_halo")
        self.assertIn("set ::env(RMP_EXPAND_SIDE_FANIN_LEVELS) 2", rendered)
        self.assertIn("set ::env(RMP_EXPAND_SIDE_FANIN_MAX_ADD) 24", rendered)

    def test_combined_mode_retains_power_then_native_restructure_schedule(self) -> None:
        for recipe in (
            "rmp_delay_timing",
            "rmp_path_cone_timing",
            "rmp_path_cone_halo_timing",
            "rmp_post_timing_halo",
        ):
            with self.subTest(recipe=recipe):
                rendered = self.render(recipe, "power_then_timing")
                self.assert_timing_restructure(
                    rendered, before=recipe != "rmp_post_timing_halo"
                )
                self.assertEqual(rendered.count("\nrepair_power "), 1)
                self.assertLess(
                    rendered.index("\nrepair_power "),
                    rendered.index("\nrestructure -liberty_file"),
                )

    def test_non_restructure_timing_and_mid_power_modes_remain_separate(self) -> None:
        for recipe in ("legacy_setup", "crit_vt_deep", "reroute_mid_power"):
            with self.subTest(recipe=recipe):
                rendered = self.render(recipe)
                self.assertNotIn("\nrestructure ", rendered)
                self.assertNotIn("\nrepair_power ", rendered)
                self.assertEqual(rendered.count("\nrepair_timing -setup"), 1)

    def test_combined_mid_power_recipe_still_has_its_original_two_passes(self) -> None:
        rendered = self.render("reroute_mid_power", "power_then_timing")
        self.assertEqual(rendered.count("\nrepair_power "), 2)
        self.assertEqual(rendered.count("\nrepair_timing -setup"), 2)
        self.assertNotIn("\nrestructure ", rendered)

    def test_area_power_recipe_does_not_acquire_timing_repair(self) -> None:
        rendered = self.render("rmp_area_power", "power_only")
        self.assertEqual(rendered.count("\nrepair_power "), 1)
        self.assertIn("-target area -slack_threshold 0 -depth_threshold 16", rendered)
        self.assertNotIn("\nrepair_timing -setup", rendered)


if __name__ == "__main__":
    unittest.main()
