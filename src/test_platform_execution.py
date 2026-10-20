"""The persistent native process is admitted once and receives registered inputs."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import platform_execution
from platform_execution import leaf, submit


class ExecutionTests(unittest.TestCase):
    def test_native_loop_receives_its_output_directory_before_first_best(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            (source / "prompts/dynamic").mkdir(parents=True)
            workspace = root / "workspace"
            workspace.mkdir()
            profile = root / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "python": "/env/eco/python",
                        "environment": {},
                        "parent_run_id": "original",
                        "snapshot_id": "original-objects",
                    }
                )
            )

            def native(*args, **kwargs):
                self.assertTrue((source / "outputs").is_dir())
                return 1

            with (
                patch.object(
                    platform_execution,
                    "__file__",
                    str(source / "src/platform_execution.py"),
                ),
                patch("platform_execution.Path.cwd", return_value=workspace),
                patch("platform_execution.subprocess.call", side_effect=native),
            ):
                self.assertEqual(leaf(profile), 1)

    def test_session_uses_registered_inputs_and_data_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            profile = state / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "kernel_url": "http://localhost:1234",
                        "data_url": "http://localhost:1235",
                        "state_root": str(state),
                        "snapshot_id": "objects-real",
                        "metrics_snapshot_id": "metrics-real",
                        "parent_run_id": "flow-real",
                        "python": "/env/eco/python",
                        "experiment_id": "session-real",
                        "input_artifacts": {
                            "odb": "art-real-odb",
                            "sdc": "art-real-sdc",
                            "spef": "art-real-spef",
                        },
                    }
                )
            )
            facts = MagicMock()
            facts.resolve_scope.return_value = {"snapshot_id": "objects-real"}
            facts.get_stage_summary.return_value = {"counts": {"instances": 10}}
            facts.get_metrics.return_value = {"tns": -1}
            kernel = MagicMock()
            kernel.submit.return_value = {"run": {"run_id": "eco-real"}}
            kernel.run.return_value = {"run_id": "eco-real", "status": "succeeded"}
            kernel.artifacts.return_value = []
            kernel.resources.return_value = {}
            with (
                patch("eda_ai_client.EdaAiClient", return_value=facts),
                patch("openroad_platform_client.KernelClient", return_value=kernel),
            ):
                submit(profile)
            spec = kernel.submit.call_args.args[0]
            from openroad_platform_contracts import TaskSpec

            TaskSpec.from_dict(spec)
            self.assertEqual(spec["resources"]["memory_bytes"], 24 << 30)
            self.assertEqual(spec["labels"]["parent_run_id"], "flow-real")
            self.assertEqual(spec["inputs"]["extractor_command"][0], "/env/eco/python")
            self.assertEqual(spec["staged_inputs"][1]["artifact_id"], "art-real-odb")
            facts.resolve_scope.assert_called_once_with(snapshot_id="objects-real")
            configured = json.loads(profile.read_text())
            configured["memory_gib"] = 16
            profile.write_text(json.dumps(configured))
            with (
                patch("eda_ai_client.EdaAiClient", return_value=facts),
                patch("openroad_platform_client.KernelClient", return_value=kernel),
            ):
                submit(profile)
            resized = kernel.submit.call_args.args[0]
            TaskSpec.from_dict(resized)
            self.assertEqual(resized["resources"]["memory_bytes"], 16 << 30)
            self.assertEqual(resized["resources"]["cpu_cores"], 8)

    def test_failure_never_falls_back_to_unmanaged_process(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            profile = state / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "kernel_url": "http://localhost:1234",
                        "data_url": "http://localhost:1235",
                        "state_root": str(state),
                        "snapshot_id": "s",
                        "metrics_snapshot_id": "m",
                        "parent_run_id": "r",
                        "python": "/env/python",
                        "experiment_id": "x",
                        "input_artifacts": {},
                    }
                )
            )
            with patch("eda_ai_client.EdaAiClient") as client:
                client.return_value.resolve_scope.side_effect = RuntimeError(
                    "data unavailable"
                )
                with self.assertRaisesRegex(RuntimeError, "data unavailable"):
                    submit(profile)


if __name__ == "__main__":
    unittest.main()
