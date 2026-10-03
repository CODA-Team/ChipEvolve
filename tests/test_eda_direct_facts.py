"""Direct engineering facts must match native definitions and retain missing data."""
import pytest

from openroad_app_data_foundation.discovery import list_objects
from openroad_app_data_foundation.engineering import object_statistics
from openroad_app_data_foundation.pin_geometry import pin_engineering
from openroad_app_data_foundation.queries import list_metrics_for_run
from openroad_app_data_foundation.repository import DataStore
from tests.test_eda_engineering import sample


def test_micron_region_matches_dbu_boundary_and_complete_macro_counts(tmp_path):
    pack = sample()
    pack['physical_context'][0]['bbox'] = dict(x_min=20140, y_min=0, x_max=22000, y_max=2000)
    pack['entities'].extend([
        {'object_id': 'macro', 'kind': 'instance', 'name': 'ram', 'attributes': {'is_macro': 1}},
        {'object_id': 'unknown', 'kind': 'instance', 'name': 'unknown', 'attributes': {}}])
    pack['physical_context'].extend([
        {'object_id': key, 'bbox': dict(x_min=20140, y_min=0, x_max=22000, y_max=2000)}
        for key in ('macro', 'unknown')])
    store = DataStore(tmp_path / 'region.sqlite')
    try:
        store.register(pack)
        base = {'kind': 'instance', 'intersection': 'positive_area'}
        dbu = list_objects(store, 's', {**base, 'region': '20140,0,22000,2000'})
        um = list_objects(store, 's', {**base, 'region': '10.070,0,11,1', 'region_units': 'um'})
        assert um['objects'] == dbu['objects'] and um['count'] == 3
        stats = object_statistics(store, 's', {**base, 'region': '10.070,0,11,1',
            'region_units': 'um', 'group_by': 'is_macro', 'limit': '1'})
        assert stats['object_count'] == 3 and stats['truncated']
        all_stats = object_statistics(store, 's', {**base, 'group_by': 'is_macro',
            'region': '10.070,0,11,1', 'region_units': 'um'})
        assert {row['value']: row['count'] for row in all_stats['groups']} == {None: 1, 0: 1, 1: 1}
        # 10.070 must stay exactly 20140 DBU: adjacent boxes only touch.
        adjacent = {**base, 'region': '9,0,10.070,1', 'region_units': 'um'}
        assert list_objects(store, 's', adjacent)['count'] == 0
        assert list_objects(store, 's', {**adjacent, 'intersection': 'touching'})['count'] == 3
        assert list_objects(store, 's', {**base, 'region': '10.070,0,10.070,1', 'region_units': 'um'})['count'] == 0
        with pytest.raises(ValueError, match='region_units'):
            list_objects(store, 's', {**adjacent, 'region_units': 'mm'})
    finally:
        store.close()


def test_regional_pages_and_statistics_exclude_zero_area_objects_without_losing_touching_points(tmp_path):
    pack = sample()
    pack['entities'].extend([
        {'object_id': 'point', 'kind': 'instance', 'name': 'point', 'attributes': {'is_macro': 0}},
        {'object_id': 'line', 'kind': 'instance', 'name': 'line', 'attributes': {'is_macro': 1}},
        {'object_id': 'pin', 'kind': 'pin', 'name': 'u/a', 'attributes': {}}])
    pack['physical_context'].extend([
        {'object_id': 'point', 'bbox': dict(x_min=2, y_min=2, x_max=2, y_max=2)},
        {'object_id': 'line', 'bbox': dict(x_min=3, y_min=2, x_max=3, y_max=8)},
        {'object_id': 'pin', 'bbox': dict(x_min=4, y_min=4, x_max=4, y_max=4)}])
    store = DataStore(tmp_path / 'zero-area-region.sqlite')
    try:
        store.register(pack)
        base = {'region': '1,1,9,9', 'intersection': 'positive_area', 'sort': 'name'}
        assert list_objects(store, 's', base)['count'] == 1
        assert object_statistics(store, 's', {**base, 'group_by': 'kind'})['object_count'] == 1
        assert list_objects(store, 's', {**base, 'kind': 'pin'})['count'] == 0
        assert list_objects(store, 's', {**base, 'kind': 'instance', 'name': 'point'})['count'] == 0
        touching = {**base, 'intersection': 'touching', 'limit': '1'}
        pages, offset = [], 0
        while True:
            page = list_objects(store, 's', {**touching, 'offset': str(offset)})
            pages.extend(row['object_id'] for row in page['objects'])
            if page['next_offset'] is None:
                break
            offset = page['next_offset']
        assert set(pages) == {'i', 'point', 'line', 'pin'}
        assert object_statistics(store, 's', {**touching, 'group_by': 'kind'})['object_count'] == 4
    finally:
        store.close()


