"""Read-only HTTP and batch reads never launch a tool or register a snapshot."""
import json
import threading
import urllib.request
import urllib.error

import pytest

from test_data_foundation import pack
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.relationships import object_relationships
from openroad_app_data_foundation.server import Handler, ThreadingHTTPServer


class UnexpectedExecution:
    def __getattr__(self, name):
        raise AssertionError('read unexpectedly accessed execution method ' + name)


@pytest.mark.parametrize('path', [
    '/snapshots/snap-1/net-inventory', '/snapshots/snap-1/analysis-setup',
    '/snapshots/snap-1/timing-overview?resolve=1',
    '/snapshots/snap-1/pins/p/engineering',
    '/snapshots/snap-1/instances/u/pin-inventory',
    '/snapshots/snap-1/instances/u/power',
    '/snapshots/snap-1/compare/other/inventory?include_native_area=1',
])
def test_get_refuses_implicit_tool_execution(tmp_path, path):
    store = DataStore(tmp_path / 'd.sqlite')
    store.register(pack())
    handler = object.__new__(Handler)
    handler.store, handler.execution_client, handler.auto_import = store, UnexpectedExecution(), True
    from urllib.parse import urlsplit, parse_qs
    parsed = urlsplit(path)
    try:
        with pytest.raises(ValueError, match='requires POST'):
            handler._get(parsed.path, {k:v[0] for k,v in parse_qs(parsed.query).items()})
        assert handler._get('/designs', {})['designs'][0]['design_id'] == 'chip'
    finally:
        store.close()


def test_read_only_http_rejects_registration_and_allows_read_batch(tmp_path):
    db = tmp_path / 'd.sqlite'
    writer = DataStore(db)
    writer.register(pack())
    writer.close()
    store = DataStore(db, read_only=True)
    handler = type('ReadOnlyHandler', (Handler,), {'store':store, 'execution_client':UnexpectedExecution()})
    server = ThreadingHTTPServer(('127.0.0.1',0), handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f'http://127.0.0.1:{server.server_port}'
    def post(path, body):
        return opener.open(urllib.request.Request(base+path, data=json.dumps(body).encode(),
            headers={'Content-Type':'application/json'}), timeout=2)
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            post('/snapshots', pack())
        assert error.value.code == 403
        with post('/query', {'requests':['/snapshots/snap-1/summary']}) as response:
            assert json.load(response)['failed_query_count'] == 0
        assert len(store.snapshots()) == 1
    finally:
        server.shutdown();server.server_close();thread.join();store.close()


def test_relationships_include_pins_and_declare_unresolved_endpoints(tmp_path):
    value = pack()
    value['entities'].append({'object_id':'p', 'kind':'pin', 'name':'u1/Z', 'parent_id':'top/u1'})
    value['relations'] = [
        {'relation_id':'a', 'subject_id':'p', 'predicate':'connected_to', 'object_id':'net:n1'},
        {'relation_id':'b', 'subject_id':'net:n1', 'predicate':'loads', 'object_id':'missing'}]
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(value)
        instance = object_relationships(store, 'snap-1', 'u1', {'kind':'instance','limit':'1'})
        assert instance['count'] == 1 and instance['relations'][0]['subject_id'] == 'p'
        net = object_relationships(store, 'snap-1', 'n1', {'kind':'net','limit':'1'})
        assert net['count'] == 2 and net['next_offset'] == 1
        last = object_relationships(store, 'snap-1', 'n1', {'kind':'net','limit':'1','offset':'1'})
        assert last['coverage']['missing_entity_ids'] == ['missing']
        assert last['availability']['relation_endpoints']['status'] == 'unavailable'
    finally:
        store.close()
