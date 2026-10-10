"""A completed producer must become queryable, or leave a retryable failure."""
import hashlib
import json
from pathlib import Path
import threading
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest

from openroad_platform_contracts import ContractError
from openroad_app_data_foundation.bundle import import_bundle, import_ready_bundles
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler, ThreadingHTTPServer


class ProducerClient:
    def __init__(self, root, count=1):
        self.root, self.count = root, count
        self.downloads = 0
        self.pages = []
        self.fail = False
        for i in range(count):
            manifest = {'snapshot_id': f'snap-{i}', 'design_id': 'aes',
                        'revision_id': f'rev-{i}', 'run_id': f'run-{i}', 'stage': 'finish',
                        'created_at': '2026-10-10T00:00:00Z'}
            with zipfile.ZipFile(root / f'{i}.zip', 'w') as archive:
                archive.writestr('manifest.json', json.dumps(manifest))

    def runs(self, *, status, limit, offset):
        assert status == 'succeeded'
        self.pages.append(offset)
        return [{'run_id': f'run-{i}'} for i in range(offset, min(self.count, offset + limit))]

    def run(self, run_id):
        return {'status': 'succeeded'}

    def artifacts(self, run_id):
        index = int(run_id.split('-')[-1])
        path = self.root / f'{index}.zip'
        return [{'artifact_id': f'artifact-{index}', 'kind': 'data_snapshot',
                 'store_key': 'query-data.zip', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                 'size_bytes': path.stat().st_size}]

    def download_artifact_to(self, run_id, artifact_id, destination):
        self.downloads += 1
        if self.fail:
            raise ContractError('temporary producer artifact unavailable')
        index = int(run_id.split('-')[-1])
        Path(destination).write_bytes((self.root / f'{index}.zip').read_bytes())


def test_specified_import_is_durable_idempotent_and_queryable(tmp_path):
    client = ProducerClient(tmp_path)
    store = DataStore(tmp_path / 'facts.sqlite')
    first = import_bundle(store, client, 'run-0', 'artifact-0')
    assert first['import_receipt']['status'] == 'imported'
    assert first['import_receipt']['snapshot_id'] == 'snap-0'
    store.close()
    store = DataStore(tmp_path / 'facts.sqlite')
    try:
        second = import_bundle(store, client, 'run-0', 'artifact-0')
        assert second == first
        assert client.downloads == 1
        assert len(store.snapshots()) == 1
        handler = object.__new__(Handler)
        handler.store = store
        assert handler._get('/imports/artifact-0', {})['import_receipt'] == first['import_receipt']
        with pytest.raises(ContractError, match='different producer'):
            import_bundle(store, client, 'run-1', 'artifact-0')
    finally:
        store.close()


def test_failed_import_retries_after_restart_without_duplicate_snapshot(tmp_path):
    client = ProducerClient(tmp_path)
    client.fail = True
    store = DataStore(tmp_path / 'facts.sqlite')
    with pytest.raises(ContractError, match='unavailable'):
        import_bundle(store, client, 'run-0', 'artifact-0')
    assert not store.imported('artifact-0')
    assert store.snapshots() == []
    assert store.import_receipt('artifact-0')['status'] == 'failed'
    store.close()
    store = DataStore(tmp_path / 'facts.sqlite')
    try:
        client.fail = False
        result = import_bundle(store, client, 'run-0', 'artifact-0')
        assert result['import_receipt']['attempts'] == 2
        assert result['import_receipt']['error'] is None
        assert len(store.snapshots()) == 1
    finally:
        store.close()


def test_completed_result_older_than_first_page_is_not_lost(tmp_path):
    client = ProducerClient(tmp_path, count=101)
    store = DataStore(tmp_path / 'facts.sqlite')
    try:
        assert import_ready_bundles(store, client) == 101
        assert client.pages == [0, 100]
        assert store.snapshot('snap-100')['producer_run_id'] == 'run-100'
        assert import_ready_bundles(store, client) == 0
        assert client.downloads == 101
    finally:
        store.close()


def test_automatic_retry_is_bounded_but_explicit_retry_still_works(tmp_path):
    client = ProducerClient(tmp_path)
    client.fail = True
    store = DataStore(tmp_path / 'facts.sqlite')
    try:
        for _ in range(5):
            assert import_ready_bundles(store, client) == 0
        assert client.downloads == 3
        assert not store.imported('artifact-0')
        client.fail = False
        result = import_bundle(store, client, 'run-0', 'artifact-0')
        assert result['import_receipt']['attempts'] == 4
    finally:
        store.close()


def test_concurrent_http_imports_return_one_queryable_snapshot(tmp_path):
    client = ProducerClient(tmp_path)
    store = DataStore(tmp_path / 'facts.sqlite')
    handler = type('ImportHandler', (Handler,), {'store': store, 'execution_client': client})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'

    def post():
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request = urllib.request.Request(base + '/snapshots/from-run',
            data=json.dumps({'run_id': 'run-0', 'artifact_id': 'artifact-0'}).encode(),
            headers={'Content-Type': 'application/json'})
        with opener.open(request, timeout=5) as response:
            return json.load(response)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: post(), range(2)))
        assert results[0] == results[1]
        assert client.downloads == 1
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(base + '/imports/artifact-0', timeout=5) as response:
            receipt = json.load(response)['data']['import_receipt']
        assert receipt['status'] == 'imported'
        with opener.open(base + '/snapshots/snap-0/summary?detail=full', timeout=5) as response:
            assert json.load(response)['data']['snapshot']['producer_run_id'] == 'run-0'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        store.close()
