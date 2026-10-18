"""Cross-kernel analysis inputs are immutable and verified before submission."""
import hashlib
from unittest.mock import patch
import pytest
from openroad_platform_client import KernelError
from eda_toolkits.inputs import FileChunks, SnapshotExecutionClient


def test_sequence_upload_is_bounded_and_preserves_exact_bytes(tmp_path):
    p = tmp_path / 'original.odb'
    content = b'abc' * 100
    p.write_bytes(content)
    chunks = FileChunks(p, chunk_size=31)
    assert len(chunks) == 10
    assert b''.join(chunks) == content
    assert max(map(len, chunks)) == 31


def test_archive_digest_mismatch_never_submits_a_task(tmp_path):
    class Source:
        def artifact_locator(self, run_id, artifact_id):
            return {'sha256':'changed', 'size_bytes':3, 'path':str(tmp_path / 'x')}
    client = SnapshotExecutionClient('http://127.0.0.1:18700', source_client=Source())
    ref = {'artifact_id':'old', 'run_id':'old-run', 'sha256':'expected', 'size_bytes':3}
    task = {'inputs':{'input_provenance':[ref]}, 'staged_inputs':[{'artifact_id':'old','destination':'x'}]}
    with patch.object(client, 'artifact_locator', side_effect=KernelError('missing', status=404)), \
         patch.object(client, '_call') as transport:
        with pytest.raises(ValueError, match='identity differs'):
            client.submit(task)
        transport.assert_not_called()


def test_verified_input_reused_without_archive_execution(tmp_path):
    path = tmp_path / 'input';path.write_bytes(b'abc')
    digest = hashlib.sha256(b'abc').hexdigest()
    class Source:
        reads = 0
        def artifact_locator(self, run_id, artifact_id):
            self.reads += 1
            return {'sha256':digest, 'size_bytes':3, 'path':str(path)}
    source = Source()
    client = SnapshotExecutionClient('http://127.0.0.1:18700', source_client=source)
    ref = {'artifact_id':'old', 'run_id':'old-run', 'sha256':digest, 'size_bytes':3}
    with patch.object(client, 'upload_input_chunks', return_value={'input_id':'new','sha256':digest,'size_bytes':3}):
        assert client._upload_original(ref) == 'new'
        assert client._upload_original(ref) == 'new'
        assert source.reads == 1


def test_missing_fixed_sdc_is_rejected_before_native_task():
    from eda_toolkits.inputs import snapshot_inputs
    snapshot = {
        'run_summary': {'timing_context': {
            'executor': 'openroad', 'constraints': 'original.sdc', 'libraries': [],
            'parasitic_mode': 'spef', 'parasitics': 'original.spef',
        }},
        'source_artifacts': [
            {'category': 'raw_design_database', 'logical_path': 'original.odb', 'artifact_id': 'odb'},
            {'category': 'raw_parasitics', 'logical_path': 'original.spef', 'artifact_id': 'spef'},
        ],
    }
    with pytest.raises(ValueError, match='original.sdc'):
        snapshot_inputs(snapshot)


def test_low_memory_submission_defers_admission_to_execution_foundation():
    client = SnapshotExecutionClient('http://127.0.0.1:18700')
    with (
        patch(
            "eda_toolkits.environment.available_memory_bytes", return_value=1
        ) as memory,
        patch.object(
            client, "_call", return_value={"run": {"status": "queued"}}
        ) as transport,
    ):
        assert (
            client.submit({"inputs": {"adapter": "opensta"}})["run"]["status"]
            == "queued"
        )
        memory.assert_not_called()
        transport.assert_called_once()


def test_native_thread_limit_cannot_expand_past_server_budget():
    from eda_toolkits.openroad.sta_inputs import native_command
    assert native_command({}, 'test.tcl')[1:3] == ['-threads', '2']
    for invalid in (0, 9, True, '8'):
        with pytest.raises(ValueError, match='threads'):
            native_command({'threads': invalid}, 'test.tcl')
