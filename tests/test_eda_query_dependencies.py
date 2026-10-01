"""A linked query can only use prior actual observations, never guessed identifiers."""
import urllib.parse

import pytest

from openroad_app_data_foundation.batch_reads import read_batch


def test_linked_value_is_url_encoded_once_and_preserves_native_name():
    native_name = '模块/u[0]/Q$net'
    calls = []
    def get(path, query):
        calls.append((path, query))
        if path == '/snapshots/s/objects':
            return {'objects': [{'name': native_name}]}
        assert urllib.parse.unquote(path.rsplit('/', 1)[-1]) == native_name
        assert query['name'] == native_name
        return {'checked_name': native_name}
    body = {'requests': ['/snapshots/s/objects', '/snapshots/s/pins/{pin}?name={pin}'],
            'bindings': {'pin': {'request': 0, 'pointer': '/data/objects/0/name'}}}
    result = read_batch(body, get)
    assert len(calls) == 2 and result['failed_query_count'] == 0
    assert result['results'][1]['data']['checked_name'] == native_name


@pytest.mark.parametrize('spec', [
    {'request': 1, 'pointer': '/data/name'}, {'request': 0, 'pointer': '/data/missing'},
    {'request': 0, 'pointer': '/data/absent'}, {'request': 0, 'pointer': '/data/objects'},
    {'request': True, 'pointer': '/data/name'}, {'request': 0, 'pointer': '/data/objects/8/name'}])
def test_failed_binding_stays_explicit_and_independent_later_read_still_runs(spec):
    calls = []
    def get(path, query):
        calls.append(path)
        return {'name': 'actual', 'absent': None, 'objects': [{'name': 'pin'}]}
    body = {'requests': ['/snapshots/s', '/snapshots/{value}/summary', '/snapshots/independent'],
            'bindings': {'value': spec}}
    result = read_batch(body, get)
    assert result['failed_query_count'] == 1
    assert result['results'][1]['status'] == 'unavailable'
    assert 'ValueError' in result['results'][1]['data']['error']
    assert calls == ['/snapshots/s', '/snapshots/independent']


def test_failed_source_is_not_replaced_with_another_snapshot():
    def get(path, query):
        raise KeyError('requested snapshot does not exist')
    result = read_batch({'requests': ['/snapshots/absent', '/snapshots/{sid}/summary'],
        'bindings': {'sid': {'request': 0, 'pointer': '/data/snapshot_id'}}}, get)
    assert [item['status'] for item in result['results']] == ['not_found', 'unavailable']
    assert 'binding source request failed' in result['results'][1]['data']['error']
