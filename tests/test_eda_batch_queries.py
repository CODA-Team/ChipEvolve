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


def test_catalog_filters_real_query_origins_before_projection_in_batches(api):
    base, handler = api
    for identifier, parent in [('query-chip-flow-stage', None), ('s-query-0123456789ab', None),
                               ('separately-created-path', 's')]:
        handler.store.register({'snapshot': {'snapshot_id': identifier, 'design_id': 'chip',
            'revision_id': 'r', 'run_id': 'run', 'stage': 'finish', 'created_at': '2026-10-02'},
            'run_summary': {'timing_context': {'parent_snapshot_id': parent}}})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def ids(origin):
        data = json.load(opener.open(base + '/snapshots?origin=' + origin + '&fields=snapshot_id'))['data']
        return {row['snapshot_id'] for row in data['snapshots']}
    assert ids('flow') == {'s', 'query-chip-flow-stage'}
    assert ids('query') == {'s-query-0123456789ab', 'separately-created-path'}
    assert ids('all') == ids('flow') | ids('query')
    request = urllib.request.Request(base + '/query', data=json.dumps({
        'requests': ['/snapshots?origin=flow&fields=snapshot_id']}).encode(), method='POST',
        headers={'Content-Type': 'application/json'})
    rows = json.load(opener.open(request))['results'][0]['data']['snapshots']
    assert {row['snapshot_id'] for row in rows} == ids('flow')


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


def test_batch_keeps_independent_successes_and_each_actual_error(api):
    base, _ = api
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    paths = ['/snapshots/s/summary', '/snapshots/absent/summary',
             '/snapshots/s/summary?fields=run_summary.invented', '/runs/run/metrics?name=AREA']
    request = urllib.request.Request(base + '/query', json.dumps({'requests': paths}).encode(),
                                     headers={'Content-Type': 'application/json'})
    with opener.open(request, timeout=2) as response:
        result = json.load(response)
    assert result['failed_query_count'] == 2
    assert [item['status'] for item in result['results']] == ['available', 'not_found', 'unavailable', 'available']
    assert 'absent' in result['results'][1]['data']['error']
    assert 'unknown metadata field' in result['results'][2]['data']['error']
    assert result['results'][3]['data']['metrics'][0]['value'] == 85


def test_dependent_http_reads_resolve_actual_snapshot_then_read_its_metrics(api):
    base, _ = api
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    body = {'requests': ['/snapshots?fields=snapshot_id,run_id',
                         '/snapshots/{sid}/summary', '/runs/{rid}/metrics?name=area'],
            'bindings': {'sid': {'request': 0, 'pointer': '/data/snapshots/0/snapshot_id'},
                         'rid': {'request': 0, 'pointer': '/data/snapshots/0/run_id'}}}
    request = urllib.request.Request(base + '/query', json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
    with opener.open(request, timeout=2) as response:
        result = json.load(response)
    assert result['failed_query_count'] == 0
    assert result['results'][1]['scope']['snapshot_id'] == 's'
    assert result['results'][2]['data']['metrics'][0]['value'] == 85


def test_original_stage_discovery_keeps_substage_metrics_separate(tmp_path):
    from openroad_app_data_foundation.artifacts import run_inventory
    root = tmp_path / 'flow'
    logs = root / 'logs/platform/chip/revision'
    logs.mkdir(parents=True)
    (logs / '5_1_grt.json').write_text(json.dumps({'globalroute__design__instance__area': 85}))
    (logs / '5_2_route.json').write_text(json.dumps({'detailedroute__route__wirelength': 12}))
    (logs / '6_report.json').write_text(json.dumps({'finish__design__instance__area': 85}))
    store = DataStore(tmp_path / 'inventory.sqlite')
    try:
        store.register({'snapshot': {'snapshot_id': 's', 'design_id': 'chip', 'revision_id': 'revision',
                                    'run_id': 'run', 'stage': 'finish', 'created_at': '2026-10-01'}})
        result = run_inventory(store, 's', root, stage='route')
        assert len(result['stages']) == 1
        row = result['stages'][0]
        assert row['original_metrics']['relative_path'].endswith('/5_2_route.json')
        assert not row['original_metrics']['has_area']
        assert [(r['relative_path'].rsplit('/', 1)[-1], r['has_area']) for r in row['metric_reports']] == [
            ('5_1_grt.json', True), ('5_2_route.json', False)]
        selected = run_inventory(store, 's', root, stage='route', metric_names=('instance__area',))
        reports = selected['stages'][0]['metric_reports']
        assert reports[0]['metric_values'] == [{'raw_key': 'globalroute__design__instance__area', 'value': 85,
                                              'source': 'logs/platform/chip/revision/5_1_grt.json'}]
        assert reports[1]['metric_values'] == []
        with pytest.raises(ValueError, match='unknown original flow stage'):
            run_inventory(store, 's', root, stage='invented')
    finally:
        store.close()
