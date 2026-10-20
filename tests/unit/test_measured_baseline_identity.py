"""Measured seed identity must reach the existing stage-matching controller."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from goalevolve.cli import _attach_configured_baseline
from goalevolve.core.contracts import build_contract
from goalevolve.core.io import atomic_json, load_json
from goalevolve.core.models import CandidateResult, CheckResult, Hypothesis
from goalevolve.evaluation.contest2026 import (
    Contest2026Config,
    Contest2026OpenROADEvaluator,
)
from goalevolve.evaluation.promotion import PowerFirstPromotion
from goalevolve.execution.engine import GoalEvolveEngine
from goalevolve.execution.workspace import IsolatedWorkspace
from goalevolve.planning.retrieval import DiversePlanner
from goalevolve.testing.evaluators import MockEvaluator


class MeasuredBaselineIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.contract = build_contract(
            design="unit",
            baseline_metrics={
                "tns_abs_ns": 2.0,
                "dynamic_power_pw": 180.0,
                "leakage_power_pw": 80.0,
            },
            target_metrics={
                "tns_abs_ns": 1.0,
                "dynamic_power_pw": 170.0,
                "leakage_power_pw": 75.0,
            },
        )
        self.policy = PowerFirstPromotion()
        self.engine = GoalEvolveEngine(
            self.contract,
            self.root / "state",
            DiversePlanner(),
            MockEvaluator(),
            IsolatedWorkspace(),
            self.policy,
        )
        self.parent = self.engine.initialize(
            baseline_metrics=dict(self.contract.baseline_metrics)
        )
        self.config = SimpleNamespace(baseline_evaluation_root=self.root / "baseline")

    def attach(self, **identity):
        artifact = self.config.baseline_evaluation_root / "baseline.json"
        atomic_json(
            artifact,
            {
                "ok": True,
                "metrics": dict(self.contract.baseline_metrics),
                "artifacts": {},
                **identity,
            },
        )
        original = artifact.read_bytes()
        _attach_configured_baseline(engine=self.engine, config=self.config)
        self.assertEqual(artifact.read_bytes(), original)
        return self.engine._load_parent()

    def test_new_measured_identity_attaches_without_changing_metrics_or_source(self):
        parent = self.attach(
            evaluation_mode="timing_only", timing_recipe_id="legacy_setup"
        )
        self.assertEqual(parent, replace(self.parent, evaluation_mode="timing_only"))

    def test_historical_metadata_less_baseline_remains_unknown(self):
        self.assertEqual(self.attach(), self.parent)

    def test_inherited_drv_reaches_parent_without_changing_objectives(self):
        contract_before = self.contract.to_dict()
        parent = self.attach(
            metrics={
                **self.contract.baseline_metrics,
                "drv_count": 294,
                "runtime_s": 1093,
            },
            evaluation_mode="timing_only",
        )
        self.assertEqual(parent.metrics["drv_count"], 294)
        self.assertEqual(parent.metrics["runtime_s"], 1093)
        self.assertEqual(self.contract.to_dict(), contract_before)
        self.assertEqual(parent.goal_distance, self.parent.goal_distance)
        self.assertEqual(parent.source_hash, self.parent.source_hash)
        self.assertEqual(parent.source_commit, self.parent.source_commit)
        for name, value in self.parent.metrics.items():
            self.assertEqual(parent.metrics[name], value)

    def test_zero_drv_is_retained(self):
        parent = self.attach(metrics={**self.contract.baseline_metrics, "drv_count": 0})
        self.assertEqual(parent.metrics["drv_count"], 0)

    def test_measured_parent_distinguishes_inherited_from_added_drv(self):
        parent = self.attach(
            metrics={**self.contract.baseline_metrics, "drv_count": 294}
        )
        candidate = CandidateResult(
            "student_1",
            Hypothesis("unit", "timing", "repair timing", (), (), (), "unit"),
            {"drv_count": 294},
            {},
            [CheckResult(name, True) for name in ("build", "flow", "metrics", "lec")],
            "",
            "source",
        )
        self.assertFalse(
            self.engine._repairable_constraint_failure(
                candidate=candidate, parent=parent
            )
        )
        candidate = replace(candidate, metrics={"drv_count": 296})
        self.assertTrue(
            self.engine._repairable_constraint_failure(
                candidate=candidate, parent=parent
            )
        )
        context = self.engine._constraint_failure_context(
            candidate=candidate, parent=parent, workspace=self.root
        )
        self.assertIn("candidate drv_count=296; parent drv_count=294.0", context)
        self.assertNotIn("requires drv_count=0", context)

    def test_promoted_parent_observations_are_not_replaced(self):
        promoted = replace(
            self.parent,
            parent_id="student_3",
            metrics={**self.parent.metrics, "drv_count": 2, "runtime_s": 55},
        )
        atomic_json(self.engine.state_root / "parent.json", promoted.to_dict())
        self.assertEqual(
            self.attach(
                metrics={
                    **self.contract.baseline_metrics,
                    "drv_count": 294,
                    "runtime_s": 1093,
                }
            ),
            promoted,
        )

    def test_existing_parent_observations_are_not_overwritten(self):
        existing = replace(self.parent, metrics={**self.parent.metrics, "drv_count": 7})
        atomic_json(self.engine.state_root / "parent.json", existing.to_dict())
        self.assertEqual(
            self.attach(metrics={**self.contract.baseline_metrics, "drv_count": 294}),
            existing,
        )

    def test_known_staged_baseline_is_not_reset(self):
        staged = replace(
            self.parent,
            evaluation_mode="power_then_timing",
            timing_recipe_id="wns_timing",
        )
        atomic_json(self.engine.state_root / "parent.json", staged.to_dict())
        self.assertEqual(
            self.attach(evaluation_mode="timing_only", timing_recipe_id="legacy_setup"),
            staged,
        )

    def test_promoted_unknown_parent_is_not_relabelled(self):
        promoted = replace(self.parent, parent_id="student_3", source_hash="new_source")
        atomic_json(self.engine.state_root / "parent.json", promoted.to_dict())
        self.assertEqual(self.attach(evaluation_mode="timing_only"), promoted)

    def test_explicit_empty_mode_retains_legacy_bootstrap(self):
        atomic_json(
            self.engine.state_root / "parent.json",
            replace(self.parent, evaluation_mode="").to_dict(),
        )
        self.assertEqual(self.attach(evaluation_mode="").evaluation_mode, "")

    def test_measured_mode_reaches_original_matching_and_timing_recovery(self):
        parent = self.attach(evaluation_mode="timing_only")
        source = self.engine.state_root / "parents" / parent.source_hash / "source"
        source.mkdir(parents=True)
        matched_metrics = {
            "tns_abs_ns": 6.6,
            "dynamic_power_pw": 162.0,
            "leakage_power_pw": 69.0,
            "drv_count": 0.0,
        }
        measure = Mock(
            return_value={"ok": True, "metrics": matched_metrics, "artifacts": {}}
        )
        evaluator = SimpleNamespace(name="same_source_control", evaluate_parent=measure)
        context = self.policy.context(contract=self.contract, parent=parent)
        self.assertEqual(context["stage"], "power_reclaim")
        with patch.object(self.engine, "evaluator", evaluator):
            matched = self.engine._stage_matched_parent(
                parent=parent, decision_context=context
            )
        measure.assert_called_once()
        self.assertEqual(measure.call_args.kwargs["optimization_mode"], "power_only")
        self.assertEqual(matched.metrics, matched_metrics)
        self.assertFalse(
            list(self.engine.state_root.glob("stage_baselines/*/*bootstrap.json"))
        )
        context = self.policy.context(contract=self.contract, parent=matched)
        self.assertEqual(context["stage"], "timing_recovery")
        self.assertEqual(context["evaluation_mode"], "power_then_timing")

    def test_evaluator_records_the_explicit_actual_baseline_sequence(self):
        seed = self.root / "seed"
        seed.mkdir()
        evaluator = Contest2026OpenROADEvaluator(
            Contest2026Config("unit", self.root / "benchmarks", seed)
        )
        output = self.root / "evaluation"

        def run(*, command, output_log=None, **_kwargs):
            if output_log:
                output_log.write_text("unit flow\n", encoding="utf-8")
            if command[0] == "python3":
                Path(command[-1]).write_text("unit CSV\n", encoding="utf-8")
            return SimpleNamespace(ok=True, resource_error=None)

        with (
            patch.object(evaluator, "_build", return_value=seed / "openroad"),
            patch.object(evaluator, "_write_tcl") as write_tcl,
            patch("goalevolve.evaluation.contest2026.ResilientCommandRunner") as runner,
            patch(
                "goalevolve.evaluation.contest2026._read_metrics",
                return_value=dict(self.contract.baseline_metrics),
            ),
            patch(
                "goalevolve.evaluation.contest2026._placement_legal",
                return_value=(True, "unit placement"),
            ),
            patch(
                "goalevolve.evaluation.contest2026.official_four_check",
                return_value=(True, "unit checker"),
            ),
            patch("goalevolve.evaluation.contest2026._observe_sfinal", return_value={}),
        ):
            runner.return_value.run.side_effect = run
            result = evaluator.evaluate_baseline(contract=self.contract, output=output)
        self.assertTrue(result["ok"])
        self.assertEqual(result["evaluation_mode"], "timing_only")
        self.assertEqual(result["timing_recipe_id"], "legacy_setup")
        write_tcl.assert_called_once_with(
            tcl=output / "evaluate.tcl",
            output=output,
            optimization_mode="timing_only",
            timing_recipe_id="legacy_setup",
        )

    def test_explicit_baseline_sequence_keeps_previous_tcl_byte_for_byte(self):
        benchmark = self.root / "benchmarks" / "unit"
        benchmark.mkdir(parents=True)
        for name in ("unit.def", "unit.v", "unit.sdc"):
            (benchmark / name).touch()
        for kind, name in (("lef", "unit.lef"), ("lib", "unit.lib")):
            path = self.root / "asap7" / kind / name
            path.parent.mkdir(parents=True)
            path.touch()
        (self.root / "asap7" / "setRC.tcl").touch()
        evaluator = Contest2026OpenROADEvaluator(
            Contest2026Config("unit", benchmark.parent, self.root / "seed")
        )
        output = self.root / "evaluation"
        output.mkdir()
        tcl = output / "evaluate.tcl"
        evaluator._write_tcl(tcl=tcl, output=output)
        previous = tcl.read_bytes()
        evaluator._write_tcl(
            tcl=tcl,
            output=output,
            optimization_mode="timing_only",
            timing_recipe_id="legacy_setup",
        )
        self.assertEqual(tcl.read_bytes(), previous)
        self.assertEqual(
            load_json(self.engine.state_root / "parent.json"), self.parent.to_dict()
        )
