"""Original JSON queries rank the complete source and preserve literal row identity."""
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler


@pytest.fixture
def original(tmp_path):
    rows = [{'startpoint': 'z', 'endpoint': 'q', 'slack': -1, 'path_type': 'max', 'flag': True,
             'points': [{'pin': '很长的原始名字', 'load': 1.3e-14} for _ in range(100)]},
            {'startpoint': 'a', 'endpoint': 'q', 'slack': -1, 'path_type': 'max', 'flag': 1},
            {'startpoint': 'b', 'endpoint': 'q', 'slack': None, 'path_type': 'max', 'flag': None}]
    rows.extend({'startpoint': f'p{i}', 'endpoint': 'q', 'slack': i, 'path_type': 'min'} for i in range(45))
    rows.append({'startpoint': 'last', 'endpoint': 'q', 'slack': -9, 'path_type': 'max'})
    rows[0].update(capacitance=1.3e-14, nested={'value': 5})
    rows[1].update(capacitance=None, nested=None)
    rows[2]['nested'] = {}
    source = tmp_path / 'source.json'
    source.write_text(json.dumps({'checks': rows}, ensure_ascii=False))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    store = DataStore(tmp_path / 'd.sqlite')
    store.register({'snapshot': {'snapshot_id': 's', 'design_id': 'chip', 'revision_id': 'r', 'run_id': 'run', 'stage': 'route', 'created_at': '2026-10-03'},
                    'run_summary': {'timing_context': {'producer': {'artifacts': {'source.json': {'sha256': digest}}}}}})
    handler = Handler.__new__(Handler)
    handler.store, handler.auto_import, handler.native_root = store, False, tmp_path
    yield handler, source, rows
    store.close()


def query(handler, **options):
    return handler._get('/snapshots/s/artifacts/files/json', {'path': 'source.json', 'json_path': '$.checks', **options})


def test_full_array_ranking_projection_and_original_index_recovery(original):
    handler, source, rows = original
    options = {'sort_field': 'slack', 'tie_fields': 'startpoint,endpoint', 'filters': '{"path_type":"max"}',
               'fields': 'startpoint,endpoint,slack', 'limit': '1'}
    selected = query(handler, **options)
    assert selected['original_array_count'] == 49 and selected['count'] == 4
    assert selected['rows'] == [{'startpoint': 'last', 'endpoint': 'q', 'slack': -9}]
    assert selected['source_array_indices'] == [48] and selected['next_offset'] == 1
    second = query(handler, **{**options, 'offset': '1'})
    assert second['rows'][0]['startpoint'] == 'a' and second['source_array_indices'] == [1]
    full_query = {k: v[0] for k, v in parse_qs(urlsplit(second['delivery']['full_details']).query).items()}
    restored = handler._get('/snapshots/s/artifacts/files/json', full_query)
    assert restored['rows'] == [rows[1]] and restored['count'] == 4
    assert selected['source']['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert query(handler, sort_field='slack', order='desc', filters='{"path_type":"max"}', limit='4')['rows'][-1]['slack'] is None


def test_filters_keep_boolean_number_and_null_meanings_distinct(original):
    handler, _, _ = original
    assert query(handler, filters='{"flag":true}', fields='startpoint')['rows'] == [{'startpoint': 'z'}]
    assert query(handler, filters='{"flag":1}', fields='startpoint')['rows'] == [{'startpoint': 'a'}]
    assert query(handler, filters='{"flag":null}', fields='startpoint')['rows'] == [{'startpoint': 'b'}]
    assert query(handler, filters='{"path_type":"missing"}')['count'] == 0


def test_sparse_original_fields_preserve_absence_and_literal_null_without_defaults(original):
    handler, _, _ = original
    result = query(handler, filters='{"path_type":"max"}', fields='startpoint,capacitance,nested.value')
    assert result['rows'] == [{'startpoint': 'z', 'capacitance': 1.3e-14, 'nested': {'value': 5}},
                             {'startpoint': 'a', 'capacitance': None, 'nested': None},
                             {'startpoint': 'b', 'nested': {}}, {'startpoint': 'last'}]
    assert 'capacitance' in result['delivery']['requested_fields_absent_in_some_returned_rows']
    # A page with no capacitance still uses the complete source field declaration.
    last = query(handler, fields='startpoint,capacitance', offset='48', limit='1')
    assert last['rows'] == [{'startpoint': 'last'}]
    maximum = query(handler, sort_field='capacitance', order='desc', fields='startpoint,capacitance', limit='1')
    assert maximum['rows'] == [{'startpoint': 'z', 'capacitance': 1.3e-14}]


@pytest.mark.parametrize('options, error', [({'sort_field': 'unknown'}, 'ranking field does not exist'),
    ({'json_path': '$.missing'}, 'existing array'), ({'json_path': '$..'}, 'invalid json_path'),
    ({'fields': 'unknown'}, 'projection field does not exist'), ({'order': 'worst'}, 'asc\\|desc'),
    ({'filters': '{"slack":[1,2]}'}, 'scalar row field'), ({'path': '../outside.json'}, 'design and revision')])
def test_invalid_source_queries_are_explicit(original, options, error):
    handler, _, _ = original
    with pytest.raises(ValueError, match=error):
        query(handler, **options)
