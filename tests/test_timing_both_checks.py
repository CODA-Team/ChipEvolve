"""One fresh query serves distinct setup/hold domains and compact path headers."""
from copy import deepcopy

from openroad_app_data_foundation import resolved_timing
from openroad_app_data_foundation.engineering import timing_overview
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
