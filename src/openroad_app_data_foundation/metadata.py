"""Bounded metadata views; original metadata remains directly addressable."""
from copy import deepcopy
from urllib.parse import urlencode

from .identity import snapshot_identity


def recovery_path(path, query):
    return path + '?' + urlencode({**{key: value for key, value in query.items()
                                     if key not in ('fields', 'detail')}, 'detail': 'full'})


def metadata_view(payload, query, path, *, sparse_fields=False):
    """Project requested facts or expose a compact summary with a full continuation."""
    payload = deepcopy(payload)
    for container in (payload, payload.get('snapshot', {})):
        if 'timing_context' in container:
            container['timing_context'] = clock_context(container['timing_context'])
        summary = container.get('run_summary', {})
        if 'timing_context' in summary:
            summary['timing_context'] = clock_context(summary['timing_context'])
    detail = query.get('detail', 'summary')
    if detail not in ('summary', 'full'):
        raise ValueError('metadata detail must be summary|full')
    full_details = recovery_path(path, query)
    fields = query.get('fields')
    if fields:
        selection = {}
        for field in sorted(fields.split(','), key=lambda field: field.count('.')):
            parts = field.split('.')
            if any(not part for part in parts):
                raise ValueError('unknown metadata field: ' + field)
            target = selection
            for part in parts[:-1]:
                child = target.setdefault(part, {})
                if child is None:
                    break  # An explicitly selected parent already includes its children.
                target = child
            else:
                target[parts[-1]] = None
        absent = set() if sparse_fields else None
        result = _selected_metadata(payload, selection, absent=absent)
        result['snapshot'] = {**snapshot_identity(payload.get('snapshot', {})),
                              **result.get('snapshot', {})}
        attached = payload.get('evidence', payload.get('snapshot', {}).get('source_artifacts', []))
        result['evidence'] = attached[:1] if isinstance(attached, list) else attached
        for key in ('availability', 'association_coverage', 'object_facts_source', 'query_execution'):
            if key in payload:
                result[key] = deepcopy(payload[key])
        result['delivery'] = {'fields': fields.split(','), 'full_details': full_details}
        if sparse_fields:
            result['delivery']['requested_fields_absent_in_some_returned_rows'] = sorted(absent)
            result['delivery']['absent_field_basis'] = 'Original fields absent from a row stay absent; explicit nulls stay null; no default value is invented'
        return result
    if detail == 'full':
        return payload
    result = deepcopy(payload)
    omitted = []
    snapshot = result.get('snapshot')
    if isinstance(snapshot, dict):
        omitted.extend('snapshot.' + key for key in snapshot
                       if key not in snapshot_identity(snapshot))
        result['snapshot'] = snapshot_identity(snapshot)
        if 'evidence' not in result:
            result['evidence'] = snapshot.get('source_artifacts', [])[:1]
    for section in ('run_summary', 'timing_context'):
        item = result.get(section)
        if not isinstance(item, dict):
            continue
        if section == 'run_summary' and isinstance(item.get('timing_context'), dict):
            item['timing_context'] = {key: value for key, value in item['timing_context'].items()
                                      if key != 'producer'}
            omitted.append('run_summary.timing_context.producer')
        if section == 'timing_context' and 'producer' in item:
            del item['producer']
            omitted.append('timing_context.producer')
        if section == 'run_summary' and 'raw_metrics' in item:
            del item['raw_metrics']
            omitted.append('run_summary.raw_metrics')
    if 'ports_without_delay' in result:
        result['ports_without_delay_counts'] = {key: len(names)
                                               for key, names in result['ports_without_delay'].items()}
        for key, names in result['ports_without_delay'].items():
            if len(names) > 20:
                result['ports_without_delay'][key] = names[:20]
                omitted.append('ports_without_delay.' + key + '[20:]')
    result['delivery'] = {'detail': 'summary', 'omitted_fields': omitted,
                          'full_details': full_details,
                          'selection': 'summary with explicit omissions; complete facts remain available through full_details'}
    if isinstance(result.get('evidence'), list) and len(result['evidence']) > 1:
        result['delivery']['evidence_count'] = len(result['evidence'])
        result['delivery']['evidence_details'] = full_details
        result['evidence'] = result['evidence'][:1]
    return result


