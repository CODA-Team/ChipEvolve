"""Real HTTP regressions for mixed metrics/inventory batches and read concurrency."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
from openroad_app_data_foundation.connections import ReadPool
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler


@pytest.fixture(params=[False, True])
def api(tmp_path, request):
    database = DataStore(tmp_path / 'batch.sqlite')
    database.register({
        'snapshot': {'snapshot_id': 's', 'design_id': 'chip', 'revision_id': 'r',
                     'run_id': 'run', 'stage': 'finish', 'created_at': '2026-10-01'},
        'observations': [
            {'observation_id': 'metric:finish__design__instance__area', 'kind': 'metric', 'value': 85},
            {'observation_id': 'metric:finish__flow__platform__distance_units', 'kind': 'metric', 'value': '1um'}]})
    pool = ReadPool(tmp_path / 'batch.sqlite') if request.param else None
    class TestHandler(Handler):
        store = database
        read_pool = pool
        auto_import = False
        execution_client = None
        request_lock = threading.Lock()
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), TestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', TestHandler
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        if pool is not None:
            pool.close()
        database.close()


def test_metric_and_snapshot_batch_matches_individual_queries_without_write_lock(api):
    base, handler = api
    paths = ['/snapshots?fields=snapshot_id', '/snapshots/s/summary',
             '/runs/run/metrics?stage=finish&name=AREA&include_raw=1']
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    individual = []
    for path in paths:
        with opener.open(base + path, timeout=2) as response:
            individual.append(json.load(response))
    request = urllib.request.Request(base + '/query', json.dumps({'requests': paths}).encode(),
                                     headers={'Content-Type': 'application/json'})
    with handler.request_lock:
        with opener.open(request, timeout=2) as response:
            batch = json.load(response)
    assert batch['results'] == individual
    area = batch['results'][2]['data']['metrics'][0]
    assert area['name'] == 'AREA' and area['value'] == 85
    assert 'filler area excluded' in area['quantity_scope']


def test_batch_rejects_external_sources(api):
    base, _ = api
    request = urllib.request.Request(base + '/query', json.dumps({
        'requests': ['https://example.com/snapshots/s']}).encode(),
        headers={'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with pytest.raises(urllib.error.HTTPError) as caught:
        opener.open(request, timeout=2)
    assert caught.value.code == 400
    assert 'local snapshot/run' in json.load(caught.value)['error']
