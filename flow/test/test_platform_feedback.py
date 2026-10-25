"""Feedback preserves evaluator identity and reuses its one export/import."""

import hashlib
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from platform_feedback import publish_feedback


class FeedbackClient:
    def __init__(self):
        self.submissions = []
        self.changed_hash = False

    def submit(self, task, *, idempotency_key):
        self.submissions.append((task, idempotency_key))
        return {"run": {"run_id": "feedback-producer", "status": "succeeded"}}

    def run(self, run_id):
        return {"run_id": run_id, "status": "succeeded"}

    def cancel(self, run_id):
        raise AssertionError("Completed feedback must not be cancelled: " + run_id)

    def artifacts(self, run_id):
        return [
            {
                "kind": "metadata",
                "store_key": "inputs/a2-evaluation.json",
                "sha256": "changed" if self.changed_hash else "actual",
                "artifact_id": "metadata-copy",
            },
            {
                "kind": "data_snapshot",
                "store_key": "snapshot.zip",
                "artifact_id": "bundle",
                "sha256": "bundle-sha",
            },
        ]


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name)
        self.client = FeedbackClient()
        self.evaluation = {
            "campaign_id": "campaign",
            "candidate_id": "candidate",
            "iteration": 2,
            "candidate_slot": 1,
            "stage": "eval_final",
            "design": "aes",
            "run_id": "actual-evaluator",
            "parent_run_id": "actual-physical",
            "idempotency_key": "campaign:2:1:eval_final",
            "task": {"labels": {"candidate_id": "candidate"}},
            "artifacts": [
                {
                    "store_key": "a2-evaluation.json",
                    "sha256": "actual",
                    "artifact_id": "actual-metadata",
                }
            ],
        }
        self.snapshot = (
            "a2-cp0-"
            + hashlib.sha256(b"campaign:2:1:eval_final:feedback").hexdigest()[:24]
        )
        self.posts = []
        self.attempts = 1
        self.physical = "actual-physical"
        self.import_exists = False
        self.lose_import_response = False

        def request(base, path, payload=None):
            if payload is not None:
                self.posts.append(payload)
                self.import_exists = True
                if self.lose_import_response:
                    self.lose_import_response = False
                    raise TimeoutError("Import completed but response was lost")
                return {"snapshot_id": self.snapshot}
            if path.startswith("/imports/"):
                if not self.import_exists:
                    raise HTTPError(base + path, 404, "not imported", Message(), None)
                return {
                    "data": {
                        "import_receipt": {
                            "status": "imported",
                            "attempts": self.attempts,
                        }
                    }
                }
            return {
                "data": {
                    "snapshot": {
                        "run_id": self.physical,
                        "producer_run_id": "feedback-producer",
                    }
                }
            }

        patched = patch("platform_feedback.request", side_effect=request)
        self.request = request
        patched.start()
        self.addCleanup(patched.stop)

    def publish(self):
        return publish_feedback(self.client, self.state, "http://data", self.evaluation)

    def test_replay_keeps_same_export_and_import_source(self):
        first = self.publish()
        second = self.publish()
        self.assertTrue(first["imported"])
        self.assertEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertEqual(len(self.client.submissions), 1)
        self.assertEqual(len(self.posts), 1)
        staged = self.client.submissions[0][0]["staged_inputs"][0]
        self.assertEqual(staged["artifact_id"], "actual-metadata")
        self.assertEqual(first["physical_run_id"], "actual-physical")

    def test_lost_import_response_recovers_without_reposting_completed_work(self):
        self.lose_import_response = True
        with self.assertRaisesRegex(TimeoutError, "response was lost"):
            self.publish()

        def read_only(base, path, payload=None):
            self.assertIsNone(payload, "Recovery must not reissue the import POST")
            return self.request(base, path, payload)

        with patch("platform_feedback.request", side_effect=read_only):
            result = self.publish()
        self.assertTrue(result["imported"])
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(len(self.client.submissions), 1)

    def test_unavailable_receipt_does_not_trigger_another_import(self):
        self.publish()

        def unavailable(base, path, payload=None):
            self.assertIsNone(payload)
            self.assertTrue(path.startswith("/imports/"))
            raise HTTPError(
                base + path, 503, "temporarily unavailable", Message(), None
            )

        with (
            patch("platform_feedback.request", side_effect=unavailable),
            self.assertRaises(HTTPError),
        ):
            self.publish()
        self.assertEqual(len(self.posts), 1)

    def test_changed_metadata_is_rejected_before_import(self):
        self.client.changed_hash = True
        with self.assertRaisesRegex(ValueError, "actual evaluation bytes"):
            self.publish()
        self.assertEqual(self.posts, [])

    def test_queue_wait_uses_campaign_budget_and_execution_keeps_short_budget(self):
        self.client.submit = lambda task, **kwargs: {
            "run": {"run_id": "feedback-producer", "status": "queued"}
        }
        states = iter(
            [
                {"run_id": "feedback-producer", "status": "queued"},
                {"run_id": "feedback-producer", "status": "running"},
                {"run_id": "feedback-producer", "status": "succeeded"},
            ]
        )
        self.client.run = lambda run_id: next(states)
        self.client.cancel = lambda run_id: self.fail(
            "A valid queued export must not be cancelled"
        )
        with (
            patch("platform_feedback.time.monotonic", side_effect=[0, 0, 200, 400]),
            patch("platform_feedback.time.sleep"),
        ):
            result = publish_feedback(
                self.client,
                self.state,
                "http://data",
                self.evaluation,
                timeout_seconds=180,
                wait_timeout_seconds=600,
            )
        self.assertTrue(result["imported"])

    def test_wrong_physical_lineage_is_rejected_and_response_preserved(self):
        self.physical = "unrelated-physical"
        with self.assertRaisesRegex(ValueError, "lineage"):
            self.publish()
        record = json.loads(next(self.state.glob("iteration-*/*.json")).read_text())
        self.assertIn("import_response", record)
        self.assertNotIn("imported", record)

    def test_duplicate_import_attempt_is_not_accepted_as_idempotent(self):
        self.attempts = 2
        with self.assertRaisesRegex(ValueError, "lineage"):
            self.publish()


if __name__ == "__main__":
    unittest.main()
