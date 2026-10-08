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
