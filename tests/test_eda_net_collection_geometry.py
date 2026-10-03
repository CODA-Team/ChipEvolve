"""Net-centred physical joins count distinct owners, not pins or name-page rows."""
import pytest

from openroad_app_data_foundation.engineering import net_engineering
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler


@pytest.fixture
def store(tmp_path):
    db = DataStore(tmp_path / 'net-geometry.sqlite')
    entities = [{'object_id': 'n', 'kind': 'net', 'name': 'signal',
                 'attributes': {'signal_type': 'SIGNAL', 'fanout': 4, 'driver_count': 0}}]
    entities.extend({'object_id': key, 'kind': 'instance', 'name': name,
                     'attributes': {'is_macro': macro}} for key, name, macro in
                    [('macro', 'a_ram', 1), ('logic', 'z_logic', 0)])
    pins = [('p1', 'z_logic/A', 'logic'), ('p2', 'z_logic/B', 'logic'),
            ('p3', 'a_ram/A', 'macro'), ('out', 'out', None)]
    entities.extend({'object_id': key, 'kind': 'pin', 'name': name, 'parent_id': parent}
                    for key, name, parent in pins)
    db.register({'snapshot': {'snapshot_id': 's', 'design_id': 'chip', 'revision_id': 'r',
                 'run_id': 'run', 'stage': 'finish', 'created_at': '2026-10-03'},
                 'run_summary': {'dbu_per_micron': 2000},
                 'entities': entities, 'relations': [{'relation_id': key, 'subject_id': 'n',
                 'predicate': 'loads', 'object_id': key} for key, _, _ in pins],
                 'physical_context': [
                     {'object_id': 'logic', 'bbox': {'x_min': 0, 'y_min': 0, 'x_max': 2000, 'y_max': 4000}},
                     {'object_id': 'macro', 'bbox': {'x_min': -2000, 'y_min': 1000, 'x_max': 1000, 'y_max': 6000}},
                     {'object_id': 'out', 'bbox': {'x_min': 0, 'y_min': 0, 'x_max': 2000000, 'y_max': 2000000}}]})
    yield db
    db.close()


def test_complete_role_geometry_and_class_counts_ignore_duplicate_pins_ports_and_name_pages(store):
    query = {'include_instances': '1', 'include_physical': '1', 'limit': '1', 'instance_limit': '1'}
    result = net_engineering(store, 's', 'signal', query)
    loads = result['load_instances']
    assert result['load_count'] == 4 and loads['count'] == 2
    assert loads['names'] == ['a_ram'] and loads['truncated']
    assert loads['geometry']['status'] == 'complete' and loads['geometry']['matched_count'] == 2
    assert loads['geometry']['total_bbox_area_um2'] == 5.75
    assert loads['geometry']['bbox_union_um'] == {'x_min': -1, 'y_min': 0, 'x_max': 1, 'y_max': 3}
    assert {r['value']: r['count'] for r in loads['groups']} == {0: 1, 1: 1}
    second = net_engineering(store, 's', 'n', {**query, 'instance_offset': '1', 'offset': '3'})
    assert second['load_instances']['names'] == ['z_logic']
    for field in ('geometry', 'groups', 'count'):
        assert second['load_instances'][field] == loads[field]
    driver = result['driver_instances']
    assert driver['count'] == 0 and driver['geometry']['status'] == 'complete'
    assert driver['geometry']['bbox_union_um'] is None and driver['groups'] == []


def test_macro_filter_and_nested_projection_use_the_same_complete_collection(store):
    handler = Handler.__new__(Handler)
    handler.store, handler.auto_import = store, False
    result = handler._get('/snapshots/s/nets/signal/engineering', {
        'include_instances': '1', 'include_physical': 'true', 'instance_is_macro': '1',
        'fields': 'load_instances.count,load_instances.geometry,load_instances.groups.value,load_instances.groups.count'})
    loads = result['load_instances']
    assert loads['count'] == loads['geometry']['matched_count'] == 1
    assert loads['groups'] == [{'value': 1, 'count': 1}]
    assert loads['geometry']['bbox_union_um'] == {'x_min': -1, 'y_min': .5, 'x_max': .5, 'y_max': 3}
    assert 'names' not in loads and result['delivery']['full_details'].endswith('detail=full')
    with pytest.raises(ValueError, match='requires include_instances'):
        net_engineering(store, 's', 'n', {'include_physical': '1'})


def test_missing_geometry_keeps_exact_counts_and_explicit_partial_coverage(store):
    store.connection.execute("DELETE FROM records WHERE record_type='physical_context' AND record_id='macro'")
    store.connection.commit()
    result = net_engineering(store, 's', 'n', {'include_instances': '1', 'include_physical': '1'})
    geometry = result['load_instances']['geometry']
    assert result['load_instances']['count'] == 2
    assert geometry['status'] == 'partial' and geometry['missing_geometry_count'] == 1
    assert geometry['total_bbox_area_um2'] is None and geometry['available_bbox_area_um2'] == 2
