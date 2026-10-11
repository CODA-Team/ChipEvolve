"""Boundary tests; these simulated tasks do not claim physical-flow acceptance."""
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from platform_execution import (
    PlatformExecution,
    find_predecessor,
    project_archive,
    write_record,
)


def archive_bytes():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('flow/results/3_place.odb', b'actual-checkpoint-bytes')
        archive.writestr('flow/results/3_place.sdc', b'clock-constraints')
        archive.writestr('flow/combined.log', b'upstream\nplacement\n')
    return buffer.getvalue()


class FakeClient:
    def __init__(self):
        self.uploads = []
        self.submissions = []
        self.runs = {}
        self.lose_reply = False

    def upload_input(self, content):
        self.uploads.append(content)
        return {'input_id': f'input-{len(self.uploads)}'}

    def submit(self, task, *, idempotency_key):
        self.submissions.append((task, idempotency_key))
        if idempotency_key not in self.runs:
            self.runs[idempotency_key] = {'run_id': f'run-{len(self.runs) + 1}', 'status': 'succeeded'}
        if self.lose_reply:
            self.lose_reply = False
            raise ConnectionError('submit reply was lost after acceptance')
        return {'run': self.runs[idempotency_key]}

    def run(self, run_id):
        return next(row for row in self.runs.values() if row['run_id'] == run_id)

    def artifacts(self, run_id):
        return [{'kind': 'flow_archive', 'artifact_id': 'archive-' + run_id,
                 'sha256': hashlib.sha256(archive_bytes()).hexdigest(), 'store_key': 'flow-artifacts.zip'},
                {'kind': 'raw_design_database', 'artifact_id': 'odb-' + run_id,
                 'sha256': hashlib.sha256(b'actual-checkpoint-bytes').hexdigest(),
                 'store_key': 'flow/results/3_place.odb'},
                {'kind': 'raw_constraints', 'artifact_id': 'sdc-' + run_id,
                 'sha256': hashlib.sha256(b'clock-constraints').hexdigest(),
                 'store_key': 'flow/results/3_place.sdc'}]

    def artifact_bytes(self, run_id, artifact_id):
        return archive_bytes()

    def materialize_artifact(self, run_id, artifact_id, destination):
        Path(destination).write_bytes(archive_bytes())


class PlatformBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.flow = self.root / 'flow'
        self.flow.mkdir()
        self.state = self.root / 'tasks'
        self.profile = self.root / 'profile.json'
        self.profile.write_text('{}')
        self.config = self.root / 'candidate.mk'
        self.config.write_text('export CORE_UTILIZATION = 50\n')
        self.sdc = self.root / 'candidate.sdc'
        self.sdc.write_text('create_clock -period 0.82 clk\n')
        self.client = FakeClient()
        self.executor = PlatformExecution(self.client, self.flow, self.state,
                                          self.profile, 'campaign-a', 8, 3600)
        self.arguments = {'iteration': 1, 'slot': 1, 'candidate_id': 'candidate-a',
                          'platform': 'nangate45', 'design': 'aes', 'stage': 'place',
                          'config': self.config, 'sdc': self.sdc}

    def test_lost_submit_reply_reuses_exact_request_and_one_run(self):
        self.client.lose_reply = True
        with self.assertRaises(ConnectionError):
            self.executor.execute(**self.arguments)
        self.assertEqual(len(self.client.runs), 1)
        record = self.executor.execute(**self.arguments)
        self.assertEqual(record['run_id'], 'run-1')
        self.assertEqual(len(self.client.runs), 1)
        self.assertEqual(len(self.client.uploads), 3)
        self.assertEqual(self.client.submissions[0], self.client.submissions[1])
        self.assertEqual((self.flow / 'logs/nangate45_aes_run1.log').read_bytes(),
                         b'upstream\nplacement\n')

    def test_completed_task_reprojects_without_submission_or_duplicate_logs(self):
        first = self.executor.execute(**self.arguments)
        (self.flow / 'results/nangate45/aes/run_1/3_place.odb').unlink()
        second = self.executor.execute(**self.arguments)
        self.assertEqual(first['run_id'], second['run_id'])
        self.assertEqual(len(self.client.submissions), 1)
        self.assertEqual((self.flow / 'logs/nangate45_aes_run1.log').read_bytes(),
                         b'upstream\nplacement\n')

    def test_large_stage_archive_uses_public_materialization(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('flow/results/3_place.odb', b'actual-checkpoint-bytes')
            archive.writestr('flow/results/3_place.sdc', b'clock-constraints')
            archive.writestr('flow/combined.log', b'upstream\nplacement\n')
            archive.writestr('flow/reports/large.rpt', b'x' * (5 << 20))
        content = buffer.getvalue()
        self.assertGreater(len(content), 4 << 20)
        inventory = self.client.artifacts('run-1')
        inventory[0]['sha256'] = hashlib.sha256(content).hexdigest()
        self.client.artifacts = lambda run_id: inventory

        def reject_whole_download(run_id, artifact_id):
            raise RuntimeError('whole-artifact download response limit')

        materialized = []

        def materialize(run_id, artifact_id, destination):
            materialized.append((run_id, artifact_id))
            Path(destination).write_bytes(content)

        self.client.artifact_bytes = reject_whole_download
        self.client.materialize_artifact = materialize
        record = self.executor.execute(**self.arguments)
        self.assertEqual(materialized, [('run-1', 'archive-run-1')])
        self.assertEqual(record['status'], 'succeeded')
        self.assertEqual((self.flow / 'reports/nangate45/aes/run_1/large.rpt').stat().st_size,
                         5 << 20)
        self.assertEqual((self.flow / 'results/nangate45/aes/run_1/3_place.odb').read_bytes(),
                         b'actual-checkpoint-bytes')

    def test_changed_candidate_inputs_do_not_reuse_old_success(self):
        self.executor.execute(**self.arguments)
        self.config.write_text('export CORE_UTILIZATION = 48\n')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.executor.execute(**self.arguments)
        self.assertEqual(len(self.client.submissions), 1)

    def test_clone_uses_explicit_donor_and_requires_matching_constraints(self):
        record = self.executor.execute(**self.arguments)
        second = {**record, 'candidate_slot': 2, 'run_id': 'other-producer'}
        write_record(self.state / 'iteration-1/slot-2-place.json', second)
        selected = find_predecessor(self.state, self.flow, 'campaign-a', 1,
                                    'nangate45', 'aes', 1, 'cts', donor_slot=2)
        self.assertEqual(selected['run_id'], 'other-producer')
        (self.flow / 'results/nangate45/aes/run_1/3_place.sdc').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'matching ODB/SDC'):
            find_predecessor(self.state, self.flow, 'campaign-a', 1,
                             'nangate45', 'aes', 1, 'cts', donor_slot=2)

    def test_other_campaign_cannot_supply_matching_checkpoint(self):
        record = self.executor.execute(**self.arguments)
        write_record(self.state / 'iteration-1/slot-1-place.json',
                     {**record, 'campaign_id': 'other-campaign'})
        with self.assertRaisesRegex(ValueError, 'successful EF producer'):
            find_predecessor(self.state, self.flow, 'campaign-a', 1,
                             'nangate45', 'aes', 1, 'cts')

    def test_evaluation_references_physical_run_without_replacing_outputs(self):
        physical = self.executor.execute(**self.arguments)
        self.client.artifacts = lambda run_id: [
            {'kind': 'extractor_log', 'artifact_id': 'eval-log', 'store_key': 'extractor.log'}]
        self.client.artifact_bytes = lambda run_id, artifact_id: b'tns -4.36\nwns -0.04\n'
        arguments = {**self.arguments, 'stage': 'eval_place',
                     'evaluation': {'cp0_ns': 0.792, 'clock_port': 'clk',
                                    'library_patterns': ['/frozen/typical.lib']}}
        evaluated = self.executor.execute(**arguments)
        self.assertEqual(evaluated['parent_run_id'], physical['run_id'])
        self.assertEqual(evaluated['task']['labels']['run_type'], 'analysis')
        self.assertEqual(evaluated['task']['labels']['analysis_of_run_id'], physical['run_id'])
        self.assertEqual(evaluated['task']['inputs']['evaluation'], arguments['evaluation'])
        self.assertEqual(evaluated['task']['staged_inputs'][-1]['artifact_id'], 'archive-run-1')
        self.assertEqual((self.flow / 'logs/eval_tns_place_run1.log').read_bytes(),
                         b'tns -4.36\nwns -0.04\n')
        self.assertEqual((self.flow / 'results/nangate45/aes/run_1/3_place.odb').read_bytes(),
                         b'actual-checkpoint-bytes')

    def test_invalid_archive_does_not_replace_current_outputs(self):
        self.executor.execute(**self.arguments)
        original = self.flow / 'results/nangate45/aes/run_1/3_place.odb'
        archive_path = self.root / 'bad.zip'
        for member in ('flow/results/../../escape', 'flow/results/new.odb'):
            with zipfile.ZipFile(archive_path, 'w') as archive:
                archive.writestr(member, b'bad')
            with self.assertRaises(ValueError):
                project_archive(archive_path, self.flow, 'nangate45', 'aes', 1)
            self.assertEqual(original.read_bytes(), b'actual-checkpoint-bytes')


if __name__ == '__main__':
    unittest.main()
