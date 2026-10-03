"""One fresh query serves distinct setup/hold domains and compact path headers."""
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

import pytest

from openroad_app_data_foundation import resolved_timing
from openroad_app_data_foundation.engineering import timing_overview
from openroad_app_data_foundation.batch_reads import read_batch
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler
from test_eda_engineering import query_pair


def both_pair():
    parent, child = query_pair()
    child['timing_paths'][0].update(margin=0.03, crpr=0.02, path_type='max')
    hold = deepcopy(child['timing_paths'][0])
    hold.update(path_id='hold', check='hold', slack=0.1)
    child['timing_paths'].append(hold)
    child['timing_points'].extend({**p, 'path_id': 'hold', 'point_id': 'hold-' + p['point_id']}
                                 for p in list(child['timing_points']))
    return parent, child


def test_one_submission_returns_each_check_and_its_complete_pin_sequence(tmp_path, monkeypatch):
    parent, child = both_pair()
    store = DataStore(tmp_path / 'db.sqlite')
    calls = []
    try:
        store.register(parent)
        def submit(writer, client, sid, query):
            calls.append((sid, query))
            return {'run': {'run_id': 'native'}, 'snapshot_id': 'child'}
        def status(writer, client, run, wait):
            writer.register(child)
            return {'run_id': 'native', 'status': 'succeeded', 'snapshot_ids': ['child']}
        monkeypatch.setattr(resolved_timing, 'submit_timing_query', submit)
        monkeypatch.setattr(resolved_timing, 'timing_query_status', status)
        handler = object.__new__(Handler)
        handler.store, handler.auto_import, handler.execution_client = store, False, object()
        result = handler._get('/snapshots/s/timing-overview', {
            'resolve': '1', 'check': 'both', 'limit': '1', 'include_path_details': '1',
            'fields': 'checks.setup.paths,checks.hold.paths,checks.setup.path_details.data_pin_names'})
        assert len(calls) == 1
        assert result['checks']['setup']['paths'][0]['check'] == 'setup'
        assert result['checks']['setup']['paths'][0]['margin'] == 0.03
        assert result['checks']['setup']['paths'][0]['crpr'] == 0.02
        assert result['checks']['hold']['paths'][0]['check'] == 'hold'
        assert result['checks']['setup']['path_details'][0]['data_pin_names'] == ['u/A', 'u/Z', 'u/CLK']
        assert result['association_coverage']['status'] == 'complete'
        assert result['query_execution']['query_snapshot_id'] == 'child'
        header = handler._get('/snapshots/child/timing-paths/p', {'fields': 'timing_path.slack'})
        assert header['timing_path'] == {'slack': 0.2}
        assert 'timing_points' not in header
        assert 'full_details' in header['delivery']
    finally:
        store.close()


def test_both_checks_keep_partial_association_visible(tmp_path):
    parent, child = both_pair()
    child['timing_points'][-1].update(mapping_status='unmapped')
    store = DataStore(tmp_path / 'db.sqlite')
    try:
        store.register(parent)
        store.register(child)
        result = timing_overview(store, 'child', {'check': 'both', 'limit': '1'})
        assert result['checks']['setup']['association_coverage']['status'] == 'complete'
        assert result['checks']['hold']['association_coverage']['status'] == 'partial'
        assert result['association_coverage'] == {'status': 'partial', 'incomplete_checks': ['hold']}
        assert result['availability']['complete_association_aggregates']['status'] == 'unavailable'
    finally:
        store.close()


def test_bad_both_projection_recovers_compact_check_headers_without_new_analysis(tmp_path, monkeypatch):
    parent, child = both_pair()
    store = DataStore(tmp_path / 'recovery.sqlite')
    calls = []
    try:
        store.register(parent)
        store.register(child)
        def submit(*args):
            calls.append('native')
            return {'run': {'run_id': 'native'}, 'snapshot_id': 'child'}
        monkeypatch.setattr(resolved_timing, 'submit_timing_query', submit)
        monkeypatch.setattr(resolved_timing, 'timing_query_status', lambda *args: {
            'run_id': 'native', 'status': 'succeeded', 'snapshot_ids': ['child']})
        handler = Handler.__new__(Handler)
        handler.store, handler.auto_import, handler.execution_client = store, False, object()
        with pytest.raises(ValueError, match='unknown metadata field: paths') as error:
            handler._get('/snapshots/s/timing-overview', {
                'resolve': '1', 'check': 'both', 'include_path_details': '1', 'fields': 'paths'})
        route = str(error.value).split('correct the fields on ', 1)[1].split(' to reuse', 1)[0]
        url = urlsplit(route)
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        assert 'resolve' not in query and 'detail' not in query
        assert query['fields'] == 'checks.setup.paths,checks.hold.paths,object_facts_source,association_coverage'
        result = handler._get(url.path, query)
        assert result['checks']['setup']['paths'][0]['path_type'] == 'max'
        assert result['checks']['hold']['paths'][0]['check'] == 'hold'
        assert 'path_details' not in result['checks']['setup']
        assert calls == ['native']
    finally:
        store.close()


def test_batch_reuses_only_its_actual_completed_analysis_and_validates_each_request(tmp_path, monkeypatch):
    parent, child = both_pair()
    store = DataStore(tmp_path / 'db.sqlite')
    calls = []
    try:
        store.register(parent)
        def submit(writer, client, sid, query):
            calls.append(sid)
            return {'run': {'run_id': 'native'}, 'snapshot_id': 'child'}
        def status(writer, client, run, wait):
            writer.register(child)
            return {'run_id': 'native', 'status': 'succeeded', 'snapshot_ids': ['child']}
        monkeypatch.setattr(resolved_timing, 'submit_timing_query', submit)
        monkeypatch.setattr(resolved_timing, 'timing_query_status', status)
        handler = object.__new__(Handler)
        handler.store, handler.auto_import, handler.execution_client = store, False, object()
        response = read_batch({'requests': [
            '/snapshots/s/timing-overview?resolve=1&check=setup&limit=1&fields=paths',
            '/snapshots/s/timing-overview?resolve=1&check=hold&limit=1&fields=paths',
            '/snapshots/s/timing-overview?resolve=1&check=invalid&limit=1&fields=paths']}, handler._get)
        assert calls == ['s']
        setup, hold, invalid = response['results']
        assert setup['data']['paths'][0]['check'] == 'setup'
        assert hold['data']['paths'][0]['check'] == 'hold'
        assert setup['data']['query_execution']['run_id'] == hold['data']['query_execution']['run_id']
        assert hold['data']['query_execution']['reuse_scope'] == 'one fresh native analysis within this read batch'
        assert invalid['status'] == 'unavailable'
        assert response['failed_query_count'] == 1
    finally:
        store.close()
