"""Proximity searches rank the full filtered geometry, rather than a returned sample."""
import pytest

from openroad_app_data_foundation.discovery import list_objects
from openroad_app_data_foundation.instance_pair import instance_pair
from openroad_app_data_foundation.repository import DataStore


@pytest.fixture
def spatial_store(tmp_path):
    boxes = {'ref': (0, 0, 1, 1), 'logic': (0, 0, 1, 1),
             'close': (0, 0, 1, 2), 'tie10': (1, 0, 2, 1),
             'tie2': (0, 1, 1, 2), 'far': (10, 10, 11, 11)}
    names = {'ref': 'logic/source', 'logic': 'logic/other', 'close': 'macro/close',
             'tie10': 'macro/m[10]', 'tie2': r'macro/m\[2\]', 'far': 'macro/far', 'missing': 'macro/missing'}
    pack = {'snapshot': {'snapshot_id': 's', 'design_id': 'd', 'stage': 'placeopt',
                        'revision_id': 'r', 'run_id': 'run', 'created_at': '2026-10-04'},
            'run_summary': {'dbu_per_micron': 2},
            'entities': [{'object_id': key, 'kind': 'instance', 'name': value,
                          'attributes': {'is_macro': int(key not in ('ref', 'logic'))}}
                         for key, value in names.items()],
            'physical_context': [{'object_id': key, 'bbox': dict(zip(
                ('x_min', 'y_min', 'x_max', 'y_max'), value))} for key, value in boxes.items()]}
    store = DataStore(tmp_path / 'spatial.sqlite')
    store.register(pack)
    try:
        yield store
    finally:
        store.close()


def query(**extra):
    return {'kind': 'instance', 'is_macro': '1', 'sort': 'distance',
            'reference_instance': 'logic/source', 'limit': '1',
            'fields': 'name,spatial.bbox_center_manhattan_um', **extra}


def test_nearest_and_farthest_rank_before_paging_with_exact_half_dbu(spatial_store):
    first = list_objects(spatial_store, 's', query())
    assert first['objects'] == [{'name': 'macro/close', 'spatial': {'bbox_center_manhattan_um': .25}}]
    assert first['ranking']['candidate_count'] == 5
    assert first['ranking']['leading_value_twice_dbu'] == 1
    assert first['ranking']['leading_value'] == .5 and first['ranking']['unit'] == 'dbu'
    assert first['ranking']['missing_value_count'] == 1 and first['ranking']['status'] == 'partial'
    second = list_objects(spatial_store, 's', query(offset='1'))
    third = list_objects(spatial_store, 's', query(offset='2'))
    assert second['objects'][0]['name'] == 'macro/m[10]'
    assert third['objects'][0]['name'] == r'macro/m\[2\]'
    assert second['ranking'] == third['ranking'] == first['ranking']
    beyond = list_objects(spatial_store, 's', query(offset='20'))
    assert beyond['objects'] == [] and beyond['ranking'] == first['ranking']
    far = list_objects(spatial_store, 's', query(order='desc'))
    assert far['objects'][0]['name'] == 'macro/far'
    assert far['ranking']['leading_value_twice_dbu'] == 40
    assert far['objects'][0]['spatial']['bbox_center_manhattan_um'] == 10
    original_pair = instance_pair(spatial_store, 's', 'ref', {'with_instance': 'close'})
    assert original_pair['geometry']['bbox_center_manhattan_um'] == first['ranking']['leading_value_um']


def test_filters_ties_and_column_projection_cover_the_complete_region(spatial_store):
    result = list_objects(spatial_store, 's', query(region='0,0,3,3', intersection='positive_area',
        name_contains='macro/m', format='columns', fields='name,spatial.distance_twice_dbu'))
    assert result['object_columns'] == ['name', 'spatial.distance_twice_dbu']
    assert result['object_rows'] == [['macro/m[10]', 2]]
    assert result['count'] == 2 and result['next_offset'] == 1
    assert result['ranking']['leading_tie_count'] == 2 and result['ranking']['status'] == 'complete'
    assert result['ranking']['reference_instance']['bbox_dbu'] == {'x_min': 0, 'y_min': 0, 'x_max': 1, 'y_max': 1}


def test_reference_inclusion_is_explicit_and_missing_values_remain_null(spatial_store):
    excluded = list_objects(spatial_store, 's', query(is_macro='0'))
    included = list_objects(spatial_store, 's', query(is_macro='0', exclude_reference='0', limit='10'))
    assert excluded['count'] == 1 and included['count'] == 2
    assert excluded['ranking']['excludes_reference'] and not included['ranking']['excludes_reference']
    assert included['ranking']['leading_tie_count'] == 2 and included['ranking']['leading_value'] == 0
    missing = list_objects(spatial_store, 's', query(name='macro/missing'))
    assert missing['objects'][0]['spatial']['bbox_center_manhattan_um'] is None
    assert missing['ranking']['leading_value'] is None and missing['ranking']['leading_tie_count'] == 0
    assert missing['ranking']['missing_value_count'] == 1
    empty = list_objects(spatial_store, 's', query(name='no-such-candidate'))
    assert empty['count'] == 0 and empty['objects'] == [] and empty['ranking']['leading_value_um'] is None


def test_reference_requires_actual_native_geometry(spatial_store):
    with pytest.raises(ValueError, match='integer native placed bbox'):
        list_objects(spatial_store, 's', query(reference_instance='missing'))


@pytest.mark.parametrize('extra', [{'sort': 'name'}, {'kind': 'pin'}, {'reference_instance': ''}, {'exclude_reference': 'maybe'}])
def test_invalid_proximity_query_is_explicit(spatial_store, extra):
    with pytest.raises(ValueError):
        list_objects(spatial_store, 's', query(**extra))
