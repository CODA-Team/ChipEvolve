"""Meaningful task-boundary checks for the local overnight driver."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from overnight_runtime import command, leaf
from prepare_overnight_eco import source_hashes


class OvernightRuntimeTests(unittest.TestCase):
    def test_native_probe_and_expert_prompt_change_frozen_source_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            for name in (
                "src/main.py",
                "OpenROAD_utils/probe.tcl",
                "prompts/AGENTS.md",
            ):
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("original")
            (source / "prompts/runtime.log").write_text("not source")
            before = source_hashes(source)
            (source / "OpenROAD_utils/probe.tcl").write_text("changed probe")
            (source / "prompts/AGENTS.md").write_text("changed strategy")
            after = source_hashes(source)
            self.assertEqual(before["src/main.py"], after["src/main.py"])
            self.assertNotEqual(
                before["OpenROAD_utils/probe.tcl"], after["OpenROAD_utils/probe.tcl"]
            )
            self.assertNotEqual(before["prompts/AGENTS.md"], after["prompts/AGENTS.md"])
            self.assertNotIn("prompts/runtime.log", after)

    def test_failed_leaf_preserves_real_log_and_never_claims_design_facts(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            request = work / "request.json"
            request.write_text(
                json.dumps(
                    {
                        "command": [
                            sys.executable,
                            "-c",
                            "print('actual command failure');raise SystemExit(7)",
                        ],
                        "cwd": str(work),
                        "capture": [],
                    }
                )
            )
            prior = Path.cwd()
            try:
                os.chdir(work)
                self.assertEqual(leaf(request), 7)
            finally:
                os.chdir(prior)
            manifest = json.loads((work / "query-data/manifest.json").read_text())
            self.assertTrue(manifest["evidence_only"])
            self.assertEqual(manifest["returncode"], 7)
            self.assertIn(
                "actual command failure", (work / "query-data/stdout.log").read_text()
            )

    def test_public_spec_records_resources_and_registered_input_before_submission(self):
        from openroad_platform_contracts import TaskSpec

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / "runtime.json").write_text(
                json.dumps({"client_python": sys.executable})
            )

            def admitted(root, key, spec):
                validated = TaskSpec.from_dict(spec)
                self.assertEqual(validated.resources.memory_bytes, 64 << 30)
                self.assertEqual(validated.resources.processes, 2048)
                self.assertEqual(validated.max_attempts, 1)
                path = Path(spec["staged_inputs"][0]["source"])
                self.assertTrue(path.is_file())
                self.assertEqual(
                    json.loads(path.read_text())["command"], ["compile", "--real"]
                )
                return "run-real"

            with patch("overnight_runtime.submit", side_effect=admitted), patch(
                "overnight_runtime.collect",
                return_value={"run": {"status": "succeeded"}},
            ):
                result = command(state, "compile", ["compile", "--real"], memory_gib=64)
            self.assertEqual(result["run"]["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
