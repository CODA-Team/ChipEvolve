"""Metadata selection must preserve engineering facts and recover omitted inputs."""
import json

import pytest

from openroad_app_data_foundation.metadata import metadata_view, placement_geometry


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