def test_multi_metric_selection_preserves_units_sources_missing_names_and_pages(tmp_path):
    pack = sample()
    pack['observations'] = [
        {'observation_id': 'metric:finish__flow__platform__time_units', 'kind': 'metric', 'value': '1ns'},
        {'observation_id': 'metric:finish__custom__hold__ws', 'kind': 'metric', 'value': -.2},
        {'observation_id': 'metric:finish__timing__setup__ws', 'kind': 'metric', 'value': .25,
         'evidence': [{'artifact_id': 'original'}]},
        {'observation_id': 'metric:finish__timing__hold__ws', 'kind': 'metric', 'value': -.1,
         'evidence': [{'artifact_id': 'original'}]}]
    store = DataStore(tmp_path / 'metrics.sqlite')
    try:
        store.register(pack)
        query = {'stage': 'finish', 'names': 'WS,WNS,HOLD_WS,absent', 'fields': 'name,value,unit,status', 'limit': '1'}
        first = list_metrics_for_run(store, 'run', query)
        assert first['count'] == 3 and first['missing_names'] == ['absent']
        assert first['next_offset'] == 1 and first['evidence'] == [{'artifact_id': 'original', 'resolution': 'unverified'}]
        rows = list_metrics_for_run(store, 'run', {**query, 'limit': '10'})['metrics']
        assert {row['name']: row['value'] for row in rows} == {'WS': .25, 'WNS': 0, 'HOLD_WS': -.1}
        assert all(row['unit'] == 'ns' for row in rows)
        raw = list_metrics_for_run(store, 'run', {'include_raw': '1', 'name_contains': 'hold__ws'})
        assert len(raw['raw_metrics']) == 1 and raw['raw_metrics'][0]['value'] == -.2
        assert raw['raw_metrics'][0]['raw_key'] == 'finish__custom__hold__ws'
        assert [row['name'] for row in raw['metrics']] == ['HOLD_WS', 'HOLD_WNS']
        for names in ('', 'WS,', ','.join(['WS'] * 33)):
            with pytest.raises(ValueError, match='names'):
                list_metrics_for_run(store, 'run', {'names': names})
        with pytest.raises(ValueError, match='projection field'):
            list_metrics_for_run(store, 'run', {'fields': 'invented'})
    finally:
        store.close()


@pytest.mark.parametrize('kind,getter', [('iterm', 'getAvgXY'), ('bterm', 'getFirstPinLocation')])
@pytest.mark.parametrize('native_status,position', [('succeeded', '1 20140 -2000'),
    ('succeeded', '0 0 0'), ('failed', None), ('running', None), ('succeeded', 'malformed')])
