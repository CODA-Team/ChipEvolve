"""Bounded metadata views; original metadata remains directly addressable."""
from copy import deepcopy

from .identity import snapshot_identity


def metadata_view(payload, query, path):
    """Project requested facts or expose a compact summary with a full continuation."""
    detail = query.get('detail', 'summary')
    if detail not in ('summary', 'full'):
        raise ValueError('metadata detail must be summary|full')
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
        result = _selected_metadata(payload, selection)
        result['snapshot'] = {**snapshot_identity(payload.get('snapshot', {})),
                              **result.get('snapshot', {})}
        result['evidence'] = payload.get('evidence', payload.get('snapshot', {}).get('source_artifacts', []))[:1]
        for key in ('availability', 'association_coverage'):
            if key in payload:
                result[key] = deepcopy(payload[key])
        result['delivery'] = {'fields': fields.split(','), 'full_details': path + '?detail=full'}
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
    result['delivery'] = {'detail': 'summary', 'omitted_fields': omitted,
                          'full_details': path + '?detail=full',
                          'selection': 'metadata only; engineering fact counts are unchanged'}
    if len(result.get('evidence', [])) > 1:
        result['delivery']['evidence_count'] = len(result['evidence'])
        result['delivery']['evidence_details'] = path + '?detail=full'
        result['evidence'] = result['evidence'][:1]
    return result


def _selected_metadata(value, selection, prefix=''):
    """Apply the same field selection through dictionaries and ordered list items."""
    if selection is None:
        return deepcopy(value)
    if isinstance(value, list):
        return [_selected_metadata(item, selection, prefix) for item in value]
    result = {}
    for key, children in selection.items():
        field = prefix + key
        if not isinstance(value, dict) or key not in value:
            raise ValueError('unknown metadata field: ' + field)
        result[key] = _selected_metadata(value[key], children, field + '.')
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
