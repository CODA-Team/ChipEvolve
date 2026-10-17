"""Recovery windows, not a substitute for actual campaign acceptance."""

import json
import os
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import platform_campaign as campaign
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

    def test_shared_goal_reaches_model_and_changed_goal_is_not_replayed(self):
        from eda_toolkits.objectives import SCHEMA, objective_id

        value = {
            "schema_version": SCHEMA, "design_id": "example", "reference_run_id": "reference",
            "conditions": {"libraries": [{"sha256": "lib"}], "sdc": {"sha256": "sdc"}},
            "constraints": {"core_area_um2_max": 100},
        }
        objective = self.root / "objective.json"
        for maximum in (100, 90):
            value["constraints"]["core_area_um2_max"] = maximum
            value["objective_id"] = objective_id(value)
            objective.write_text(json.dumps(value))
            with patch.dict(os.environ, {"EDA_PLATFORM_OBJECTIVE": str(objective)}):
                tracked_completion(self.client, self.payload, self.context)
            self.assertIn(value["objective_id"], self.calls[-1]["messages"][-1]["content"])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.payload["messages"]), 1)

    def test_corrupted_response_is_rejected_without_paid_duplicate(self):
        tracked_completion(self.client, self.payload, self.context)
        path = next((self.root / "model-responses").glob("*.json"))
        value = json.loads(path.read_text())
        value["response"]["message"]["content"] = "tampered"
        write_record(path, value)
        with self.assertRaisesRegex(RuntimeError, "hash changed"):
            tracked_completion(self.client, self.payload, self.context)
        self.assertEqual(len(self.calls), 1)

    def test_new_diagnosis_reaches_model_and_invalidates_response_replay(self):
        import hashlib

        packet = {
            "schema_version": "chip-evolve.design-context.v1",
            "scope": {"design_id": "example"},
        }
        context_path = self.root / "context.json"
        for fact in ("first diagnosed net", "different diagnosed net"):
            packet["summary"] = fact
            packet.pop("context_id", None)
            packet["context_id"] = hashlib.sha256(
                json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            context_path.write_text(json.dumps(packet))
            with patch.dict(os.environ, {"EDA_PLATFORM_CONTEXT": str(context_path)}):
                tracked_completion(self.client, self.payload, self.context)
            self.assertIn(fact, self.calls[-1]["messages"][-1]["content"])
        self.assertEqual(len(self.calls), 2)


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


class CopiedSourceResumeTests(unittest.TestCase):
    """Exercise the real preflight on an untracked prepared runtime copy."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "--quiet"], cwd=self.root, check=True)
        self.source = self.root / "runtime/source"
        self.flow = self.source / "flow"
        self.flow.mkdir(parents=True)
        (self.source / "config").mkdir()
        (self.source / "config/env.local.sh").write_text("export FIXED_TOOLS=1\n")
        self.controller = self.flow / "native_controller.py"
        self.controller.write_text("print('original controller')\n")
        self.index = self.source / "prepared-files.json"
        write_record(
            self.index, {"flow/native_controller.py": campaign.digest(self.controller)}
        )
        self.profile = self.root / "profile.json"
        self.profile.write_text("{}\n")
        self.state = self.root / "state"
        self.state.mkdir()
        backup = self.flow / "backup_dir/example/example"
        backup.mkdir(parents=True)
        self.manifest = backup / "campaign_manifest.json"
        self.manifest.write_text('{"campaign_id":"copied-source"}\n')
        (backup / "llm_usage_events.jsonl").touch()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(
            patch.object(
                campaign,
                "settings",
                return_value={
                    "profile_path": str(self.profile),
                    "state_root": str(self.state),
                },
            )
        )
        stack.enter_context(
            patch.object(campaign, "tool_fingerprint", return_value={"tools": "fixed"})
        )
        stack.enter_context(
            patch.object(campaign.importlib.metadata, "distributions", return_value=[])
        )
        stack.enter_context(patch.object(campaign, "assert_old_group_stopped"))
        stack.enter_context(
            patch.dict(os.environ, {"DRP_CAMPAIGN_OPTIONS": "fixed-options"})
        )
        stack.enter_context(
            patch.object(campaign, "__file__", str(self.flow / "platform_campaign.py"))
        )

    def save_campaign(self):
        write_record(
            self.state / "campaign.json",
            {
                "platform": "example",
                "design": "example",
                "campaign_id": "copied-source",
                "manifest_sha256": campaign.digest(self.manifest),
                "fingerprint": campaign.fingerprint(self.flow),
                "owner": None,
            },
        )

    def preflight(self):
        with patch("sys.argv", ["platform_campaign.py", "preflight"]):
            campaign.main()

    def test_changed_copied_controller_is_rejected_before_resume(self):
        self.save_campaign()
        self.controller.write_text("print('different controller')\n")
        with self.assertRaisesRegex(
            RuntimeError, "source, tools or installed environment changed"
        ):
            self.preflight()

    def test_missing_declared_controller_is_rejected_before_resume(self):
        self.save_campaign()
        self.controller.unlink()
        with self.assertRaisesRegex(
            RuntimeError, "source, tools or installed environment changed"
        ):
            self.preflight()

    def test_changed_preparation_index_is_rejected_before_resume(self):
        self.save_campaign()
        write_record(self.index, {"flow/native_controller.py": "0" * 64})
        with self.assertRaisesRegex(
            RuntimeError, "source, tools or installed environment changed"
        ):
            self.preflight()

    def test_unchanged_copy_accepts_new_generated_candidate_data(self):
        self.save_campaign()
        generated = self.flow / "designs/example/example/config_2.mk"
        generated.parent.mkdir(parents=True)
        generated.write_text("export CLOCK_PERIOD=123\n")
        self.preflight()

    def test_git_only_source_keeps_existing_resume_checks(self):
        self.index.unlink()
        subprocess.run(
            ["git", "add", str(self.controller.relative_to(self.root))],
            cwd=self.root,
            check=True,
        )
        self.save_campaign()
        self.preflight()
        self.controller.write_text("print('changed tracked controller')\n")
        with self.assertRaisesRegex(
            RuntimeError, "source, tools or installed environment changed"
        ):
            self.preflight()


if __name__ == "__main__":
    unittest.main()
