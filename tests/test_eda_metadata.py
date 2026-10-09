"""Metadata selection must preserve engineering facts and recover omitted inputs."""
import json

import pytest

from openroad_app_data_foundation.metadata import metadata_view, placement_geometry


def test_si_timing_values_have_explicit_engineering_units_without_changing_originals():
    from openroad_app_data_foundation.metadata import timing_values
    fact = {'slack': -2.022e-10, 'data_arrival_time': 8.452e-10, 'required_time': 6.43e-10,
            'slew': 4.668e-11, 'load': 7.281e-15, 'unit': 's', 'evidence': [{'artifact_id': 'original'}]}
    result = timing_values(fact)
    assert result['slack_ns'] == pytest.approx(-0.2022)
    assert result['arrival_ns'] == pytest.approx(0.8452)
    assert result['required_ns'] == pytest.approx(0.643)
    assert result['slew_ns'] == pytest.approx(0.04668)
    assert result['load_ff'] == pytest.approx(7.281)
    assert all(result[key] == value for key, value in fact.items())
    assert timing_values({**fact, 'arrival': 1e-10})['arrival_ns'] == pytest.approx(0.8452)
    assert timing_values({'load': None})['load_ff'] is None  # missing remains null, never zero
    assert 'slew_ns' not in timing_values({'slew': False})


def test_time_units_are_normalized_without_assuming_missing_path_units():
    from openroad_app_data_foundation.metadata import timing_values
    for unit, slack, expected in [('s', -2e-10, -.2), ('ns', -.2, -.2),
                                  ('ps', -200, -.2)]:
        result = timing_values({'path_id': 'p', 'slack': slack, 'unit': unit})
        assert result['slack'] == slack
        assert result['slack_ns'] == pytest.approx(expected)
    assert 'slack_ns' not in timing_values({'path_id': 'p', 'slack': -.2})
    assert 'slack_ns' not in timing_values({'path_id': 'p', 'slack': -.2, 'unit': 'unknown'})


def test_clock_engineering_units_preserve_native_values_and_ignore_library_display_units():
    from copy import deepcopy
    from openroad_app_data_foundation.metadata import clock_context
    context = {'clocks': [
        {'name': 'core', 'unit': 's', 'period': 6.5e-10, 'period_ui': 650,
         'waveform': [0, 3.25e-10], 'generated': 0, 'virtual': 0},
        {'name': 'generated', 'unit': 's', 'period': 1.3e-9, 'period_ui': 1300,
         'waveform': [6.5e-10, 1.3e-9], 'generated': 1, 'virtual': 1},
        {'name': 'unidentified', 'period': 650}]}
    original = deepcopy(context)
    result = clock_context(context)
    assert result['clocks'][0]['period_ns'] == pytest.approx(0.65)
    assert result['clocks'][0]['waveform_ns'] == pytest.approx([0, 0.325])
    assert result['clocks'][1]['period_ns'] == pytest.approx(1.3)
    assert result['clocks'][1]['waveform_ns'] == pytest.approx([0.65, 1.3])
    assert result['clocks'][1]['generated'] == result['clocks'][1]['virtual'] == 1
    assert 'period_ns' not in result['clocks'][2]
    assert 'native library' in result['clocks'][0]['period_ui_basis']
    assert context == original
    assert clock_context(result) == result
    assert clock_context(None) is None


def test_clock_units_agree_in_discovery_summary_full_details_and_projection():
    native = {'clocks': [{'name': 'clock', 'period': 9e-10, 'period_ui': 900,
                          'unit': 's', 'waveform': [0, 4.5e-10]}]}
    payload = {'snapshot': {'snapshot_id': 's', 'run_summary': {'timing_context': native}},
               'run_summary': {'timing_context': native}, 'timing_context': native}
    full = metadata_view(payload, {'detail': 'full'}, '/snapshots/s')
    compact = metadata_view(payload, {}, '/snapshots/s/summary')
    selected = metadata_view(payload, {'fields': 'timing_context.clocks.name,timing_context.clocks.period_ns'},
                             '/snapshots/s/timing-context')
    for context in (full['snapshot']['run_summary']['timing_context'], full['timing_context'],
                    full['run_summary']['timing_context'], compact['run_summary']['timing_context']):
        assert context['clocks'][0]['period_ns'] == pytest.approx(0.9)
        assert context['clocks'][0]['period_ui'] == 900
    assert selected['timing_context']['clocks'][0]['period_ns'] == pytest.approx(0.9)
    assert 'period_ns' not in native['clocks'][0]