def test_pin_getter_success_failure_and_original_native_identity(tmp_path, monkeypatch, kind, getter, native_status, position):
    pack = sample()
    pack['entities'].append({'object_id': kind + ':12', 'kind': 'pin', 'name': r'u/a\[0\]',
        'attributes': {'native_id': '12'}, 'evidence': [{'artifact_id': 'odb'}]})
    def native(store, client, snapshot_id, payload, native_root):
        assert getter in payload['script'] and 'u/a' not in payload['script']
        assert ' $b 12]' in payload['script'] and payload['wait_seconds'] == 120
        return {'status': native_status, 'run': {'run_id': 'actual'}, 'source': {'artifact_id': 'report'},
            'excerpt': {'text': f'EDA_PIN_POSITION {position}\nEDA_PIN_BBOX 20000 -2100 20200 -1900\n', 'truncated': False}}
    monkeypatch.setattr('openroad_app_data_foundation.pin_geometry.submit_native_query', native)
    store = DataStore(tmp_path / 'pin.sqlite')
    try:
        store.register(pack)
        if position == 'malformed':
            with pytest.raises(ValueError, match='incomplete or malformed'):
                pin_engineering(store, None, 's', kind + ':12', tmp_path)
            return
        result = pin_engineering(store, None, 's', kind + ':12', tmp_path)
        if native_status != 'succeeded':
            assert result['native_query']['status'] == native_status
            assert result['native_query']['report']['run']['run_id'] == 'actual'
            assert 'position_dbu' not in result['pin']
        else:
            assert result['pin']['bbox_dbu'] == [20000, -2100, 20200, -1900]
            assert getter in result['pin']['position_basis']
            assert result['evidence'] == [{'artifact_id': 'report'}, {'artifact_id': 'odb', 'resolution': 'unverified'}]
            if position.startswith('1'):
                assert result['pin']['position_um'] == [10.07, -1]
            else:
                assert result['pin']['position_success'] is False and result['pin']['position_dbu'] is None
    finally:
        store.close()


@pytest.mark.parametrize('port', [True, False])
def test_pin_query_joins_same_snapshot_ownership_and_connection_with_projection(tmp_path, monkeypatch, port):
    from openroad_app_data_foundation.server import Handler
    pack = sample()
    pack['entities'][0]['attributes']['orientation'] = 'MY'
    pin = {'object_id': ('bterm' if port else 'iterm') + ':12', 'kind': 'pin',
           'name': 'port' if port else 'u/CLK',
           'attributes': {'native_id': '12', 'direction': 'INPUT', 'native_pin_signal_type': 'CLOCK'}}
    if not port:
        pin['parent_id'] = 'i'
    pack['entities'].append(pin)
    pack['relations'] = [{'relation_id': 'pin-net', 'subject_id': pin['object_id'],
                          'predicate': 'connected_to', 'object_id': 'n'}]
    calls = []
    def native(*args):
        calls.append(args[3])
        return {'status': 'succeeded', 'run': {'run_id': 'original'}, 'source': {'artifact_id': 'report'},
            'excerpt': {'text': 'EDA_PIN_POSITION 1 20140 -2000\nEDA_PIN_BBOX 20000 -2100 20200 -1900\n', 'truncated': False}}
    monkeypatch.setattr('openroad_app_data_foundation.pin_geometry.submit_native_query', native)
    store = DataStore(tmp_path / 'joined.sqlite')
    try:
        store.register(pack)
        handler = Handler.__new__(Handler)
        handler.store, handler.auto_import, handler.execution_client, handler.native_root = store, False, object(), tmp_path
        path = '/snapshots/s/pins/' + pin['object_id'] + '/engineering'
        fields = 'pin.position_um,pin.position_success,native_connection.net_name,native_connection.signal_type,instance'
        selected = handler._get(path, {'fields': fields})
        assert len(calls) == 1 and not calls[0]['with_timing']
        assert selected['pin'] == {'position_um': [10.07, -1], 'position_success': True}
        assert selected['native_connection'] == {'net_name': 'signal', 'signal_type': 'SIGNAL'}
        if port:
            assert selected['instance'] is None
        else:
            assert selected['instance']['name'] == 'u' and selected['instance']['orientation'] == 'MY'
            assert selected['instance']['orientation_names']['def'] == 'FN'
        assert selected['delivery']['full_details'].endswith('detail=full')
    finally:
        store.close()
