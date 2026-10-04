"""Original global-route rows must stay distinct from empty detailed dbWire records."""
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from openroad_app_data_foundation.global_routing import segment_totals
from openroad_app_data_foundation.global_routing import path_global_routes
from openroad_app_data_foundation.repository import DataStore
from tests.test_eda_engineering import sample
from tests.test_eda_timing_reports import report


def routes(handler):
    path = Path(handler.native_root) / 'results/pdk/chip/r/global_route.segments'
    path.parent.mkdir(parents=True)
    path.write_text('a\n(\n0 0 M2 2000 0 M2\n2000 0 M2 2000 0 M2\n'
                    '2000 0 M2 2000 0 M3\n)\nb\n(\n0 0 M10 0 3000 M10\n)\n'
                    'a\n(\n2000 0 M3 2000 4000 M3\n)\n')
    return path


def test_original_routes_count_every_row_and_repeated_section_separately(report):
    handler, _, _, _ = report
    path = routes(handler)
    result = segment_totals(path, {'a'}, 1000)
    value = result['a']
    assert value['wirelength_um'] == 6 and value['same_layer_segment_count'] == 3
    assert value['record_count'] == 4 and value['interlayer_transition_count'] == 1
    assert value['layers'] == [{'layer': 'M2', 'wirelength_um': 2, 'segment_count': 2},
                               {'layer': 'M3', 'wirelength_um': 4, 'segment_count': 1}]
    assert len(value['source_sections']) == 2
    assert segment_totals(path, {'not_in_file'}, 1000) == {}
    with pytest.raises(ValueError, match='positive original'):
        segment_totals(path, {'a'}, 0)


def test_native_detailed_wire_and_original_global_route_are_separate_sources(report):
    handler, _, _, _ = report
    routes(handler)
    path = '/snapshots/s/nets/a/routing-summary'
    detailed = handler._get(path, {})
    original = handler._get(path, {'source': 'global_route', 'fields': 'net_name,route'})
    assert detailed['segment_count'] == 0 and detailed['wirelength_um'] == 0
    assert original['net_name'] == 'a' and original['route']['wirelength_um'] == 6
    assert original['route']['interlayer_transition_count'] == 1
    assert original['evidence'][0]['source_type'] == 'original_global_route_segments'


def test_original_path_routes_rank_full_domain_before_paging(report):
    handler, _, _, _ = report
    routes(handler)
    query = {'startpoint': 'u/A', 'endpoint': 'v/Z', 'include_path_details': '1',
             'include_global_routing': '1', 'route_net_limit': '1', 'signal_type': 'SIGNAL'}
    first = handler._get('/snapshots/s/timing-reports', query)['path_details'][0]['global_routing']
    second = handler._get('/snapshots/s/timing-reports', {**query, 'route_offset': '1'})['path_details'][0]['global_routing']
    assert first['count'] == second['count'] == 2
    assert first['nets'][0]['name'] == 'a' and first['nets'][0]['route']['wirelength_um'] == 6
    assert second['nets'][0]['name'] == 'b' and second['nets'][0]['route']['wirelength_um'] == 3
    assert first['next_offset'] == 1 and second['next_offset'] is None
    with pytest.raises(ValueError, match='require include_path_details'):
        handler._get('/snapshots/s/timing-reports', {'include_global_routing': '1'})


def test_missing_native_load_count_is_not_a_verified_zero_or_complete_ranking(tmp_path):
    pack = sample()
    del pack['entities'][2]['attributes']['fanout']
    path = tmp_path / 'results/pdk/chip/r/finish.segments'
    path.parent.mkdir(parents=True)
    path.write_text('signal\n(\n0 0 M2 2000 0 M2\n)\n')
    store = DataStore(tmp_path / 'missing.sqlite')
    try:
        store.register(pack)
        result = path_global_routes(store, 's', ['signal'], {}, tmp_path)
        assert result['ranking_status'] == 'partial' and result['missing_fanout_count'] == 1
        assert result['nets'][0]['fanout'] is None and result['nets'][0]['route']['wirelength_um'] == 1
        assert result['availability']['complete_fanout_ranking']['status'] == 'unavailable'
    finally:
        store.close()


def test_joined_route_summary_preserves_counts_and_recovers_original_pages(report):
    handler, _, _, _ = report
    routes(handler)
    path = '/snapshots/s/timing-reports'
    query = {'startpoint': 'u/A', 'endpoint': 'v/Z', 'include_path_details': '1',
             'include_global_routing': '1', 'include_route_connections': '1', 'route_net_limit': '1'}
    summary = handler._get(path, query)['path_details'][0]['global_routing']['nets'][0]['connectivity']
    full = handler._get(path, {**query, 'detail': 'full'})['path_details'][0]['global_routing']['nets'][0]['connectivity']
    assert 'load_pins' not in summary and 'names' not in summary['load_instances']
    assert 'load_pins' in full and 'names' in full['load_instances']
    assert summary['load_count'] == full['load_count']
    assert summary['driver_pins'] == full['driver_pins']
    assert summary['load_instances']['count'] == full['load_instances']['count']
    assert summary['load_instances']['groups'] == full['load_instances']['groups']
    continuation = urlsplit(summary['delivery']['full_details'])
    restored = handler._get(continuation.path,
        {key: values[0] for key, values in parse_qs(continuation.query).items()})
    assert restored['load_pins'] == full['load_pins']
    assert restored['load_instances']['names'] == full['load_instances']['names']
    selected = handler._get(path, {**query,
        'fields': 'path_details.global_routing.nets.connectivity.load_pins'})
    assert selected['path_details'][0]['global_routing']['nets'][0]['connectivity']['load_pins'] == full['load_pins']
