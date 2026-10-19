"""Executed Tcl, analysis and usage must refer to the same actual model calls."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import LLM_call


class ReplyEvidenceTests(unittest.TestCase):
    def run_iteration(self, retry):
        primary = (
            "### Analysis\nprimary refused\n### Tcl recipe\n```tcl\n# no commands\n```"
        )
        selected = "### Analysis\nretry stage diagnosis\n### Tcl recipe\n```tcl\neco_net_sink_report net_a\n```"
        responses = [
            (
                primary,
                {
                    "usage_reported": {
                        "input_tokens": 100,
                        "output_tokens": 10,
                        "cache_read_input_tokens": 20,
                    }
                },
            ),
            (
                selected,
                {
                    "usage_reported": {
                        "input_tokens": 300,
                        "output_tokens": 30,
                        "cache_read_input_tokens": 40,
                    }
                },
            ),
        ]
        if not retry:
            responses = [(selected, responses[0][1])]
        with (
            tempfile.TemporaryDirectory() as temporary,
            contextlib.ExitStack() as stack,
        ):
            root = Path(temporary)
            for name in (
                "STATIC_GUIDE_FILE",
                "HIST_FILE",
                "RPT_PATH",
                "DYNAMIC_CONTEXT_FILE",
                "PROMPT_DUMP",
                "ECO_OUT",
                "ANALYSIS_OUT",
                "LLM_SESSION_LOG",
            ):
                stack.enter_context(patch.object(LLM_call, name, root / name))
            LLM_call.RPT_PATH.write_text("new timing report")
            stack.enter_context(
                patch.object(
                    LLM_call,
                    "build_prompt",
                    return_value=("native strategy", "native facts"),
                )
            )
            stack.enter_context(
                patch.object(LLM_call, "call_claude", side_effect=responses)
            )
            stack.enter_context(patch.object(LLM_call, "append_llm_session_log"))
            stack.enter_context(
                patch(
                    "sys.argv",
                    [
                        "LLM_call.py",
                        "--max-iter",
                        "1",
                        "--claude-log-dir",
                        str(root / "logs"),
                    ],
                )
            )
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            LLM_call.main()
            return {
                "tcl": LLM_call.ECO_OUT.read_text(),
                "analysis": LLM_call.ANALYSIS_OUT.read_text(),
                "calls": [
                    json.loads(line)
                    for line in (root / "logs/token_log.jsonl").read_text().splitlines()
                ],
                "reply": next((root / "logs").glob("reply.*.md")).read_text(),
            }

    def test_successful_primary_keeps_original_action_and_usage(self):
        actual = self.run_iteration(False)
        self.assertEqual(
            LLM_call.parse_commands(actual["tcl"]), ["eco_net_sink_report net_a"]
        )
        self.assertIn("retry stage diagnosis", actual["analysis"])
        self.assertEqual(len(actual["calls"]), 1)
        self.assertEqual(actual["calls"][0]["input_tokens"], 100)

    def test_retry_analysis_describes_the_actually_executed_response(self):
        actual = self.run_iteration(True)
        self.assertEqual(
            LLM_call.parse_commands(actual["tcl"]), ["eco_net_sink_report net_a"]
        )
        self.assertIn("retry stage diagnosis", actual["analysis"])
        self.assertNotIn("primary refused", actual["analysis"])
        self.assertIn("retry stage diagnosis", actual["reply"])

    def test_retry_logs_each_real_call_without_dropping_its_cost(self):
        actual = self.run_iteration(True)
        self.assertEqual(len(actual["calls"]), 2)
        self.assertEqual(sum(c["input_tokens"] for c in actual["calls"]), 400)
        self.assertEqual(sum(c["output_tokens"] for c in actual["calls"]), 40)
        self.assertEqual(sum(c["cache_read_input_tokens"] for c in actual["calls"]), 60)
        self.assertTrue(all(c["total_cost_usd"] is None for c in actual["calls"]))


if __name__ == "__main__":
    unittest.main()
