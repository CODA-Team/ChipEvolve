"""Complete path type counts exclude clocks, duplicates and output pages."""
from copy import deepcopy

import pytest

from openroad_app_data_foundation.engineering import path_engineering, timing_overview
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler
from test_eda_engineering import sample


@pytest.fixture
def store(tmp_path):
    pack = sample()
    pack['entities'].append({'object_id': 'ram', 'kind': 'instance', 'name': 'memory',
                             'attributes': {'master': 'SRAM', 'is_macro': 1}})
    pack['physical_context'].append({'object_id': 'ram', 'bbox': {
        'x_min': 100, 'y_min': 100, 'x_max': 500, 'y_max': 500}})
    pack['timing_points'].extend([
        {'point_id': 'ram-in', 'path_id': 'p', 'ordinal': 3, 'pin_name': 'memory/A',
         'instance_id': 'ram', 'path_section': 'source_path'},
        {'point_id': 'ram-out', 'path_id': 'p', 'ordinal': 4, 'pin_name': 'memory/Q',
         'instance_id': 'ram', 'path_section': 'source_path'}])
    second = deepcopy(pack['timing_paths'][0])
    second.update(path_id='p2', slack=0.3)
    pack['timing_paths'].append(second)
    pack['timing_points'].extend({**p, 'point_id': 'p2-' + p['point_id'], 'path_id': 'p2'}
                                 for p in list(pack['timing_points']))
    db = DataStore(tmp_path / 'path.sqlite')
    db.register(pack)
    yield db
    db.close()


def test_complete_path_and_union_counts_ignore_pin_duplication_clocks_and_paging(store, monkeypatch):
    from openroad_app_data_foundation import engineering
    monkeypatch.setattr(engineering, 'BATCH_ID_LIMIT', 1)
    path = path_engineering(store, 's', 'p', {'limit': '1'})
    overview = timing_overview(store, 's', {'check': 'setup', 'limit': '2', 'net_limit': '1'})
    assert path['instances_page']['truncated'] and len(path['instances']) == 1
    for result in (path, overview):
        assert result['macro_count'] == result['standard_cell_count'] == 1
        assert result['instance_classification_coverage'] == {
            'status': 'complete', 'classified_instance_count': 2,
            'unclassified_instance_count': 0, 'missing_instance_count': 0}
    assert overview['selected_path_count'] == 2


def test_path_type_count_is_directly_projectable_without_shipping_instances(store):
    handler = Handler.__new__(Handler)
    handler.store, handler.auto_import = store, False
    result = handler._get('/snapshots/s/timing-paths/p/engineering', {
        'fields': 'macro_count,standard_cell_count,instance_classification_coverage'})
    assert result['macro_count'] == result['standard_cell_count'] == 1
    assert 'instances' not in result
    assert result['instance_classification_coverage']['status'] == 'complete'


@pytest.mark.parametrize('missing_entity', [False, True])
def test_incomplete_native_classification_cannot_be_reported_as_zero(store, missing_entity):
    if missing_entity:
        store.connection.execute("DELETE FROM records WHERE record_type='entities' AND record_id='ram'")
    else:
        store.connection.execute("UPDATE records SET payload=json_remove(payload,'$.attributes.is_macro') WHERE record_type='entities' AND record_id='ram'")
    store.connection.commit()
    for result in (path_engineering(store, 's', 'p', {}),
                   timing_overview(store, 's', {'check': 'setup', 'limit': '2'})):
        assert result['macro_count'] is None and result['standard_cell_count'] is None
        assert result['instance_classification_coverage']['status'] == 'partial'
    coverage = path_engineering(store, 's', 'p', {})['instance_classification_coverage']
    assert coverage['missing_instance_count'] == int(missing_entity)
    assert coverage['unclassified_instance_count'] == int(not missing_entity)
