"""The persistent native process is admitted once and receives registered inputs."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import platform_execution
from platform_execution import export_best_checkpoint, leaf, submit


class ExecutionTests(unittest.TestCase):
    def test_selected_odb_and_route_evidence_survive_view_export(self):
        for improved in (False, True):
            with (
                self.subTest(improved=improved),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                source, workspace = root / "source", root / "workspace"
                dynamic = source / "prompts/dynamic"
                (dynamic / "snapshots").mkdir(parents=True)
                (workspace / "inputs").mkdir(parents=True)
                original = b"registered original routed ODB"
                selected = b"selected improved routed ODB" if improved else original
                (workspace / "inputs/6_final.odb").write_bytes(original)
                (workspace / "inputs/6_final.spef").write_bytes(b"original SPEF")
                profile = root / "profile.json"
                profile.write_text(
                    json.dumps(
                        {
                            "python": "/env/eco/python",
                            "environment": {
                                "ASAP7_PDK": "/exact/pdk",
                                "OPENROAD_BIN": "openroad",
                            },
                            "parent_run_id": "original",
                            "snapshot_id": "original-objects",
                            "input_route_drc": 0,
                        }
                    )
                )

                def native(
                    command,
                    *,
                    dynamic=dynamic,
                    selected=selected,
                    source=source,
                    improved=improved,
                    workspace=workspace,
                    **kwargs,
                ):
                    if command[0] == "/env/eco/python":
                        (dynamic / "snapshots/best_drt.odb").write_bytes(selected)
                        (source / "outputs/final_eco.spef").write_bytes(
                            b"improved SPEF" if improved else b"original SPEF"
                        )
                        if improved:
                            (source / "outputs/final_drc_report.txt.count").write_text(
                                "7"
                            )
                    else:
                        script = (workspace / "export_best.tcl").read_text()
                        self.assertNotIn("write_db", script)
                        for suffix in ("def", "v", "sdc"):
                            (source / "outputs" / ("final_eco." + suffix)).write_text(
                                "native exported view"
                            )
                    return 0

                with (
                    patch.object(
                        platform_execution,
                        "__file__",
                        str(source / "src/platform_execution.py"),
                    ),
                    patch("platform_execution.Path.cwd", return_value=workspace),
                    patch("platform_execution.subprocess.call", side_effect=native),
                ):
                    self.assertEqual(leaf(profile), 0)
                output = workspace / "session-output"
                self.assertEqual((output / "final_eco.odb").read_bytes(), selected)
                self.assertEqual(
                    (output / "final_eco.spef").read_bytes(),
                    b"improved SPEF" if improved else b"original SPEF",
                )
                evidence = json.loads((output / "route-evidence.json").read_text())
                self.assertEqual(evidence["route_drc"], 7 if improved else 0)
                self.assertIn(
                    "native" if improved else "input baseline", evidence["origin"]
                )

    def test_failed_view_export_does_not_publish_a_selected_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "prompts/dynamic/snapshots").mkdir(parents=True)
            (root / "prompts/dynamic/snapshots/best_drt.odb").write_bytes(b"selected")
            output = root / "outputs"
            output.mkdir()
            with (
                patch("platform_execution.Path.cwd", return_value=root),
                patch("platform_execution.subprocess.call", return_value=1),
            ):
                self.assertEqual(
                    export_best_checkpoint(
                        root,
                        {"ASAP7_PDK": "/pdk", "OPENROAD_BIN": "openroad"},
                        output,
                        root / "input.sdc",
                    ),
                    1,
                )
            self.assertFalse((output / "final_eco.odb").exists())

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
