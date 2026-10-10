"""Feedback preserves evaluator identity and reuses its one export/import."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

        def request(base, path, payload=None):
            if payload is not None:
                self.posts.append(payload)
                return {"snapshot_id": self.snapshot}
            if path.startswith("/imports/"):
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
        self.assertEqual(self.posts[0], self.posts[1])
        staged = self.client.submissions[0][0]["staged_inputs"][0]
        self.assertEqual(staged["artifact_id"], "actual-metadata")
        self.assertEqual(first["physical_run_id"], "actual-physical")

    def test_changed_metadata_is_rejected_before_import(self):
        self.client.changed_hash = True
        with self.assertRaisesRegex(ValueError, "actual evaluation bytes"):
            self.publish()
        self.assertEqual(self.posts, [])

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