def test_compact_metadata_and_projection_restore_original_facts_without_duplicates():
    snapshot = {'snapshot_id': 's', 'design_id': 'chip', 'stage': 'finish',
                'source_artifacts': [{'artifact_id': 'odb', 'sha256': 'abc'}]}
    summary = {'dbu_per_micron': 2000, 'instance_count': 538184,
               'timing_context': {'corner': 'typical', 'producer': {
                   'artifacts': {f'file-{i}': {'sha256': 'a' * 64} for i in range(50)}}}}
    snapshot['run_summary'] = summary
    payload = {'snapshot': snapshot, 'run_summary': summary,
               'record_counts': {'entities': 538184}, 'coverage': {'mapping': 'partial'}}
    compact = metadata_view(payload, {}, '/snapshots/s/summary')
    full = metadata_view(payload, {'detail': 'full'}, '/snapshots/s/summary')
    projection = metadata_view(payload, {'fields': 'run_summary.dbu_per_micron,run_summary.timing_context.producer'},
                               '/snapshots/s/summary')
    assert compact['run_summary']['instance_count'] == 538184
    assert compact['record_counts'] == payload['record_counts']
    assert compact['coverage'] == payload['coverage']
    assert len(json.dumps(compact)) < len(json.dumps(full)) / 5
    assert 'run_summary.timing_context.producer' in compact['delivery']['omitted_fields']
    assert projection['run_summary']['timing_context']['producer'] == summary['timing_context']['producer']
    assert full == payload and full['snapshot']['run_summary']['timing_context']['producer']
    with pytest.raises(ValueError, match='unknown metadata field'):
        metadata_view(payload, {'fields': 'run_summary.no_such_fact'}, '/snapshots/s/summary')


def test_mirrored_placement_does_not_claim_transformed_origin_or_pin_coordinates():
    fact = {'x': 125780, 'y': 44800,
            'bbox': {'x_min': 125780, 'y_min': 44800, 'x_max': 133380, 'y_max': 47600}}
    result = placement_geometry(fact, 2000, 'MX')
    assert result['location_dbu'] == [125780, 44800]
    assert result['location_um'] == [62.89, 22.4]
    assert result['bbox_um']['y_max'] == 23.8
    assert result['bbox_um_array'] == [62.89, 22.4, 66.69, 23.8]
    assert result['bbox_array_order'] == ['x_min', 'y_min', 'x_max', 'y_max']
    assert result['orientation'] == 'MX'
    assert 'getLocation' in result['location_basis']
    assert 'getOrigin' in result['native_origin_note']
    assert result['orientation_names'] == {'odb': 'MX', 'def': 'FS'}


def test_native_orientation_aliases_preserve_all_eight_transformations():
    names = {'R0': 'N', 'R90': 'W', 'R180': 'S', 'R270': 'E',
             'MY': 'FN', 'MYR90': 'FE', 'MX': 'FS', 'MXR90': 'FW'}
    for odb, lefdef in names.items():
        assert placement_geometry({}, 2000, odb)['orientation_names'] == {'odb': odb, 'def': lefdef}


def test_dotted_selection_reads_ordered_array_fields_without_full_objects():
    payload = {'instances': [{'name': 'a', 'master': 'BUF', 'bbox': {'x_min': 1, 'x_max': 4}},
                             {'name': 'b', 'master': 'INV', 'bbox': {'x_min': 2, 'x_max': 5}}]}
    result = metadata_view(payload, {'fields': 'instances.name,instances.bbox.x_min'}, '/path')
    assert result['instances'] == [{'name': 'a', 'bbox': {'x_min': 1}},
                                   {'name': 'b', 'bbox': {'x_min': 2}}]
    with pytest.raises(ValueError, match='instances.no_such_fact'):
        metadata_view(payload, {'fields': 'instances.no_such_fact'}, '/path')
    assert metadata_view(payload, {'fields': 'instances,instances.name'}, '/path')['instances'] == payload['instances']


def test_projected_recovery_retains_stage_selector_and_pagination_semantics():
    from urllib.parse import urlsplit, parse_qs
    query = {'stage': 'route', 'metrics': 'setup__ws,hold__ws', 'offset': '3', 'limit': '3',
             'traverse': '1', 'fields': 'value'}
    projected = metadata_view({'value': 7}, query, '/snapshots/s/run-inventory')
    full = parse_qs(urlsplit(projected['delivery']['full_details']).query)
    assert full == {key: [value] for key, value in {**{k: v for k, v in query.items() if k != 'fields'}, 'detail': 'full'}.items()}
    assert 'fields' not in full


def test_large_constraint_port_lists_have_explicit_counts_and_complete_recovery():
    names = [f'port[{index}]' for index in range(1200)]
    payload = {'clocks': [{'name': 'clk'}], 'ports_without_delay': {
        'input_delay': names, 'output_delay': ['z']}, 'declaration_counts': {'clocks': 1}}
    compact = metadata_view(payload, {'kind': 'all'}, '/snapshots/s/constraints')
    full = metadata_view(payload, {'detail': 'full'}, '/snapshots/s/constraints')
    selected = metadata_view(payload, {'fields': 'ports_without_delay.input_delay'}, '/snapshots/s/constraints')
    assert compact['ports_without_delay_counts'] == {'input_delay': 1200, 'output_delay': 1}
    assert compact['ports_without_delay']['input_delay'] == names[:20]
    assert compact['ports_without_delay']['output_delay'] == ['z']
    assert compact['declaration_counts'] == payload['declaration_counts']
    assert 'ports_without_delay.input_delay[20:]' in compact['delivery']['omitted_fields']
    assert 'kind=all' in compact['delivery']['full_details']
    assert full == payload
    assert selected['ports_without_delay']['input_delay'] == names
    assert len(payload['ports_without_delay']['input_delay']) == 1200
