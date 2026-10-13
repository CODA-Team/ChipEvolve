"""Transport regression without changing or simulating ECO decisions."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import platform_codex


class CodexTransportTests(unittest.TestCase):
    def test_verbatim_expert_context_real_usage_and_failed_call_boundary(self):
        events = "\n".join(
            json.dumps(row)
            for row in [
                {"type": "thread.started", "thread_id": "session"},
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 100,
                        "cached_input_tokens": 20,
                        "output_tokens": 30,
                    },
                },
            ]
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(
                platform_codex, "__file__", str(root / "src/platform_codex.py")
            ):

                def execute(argv, **kwargs):
                    self.assertIn("original expert guide", kwargs["input"])
                    self.assertIn("actual design context", kwargs["input"])
                    self.assertIn("read-only", argv)
                    self.assertIn("--ignore-rules", argv)
                    kwargs["stdout"].write(events)
                    Path(argv[argv.index("--output-last-message") + 1]).write_text(
                        "```tcl\neco_resize_gate gate cell\n```"
                    )
                    return SimpleNamespace(returncode=0, stdout=events, stderr="")

                with patch.object(
                    platform_codex.subprocess, "run", side_effect=execute
                ):
                    reply, meta = platform_codex.call_codex(
                        "original expert guide", "actual design context"
                    )
                self.assertIn("eco_resize_gate", reply)
                self.assertEqual(meta["usage_reported"]["cache_read_input_tokens"], 20)
                self.assertEqual(meta["usage_reported"]["input_tokens"], 80)
                self.assertIsNone(meta["total_cost_usd"])
                self.assertFalse(meta["monetary_cost_measured"])
                with patch.object(
                    platform_codex.subprocess,
                    "run",
                    return_value=SimpleNamespace(
                        returncode=1, stdout="", stderr="provider failed"
                    ),
                ):
                    with self.assertRaisesRegex(RuntimeError, "transport failed"):
                        platform_codex.call_codex("guide", "context")


if __name__ == "__main__":
    unittest.main()
