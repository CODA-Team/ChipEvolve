"""Recovery windows, not a substitute for actual campaign acceptance."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_platform_execution as boundary
from llm_usage import load_events
from platform_campaign import commit, restore
from platform_execution import PlatformExecution, write_record
from platform_model import tracked_completion


class DurableModelTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.ledger = self.root / "usage.jsonl"
        self.ledger.touch()
        self.settings = self.root / "settings.json"
        self.settings.write_text(json.dumps({"state_root": str(self.root)}))
        self.env = patch.dict(
            os.environ,
            {
                "DRP_EXECUTION_BACKEND": "platform",
                "DRP_CAMPAIGN_ID": "campaign-a",
                "DRP_ITER": "1",
                "DRP_LLM_USAGE_FILE": str(self.ledger),
                "DRP_PLATFORM_CONFIG": str(self.settings),
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.calls = []
        self.message = SimpleNamespace(
            content="choose CTS",
            tool_calls=[
                SimpleNamespace(
                    id="original-tool-id",
                    type="function",
                    function=SimpleNamespace(name="choose", arguments='{"value":2}'),
                )
            ],
        )
        self.response = SimpleNamespace(
            id="actual-request",
            model=None,
            usage={"input_tokens": 7, "output_tokens": 3},
            choices=[SimpleNamespace(message=self.message)],
        )

        def create(**kwargs):
            self.calls.append(kwargs)
            return self.response

        self.client = SimpleNamespace(
            base_url="codex-cli://test",
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        )
        self.payload = {
            "model": "actual-model",
            "messages": [{"role": "user", "content": "choose"}],
        }
        self.context = {"stage": "cts", "operation": "decide"}

    def test_replay_preserves_actual_ids_tools_usage_and_one_paid_call(self):
        tracked_completion(self.client, self.payload, self.context)
        replay = tracked_completion(self.client, self.payload, self.context)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(replay.choices[0].message.tool_calls[0].id, "original-tool-id")
        self.assertEqual(replay.usage, self.response.usage)
        self.assertEqual(len(load_events(self.ledger)), 2)
        self.assertEqual(load_events(self.ledger)[1]["total_tokens"], 10)

    def test_crash_after_response_fsync_recovers_original_terminal_once(self):
        with patch(
            "platform_model.finish_call",
            side_effect=RuntimeError("crash before terminal append"),
        ):
            with self.assertRaises(RuntimeError):
                tracked_completion(self.client, self.payload, self.context)
        self.assertEqual(len(load_events(self.ledger)), 1)
        tracked_completion(self.client, self.payload, self.context)
        tracked_completion(self.client, self.payload, self.context)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(load_events(self.ledger)), 2)

    def test_live_publisher_blocks_and_dead_pending_keeps_unknown_usage(self):
        with patch(
            "platform_model.write_record",
            side_effect=RuntimeError("crash before request cache"),
        ):
            with self.assertRaises(RuntimeError):
                tracked_completion(self.client, self.payload, self.context)
        with self.assertRaisesRegex(RuntimeError, "still running"):
            tracked_completion(self.client, self.payload, self.context)
        with patch("platform_model.is_alive", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "unknown usage"):
                tracked_completion(self.client, self.payload, self.context)
        self.assertEqual(len(self.calls), 0)
        self.assertIsNone(load_events(self.ledger)[1]["total_tokens"])

    def test_changed_request_does_not_replay_other_decision(self):
        tracked_completion(self.client, self.payload, self.context)
        tracked_completion(self.client, {**self.payload, "messages": []}, self.context)
        self.assertEqual(len(self.calls), 2)

    def test_corrupted_response_is_rejected_without_paid_duplicate(self):
        tracked_completion(self.client, self.payload, self.context)
        path = next((self.root / "model-responses").glob("*.json"))
        value = json.loads(path.read_text())
        value["response"]["message"]["content"] = "tampered"
        write_record(path, value)
        with self.assertRaisesRegex(RuntimeError, "hash changed"):
            tracked_completion(self.client, self.payload, self.context)
        self.assertEqual(len(self.calls), 1)


class CampaignCheckpointTests(unittest.TestCase):
    flow: Path
    state: Path
    client: boundary.FakeClient
    executor: PlatformExecution
    arguments: dict
    setUp = boundary.PlatformBoundaryTests.setUp

    # Reuse the fake archive fixture to exercise filesystem recovery itself.
    def test_checkpoint_restores_native_inputs_and_archive_without_submission(self):
        record = self.executor.execute(**self.arguments)
        design = self.flow / "designs/nangate45/aes"
        design.mkdir(parents=True)
        (design / "config_1.mk").write_text("original input")
        (self.flow / "tmp").mkdir()
        (self.flow / "tmp/lineage_iter1.json").write_text('{"trusted":true}')
        journal = {
            "campaign_id": record["campaign_id"],
            "platform": "nangate45",
            "design": "aes",
            "runs": 1,
            "owner": None,
        }
        write_record(self.state / "campaign.json", journal)
        commit(self.flow, self.state, 1, 1)
        saved = json.loads((self.state / "campaign.json").read_text())
        (design / "config_1.mk").write_text("partially mutated")
        (self.flow / "tmp/lineage_iter1.json").unlink()
        (self.flow / "results/nangate45/aes/run_1/3_place.odb").unlink()
        restore(self.flow, self.state, saved)
        self.assertEqual((design / "config_1.mk").read_text(), "original input")
        self.assertEqual(
            (self.flow / "tmp/lineage_iter1.json").read_text(), '{"trusted":true}'
        )
        self.assertEqual(len(self.client.submissions), 1)
        self.assertEqual(
            (self.flow / "results/nangate45/aes/run_1/3_place.odb").read_bytes(),
            b"actual-checkpoint-bytes",
        )

    def test_modified_checkpoint_is_rejected_before_restoring_files(self):
        (self.flow / "designs/nangate45/aes").mkdir(parents=True)
        journal = {
            "campaign_id": "campaign-a",
            "platform": "nangate45",
            "design": "aes",
            "runs": 1,
            "owner": None,
        }
        write_record(self.state / "campaign.json", journal)
        commit(self.flow, self.state, 1, -1)
        saved = json.loads((self.state / "campaign.json").read_text())
        Path(saved["checkpoint"], "receipt.json").write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "receipt changed"):
            restore(self.flow, self.state, saved)


if __name__ == "__main__":
    unittest.main()
