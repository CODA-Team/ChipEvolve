"""Controller checks for the U4 slice, independent of private module sources."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from accept_common_goalevolve import audit, compare_replay, measured, validate_archive
from run_common_goalevolve import (
    configure_adapter_ceiling,
    host_environment,
    prepare_replay,
    run,
)


class CommonGoalControllerTests(unittest.TestCase):
    def test_private_adapter_cap_preserves_native_command_budget(self):
        from openroad_platform_contracts import PluginManifest, TaskSpec
        from openroad_platform_runtime import ProcessAdapter, ProcessOutcome

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            path = state / "plugins/openroad-data/openroad-data.plugin.json"
            path.parent.mkdir(parents=True)
            original = PluginManifest(
                plugin_id="test-command",
                plugin_version="1.0",
                adapter_entry=("unused-adapter",),
                capabilities=("test",),
                supported_arch=("x86_64",),
                default_timeout_seconds=3600,
                environment={
                    "EDA_ACTIVITY_LOCK": str(state / "activity.lock"),
                    "LANG": "C",
                },
            )
            path.write_text(json.dumps(original.to_dict()))
            configure_adapter_ceiling(state, {"adapter_timeout_ceiling_seconds": 7260})
            updated = PluginManifest.from_dict(json.loads(path.read_text()))
            self.assertNotIn("EDA_ACTIVITY_LOCK", updated.environment)
            self.assertEqual(updated.environment["LANG"], "C")
            spec = TaskSpec(
                task_id="native-timeout",
                project_id="p",
                design_id="d",
                plugin_id="test-command",
                timeout_seconds=7260,
            )
            adapter = ProcessAdapter()
            with patch.object(
                adapter.guardian,
                "run",
                return_value=ProcessOutcome(("unused-adapter",), 1, 0, timed_out=True),
            ) as execution:
                adapter.execute(updated, spec, workspace=state / "attempt")
            self.assertEqual(execution.call_args.kwargs["timeout_seconds"], 7260)
            self.assertEqual(updated.adapter_entry, original.adapter_entry)
            self.assertEqual(updated.capabilities, original.capabilities)

    def test_existing_login_environment_does_not_inject_other_source_roots(self):
        profile = {
            "profile_path": "/var/u4/profile.json",
            "state_root": "/var/u4",
            "agent_python": "/var/u4/envs/goal/bin/python",
        }
        with patch.dict(
            "os.environ",
            {
                "PYTHONPATH": "/sibling",
                "PYTHONHOME": "/another",
                "VIRTUAL_ENV": "/third",
            },
        ):
            env = host_environment(profile)
        self.assertEqual(env["GOALEVOLVE_PLATFORM_PROFILE"], profile["profile_path"])
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("PYTHONHOME", env)
        self.assertTrue(env["PATH"].startswith("/var/u4/envs/goal/bin"))

    def test_native_phase_commands_keep_four_student_policy_in_templates(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / "config.json").write_text(
                json.dumps({"agent_python": "/goal/python"})
            )
            with patch("run_common_goalevolve.step") as step:
                run(state, "init", None)
                command = step.call_args.args[2]
                self.assertIn("ast_graph", command)
                self.assertEqual(command[command.index("--max-rounds") + 1], "1")
                run(state, "evolve", None)
                self.assertEqual(step.call_args.args[2][-2:], ["--rounds", "1"])

    def test_native_cli_entrypoint_is_real(self):
        root = Path(__file__).resolve().parents[1] / "goalevolve"
        env = dict(os.environ)
        env.pop("GOALEVOLVE_PLATFORM_PROFILE", None)
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-m", "goalevolve.cli", "--help"],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("p0", result.stdout)

    def test_embedded_native_commands_have_valid_python_syntax(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / "config.json").write_text(
                json.dumps({"agent_python": "/goal/python", "source_seed": "/source"})
            )
            with patch("run_common_goalevolve.step") as step:
                for phase in ("build", "ast", "model-smoke"):
                    run(state, phase, None)
                    command = step.call_args.args[2]
                    compile(command[-1], "U4 " + phase, "exec")

    def test_independent_replay_preserves_native_recipe_and_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / "config.json").write_text(
                json.dumps({"agent_python": "/goal/python"})
            )
            root = state / "campaigns/aes_cipher_top/u4/campaign/rounds/round_001"
            root.mkdir(parents=True)
            (root / "round.json").write_text(
                json.dumps({"promoted_student": "student_2"})
            )
            for student in ("student_1", "student_2"):
                path = root / "students" / student / "artifacts/candidate.json"
                path.parent.mkdir(parents=True)
                path.write_text(
                    json.dumps(
                        {
                            "student_id": student,
                            "evaluation_error": None,
                            "implementation_diff": "new C++",
                            "checks": [{"passed": True}],
                            "metrics": {"drv_count": 0},
                            "source_commit": "content",
                        }
                    )
                )
            _, script = prepare_replay(state)
            compile(script.read_text(), "independent replay", "exec")
            receipt = json.loads((state / "replay/replay.json").read_text())
            self.assertEqual(receipt["student_id"], "student_2")
            self.assertFalse(receipt["used_build_donor"])
            self.assertIn("build_seed_root=None", script.read_text())
            self.assertIn("hypothesis['timing_recipe_id']", script.read_text())

    def test_explicit_replay_witness_can_precede_native_round_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / "config.json").write_text(
                json.dumps({"agent_python": "/goal/python"})
            )
            round_root = state / "campaigns/aes_cipher_top/u4/campaign/rounds/round_002"
            candidate = round_root / "students/student_2/artifacts/candidate.json"
            candidate.parent.mkdir(parents=True)
            candidate.write_text(
                json.dumps(
                    {
                        "student_id": "student_2",
                        "evaluation_error": None,
                        "implementation_diff": "new source",
                        "checks": [{"passed": True}],
                        "metrics": {"drv_count": 0},
                        "source_commit": "fixed-code",
                    }
                )
            )
            _, script = prepare_replay(state, candidate)
            compile(script.read_text(), "early replay", "exec")
            receipt = json.loads((state / "replay/replay.json").read_text())
            self.assertFalse(receipt["native_round_completed_at_selection"])
            self.assertIsNone(receipt["native_promoted_student"])
            self.assertFalse((round_root / "round.json").exists())


class CommonGoalEvidenceTests(unittest.TestCase):
    def test_prior_completed_round_cannot_certify_new_partial_round_or_its_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / "config.json").write_text("{}")
            campaign = state / "campaigns/aes_cipher_top/u4"
            baseline = campaign / "baseline/baseline.json"
            baseline.parent.mkdir(parents=True)
            baseline.write_text(json.dumps(self.result()))
            first = campaign / "campaign/rounds/round_001"
            second = first.parent / "round_002"
            first.mkdir(parents=True)
            second.mkdir()
            (first / "round.json").write_text('{"student_count": 4}')
            with self.assertRaisesRegex(
                ValueError, "Latest native round is incomplete"
            ):
                audit(state)
            (second / "round.json").write_text('{"student_count": 4}')
            for number in range(1, 5):
                path = second / f"students/student_{number}/artifacts/candidate.json"
                path.parent.mkdir(parents=True)
                value = self.result()
                value.update(
                    student_id=f"student_{number}",
                    source_commit="source",
                    evaluation_error=None,
                )
                path.write_text(json.dumps(value))
            replay = state / "replay/replay.json"
            replay.parent.mkdir()
            replay.write_text(
                json.dumps({"candidate_json": str(first / "candidate.json")})
            )
            with self.assertRaisesRegex(ValueError, "different native round"):
                audit(state)

    def test_registered_archive_requires_actual_output_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            request = {"source_files": {"policy.cc": "fixed-source"}}
            receipt = {
                "request": request,
                "output_files": {
                    "/run/qor.json": hashlib.sha256(b"measured").hexdigest()
                },
            }
            (folder / "leaf.json").write_text(json.dumps(receipt))
            for payload, valid in ((b"measured", True), (b"fabricated", False)):
                with zipfile.ZipFile(folder / "evidence.zip", "w") as archive:
                    archive.writestr("0/qor.json", payload)
                    archive.writestr(
                        "manifest.json",
                        json.dumps({"evidence_only": True, "receipt": receipt}),
                    )
                if valid:
                    validate_archive(folder, request)
                else:
                    with self.assertRaisesRegex(ValueError, "output bytes"):
                        validate_archive(folder, request)

    @staticmethod
    def result():
        return {
            "ok": True,
            "metrics": {
                "tns_abs_ns": 12.0,
                "dynamic_power_pw": 350000000000.0,
                "leakage_power_pw": 35000000.0,
                "drv_count": 0.0,
            },
            "checks": [
                {"name": name, "passed": True}
                for name in ("build", "flow", "metrics", "placement", "lec")
            ],
        }

    def test_real_checks_and_zero_drv_are_required(self):
        result = self.result()
        self.assertEqual(measured(result)["tns_abs_ns"], 12.0)
        result["metrics"]["drv_count"] = 1.0
        with self.assertRaisesRegex(ValueError, "DRV"):
            measured(result)
        result = self.result()
        result["checks"][-1]["passed"] = False
        with self.assertRaisesRegex(ValueError, "validity"):
            measured(result)

    def test_replay_compares_physical_metrics_without_overwriting_native_choice(self):
        first, second = self.result(), self.result()
        self.assertEqual(
            compare_replay(first, second)["tns_abs_ns"]["absolute_difference"], 0
        )
        second["metrics"]["tns_abs_ns"] = 13.0
        with self.assertRaisesRegex(ValueError, "replay differs"):
            compare_replay(first, second)


if __name__ == "__main__":
    unittest.main()
