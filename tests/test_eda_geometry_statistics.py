"""Complete geometry sums remain exact beyond 32 bits, filters and page boundaries."""
import pytest

from openroad_app_data_foundation.engineering import object_statistics
from openroad_app_data_foundation.discovery import list_objects
from openroad_app_data_foundation.repository import DataStore


def pack():
    return {'snapshot': {'snapshot_id': 's', 'design_id': 'chip', 'revision_id': 'r',
                         'run_id': 'run', 'stage': 'global_route', 'created_at': '2026-10-03'},
        'run_summary': {'dbu_per_micron': 1000,
                        'core_bbox': {'x_min': 0, 'y_min': 0, 'x_max': 400000, 'y_max': 400000}},
        'entities': [{'object_id': name, 'kind': 'instance', 'name': name,
                      'attributes': {'is_macro': 1, 'master': name}} for name in ['a', 'b']],
        'physical_context': [
            {'object_id': 'a', 'bbox': {'x_min': 0, 'y_min': 0, 'x_max': 100000, 'y_max': 100000}},
            {'object_id': 'b', 'bbox': {'x_min': 100000, 'y_min': 0, 'x_max': 200000, 'y_max': 100000}}]}


def test_full_integer_area_is_not_32_bit_wrapped_or_limited_to_group_page(tmp_path):
    store = DataStore(tmp_path / 'geometry.sqlite')
    try:
        store.register(pack())
        query = {'kind': 'instance', 'is_macro': '1', 'group_by': 'master', 'include_physical': '1', 'limit': '1'}
        result = object_statistics(store, 's', query)
        assert result['next_offset'] == 1 and len(result['groups']) == 1
        geometry = result['geometry']
        assert geometry['status'] == 'complete' and geometry['geometry_count'] == 2
        assert geometry['available_bbox_area_dbu2'] == 20000000000
        assert geometry['total_bbox_area_um2'] == 20000
        assert geometry['percent_of_core_area'] == pytest.approx(12.5)
        assert geometry['bbox_union_um'] == {'x_min': 0, 'y_min': 0, 'x_max': 200, 'y_max': 100}
        one = object_statistics(store, 's', {**query, 'name': 'a'})
        assert one['geometry']['total_bbox_area_um2'] == 10000
        region = object_statistics(store, 's', {**query, 'region': '0,0,100,100',
                                               'region_units': 'um', 'intersection': 'positive_area'})
        assert region['geometry']['geometry_count'] == 1 and region['geometry']['total_bbox_area_um2'] == 10000
    finally:
        store.close()


def test_missing_geometry_cannot_be_reported_as_a_complete_small_area(tmp_path):
    store = DataStore(tmp_path / 'missing.sqlite')
    try:
        data = pack()
        data['physical_context'].pop()
        store.register(data)
        query = {'kind': 'instance', 'include_physical': 'true'}
        result = object_statistics(store, 's', query)['geometry']
        assert result['status'] == 'partial' and result['missing_geometry_count'] == 1
        assert result['available_bbox_area_um2'] == 10000 and result['total_bbox_area_um2'] is None
        assert result['percent_of_core_area'] is None
        empty = object_statistics(store, 's', {**query, 'name': 'absent'})['geometry']
        assert empty['status'] == 'complete' and empty['matched_count'] == 0
        assert empty['total_bbox_area_um2'] == 0 and empty['bbox_union_um'] is None
        with pytest.raises(ValueError, match='kind=instance'):
            object_statistics(store, 's', {'kind': 'net', 'include_physical': '1'})
    finally:
        store.close()


@pytest.mark.parametrize('macro,positive,touching', [('0', ['a'], ['a', 'b']),
                                                   ('false', ['a'], ['a', 'b']),
                                                   ('1', ['c'], ['c']),
                                                   ('true', ['c'], ['c'])])
def test_regional_classification_preserves_complete_counts_names_and_boundary_modes(tmp_path, macro, positive, touching):
    store = DataStore(tmp_path / 'region.sqlite')
    try:
        data = pack()
        data['entities'] = [{'object_id': name, 'kind': 'instance', 'name': name,
                             'attributes': attributes} for name, attributes in
                            [('a', {'is_macro': 0}), ('b', {'is_macro': 0}),
                             ('c', {'is_macro': 1}), ('unclassified', {})]]
        data['physical_context'].extend([
            {'object_id': 'c', 'bbox': {'x_min': 0, 'y_min': 0, 'x_max': 1000, 'y_max': 1000}},
            {'object_id': 'unclassified', 'bbox': {'x_min': 0, 'y_min': 0, 'x_max': 1000, 'y_max': 1000}}])
        store.register(data)
        query = {'kind': 'instance', 'is_macro': macro, 'region': '0,0,100,100',
                 'region_units': 'um', 'sort': 'name', 'fields': 'name', 'limit': '1'}
        for mode, names in [('positive_area', positive), ('touching', touching)]:
            filtered = {**query, 'intersection': mode}
            page = list_objects(store, 's', filtered)
            actual = [item['name'] for item in page['objects']]
            assert page['count'] == len(names)
            while page['next_offset'] is not None:
                page = list_objects(store, 's', {**filtered, 'offset': str(page['next_offset'])})
                actual.extend(item['name'] for item in page['objects'])
            assert actual == names
            statistics = object_statistics(store, 's', {k: v for k, v in filtered.items() if k != 'fields'})
            assert statistics['object_count'] == len(names)
        with pytest.raises(ValueError, match='use fields=name.*count/returned/next_offset'):
            list_objects(store, 's', {**query, 'fields': 'count,objects.name'})
    finally:
        store.close()


def test_grouped_names_keep_null_classification_complete_counts_and_readable_pages(tmp_path):
    from urllib.parse import parse_qs, urlsplit
    from openroad_app_data_foundation.server import Handler
    store = DataStore(tmp_path / 'group_names.sqlite')
    try:
        data = pack()
        data['entities'].extend([
            {'object_id': 'c', 'kind': 'instance', 'name': 'c', 'attributes': {'is_macro': 0}},
            {'object_id': 'd', 'kind': 'instance', 'name': 'd', 'attributes': {}}])
        store.register(data)
        handler = Handler.__new__(Handler)
        handler.store = store
        path = '/snapshots/s/objects/statistics'
        query = {'kind': 'instance', 'group_by': 'is_macro', 'include_names': '1', 'names_limit': '1',
                 'limit': '1', 'fields': 'object_count,groups.value,groups.names'}
        first = handler._get(path, query)
        assert first['object_count'] == 4
        assert first['groups'][0]['value'] == 1
        page = first['groups'][0]['names']
        assert page['count'] == 2 and page['items'] == ['a'] and page['truncated']
        continuation = urlsplit(page['continuation'])
        second = handler._get(continuation.path, {k: v[0] for k, v in parse_qs(continuation.query).items()})
        assert second['groups'][0]['names']['items'] == ['b']
        assert second['groups'][0]['names']['count'] == 2
        assert second['groups'][0]['names']['next_offset'] is None
        all_groups = object_statistics(store, 's', {**query, 'limit': '3'})
        groups = {g['value']: g['names'] for g in all_groups['groups']}
        assert groups[0]['items'] == ['c'] and groups[None]['items'] == ['d']
        assert sum(g['count'] for g in groups.values()) == 4
        with pytest.raises(ValueError, match='names paging requires'):
            object_statistics(store, 's', {'kind': 'instance', 'names_limit': '1'})
        with pytest.raises(ValueError, match='unknown object query fields'):
            list_objects(store, 's', {'kind': 'instance', 'include_names': '1'})
    finally:
        store.close()