def _selected_metadata(value, selection, prefix='', absent=None):
    """Apply the same field selection through dictionaries and ordered list items."""
    if selection is None:
        return deepcopy(value)
    if isinstance(value, list):
        return [_selected_metadata(item, selection, prefix, absent) for item in value]
    if absent is not None and not isinstance(value, dict):
        absent.update(prefix + key for key in selection)
        return deepcopy(value)
    result = {}
    for key, children in selection.items():
        field = prefix + key
        if not isinstance(value, dict) or key not in value:
            if absent is not None:
                absent.add(field)
                continue
            available = ','.join(sorted(value)) if isinstance(value, dict) else 'none (parent is not an object)'
            raise ValueError('unknown metadata field: ' + field + '; available fields in this parent: ' + available)
        result[key] = _selected_metadata(value[key], children, field + '.', absent)
    # Classified counts need their scope even when the caller selects one map.
    # Sparse original JSON selections must remain literal source projections.
    if absent is None and 'native_pin_classification_coverage' in value and any(
            key in selection for key in ('pin_counts_by_native_type',
                'connected_pin_counts_by_native_type', 'distinct_net_counts_by_native_pin_type')):
        for key in ('native_pin_classification_coverage', 'classification_basis'):
            result[key] = deepcopy(value[key])
    return result


def placement_geometry(fact, scale, orientation=None):
    """Name the extracted getLocation position explicitly, never confuse it with pin XY."""
    box = fact.get('bbox')
    location = [fact.get('x'), fact.get('y')]
    def_names = {'R0': 'N', 'R90': 'W', 'R180': 'S', 'R270': 'E',
                 'MY': 'FN', 'MYR90': 'FE', 'MX': 'FS', 'MXR90': 'FW'}
    return {'dbu_per_micron': scale, 'bbox_dbu': box,
            'bbox_um': {key: value / scale for key, value in box.items()} if box else None,
            'bbox_um_array': [box[key] / scale for key in ('x_min', 'y_min', 'x_max', 'y_max')] if box else None,
            'bbox_array_order': ['x_min', 'y_min', 'x_max', 'y_max'],
            'location_dbu': location,
            'location_um': [value / scale if value is not None else None for value in location],
            'location_basis': 'OpenDB dbInst.getLocation; lower-left placement location in block coordinates',
            'orientation': orientation,
            'orientation_names': {'odb': orientation, 'def': def_names.get(orientation)},
            'native_origin_note': 'dbInst.getOrigin is the transformed master origin; query it natively if needed; this is not pin XY'}


def timing_values(fact, *, default_time_unit=None):
    """Normalize declared time units; native point callers may declare SI defaults."""
    result = dict(fact)
    time_scale = {'s': 1e9, 'ms': 1e6, 'us': 1e3, 'ns': 1, 'ps': 1e-3,
                  'fs': 1e-6}.get(fact.get('unit') or default_time_unit)
    fields = [('slack', 'slack_ns', 1e9), ('arrival', 'arrival_ns', 1e9),
              ('data_arrival_time', 'arrival_ns', 1e9), ('required_time', 'required_ns', 1e9),
              ('slew', 'slew_ns', 1e9), ('load', 'load_ff', 1e15),
              ('margin', 'margin_ns', 1e9), ('crpr', 'crpr_ns', 1e9),
              ('source_clock_edge', 'source_clock_edge_ns', 1e9),
              ('target_clock_edge', 'target_clock_edge_ns', 1e9), ('period', 'period_ns', 1e9)]
    for source, target, factor in fields:
        value = fact.get(source)
        if source != 'load':
            if time_scale is None:
                continue
            factor = time_scale
        if source in fact and value is None:
            # A declared-but-missing observation has the same optional engineering
            # field as a measured row. Preserve null, never manufacture zero.
            result[target] = None
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            result[target] = value * factor
    return result


def clock_context(context):
    """Give every native SI clock an explicit engineering view without using period_ui."""
    if context is None or 'clocks' not in context:
        return context
    clocks = []
    for clock in context['clocks']:
        result = timing_values(clock) if clock.get('unit') == 's' else dict(clock)
        if clock.get('unit') == 's' and 'waveform' in clock:
            result['waveform_ns'] = [edge * 1e9 for edge in clock['waveform']]
        if 'period_ui' in clock:
            result['period_ui_basis'] = 'native library display time unit; use period_ns for nanoseconds'
        clocks.append(result)
    return {**context, 'clocks': clocks}
