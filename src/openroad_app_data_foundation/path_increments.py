"""Adjacent arrival differences over the complete original data-path sequence."""
from math import fsum, isfinite


def data_path_increments(points):
    """Separate same-instance and between-instance increments without clock points."""
    missing = [index for index, point in enumerate(points)
               if type(point.get('arrival')) not in (int, float) or not isfinite(point['arrival'])]
    result = {'status': 'partial' if missing else ('complete' if points else 'not_extracted'),
        'point_count': len(points), 'adjacent_pair_count': max(0, len(points) - 1),
        'missing_arrival_point_indices': missing, 'unit': 's',
        'scope': 'complete source_path report sequence; excludes clock sections and time before the first data point',
        'classification_basis': 'cell when adjacent original report instance names are equal and nonempty; wire otherwise',
        'first_arrival': points[0].get('arrival') if points else None,
        'last_arrival': points[-1].get('arrival') if points else None,
        'cell_increment': None, 'wire_increment': None, 'total_increment': None,
        'cell_increment_ns': None, 'wire_increment_ns': None, 'total_increment_ns': None,
        'largest_increment': None}
    if missing or not points:
        return result
    cell, wire, largest, tied = [], [], None, 0
    for index, (left, right) in enumerate(zip(points, points[1:])):
        increment = right['arrival'] - left['arrival']
        kind = 'cell' if left.get('instance_name') and left['instance_name'] == right.get('instance_name') else 'wire'
        (cell if kind == 'cell' else wire).append(increment)
        if largest is None or increment > largest['increment']:
            largest = {'increment': increment, 'increment_ns': increment * 1e9,
                'kind': kind, 'from_pin': left.get('pin_name'), 'to_pin': right.get('pin_name'),
                'from_point_id': left.get('point_id'), 'to_point_id': right.get('point_id'),
                'from_data_index': index, 'to_data_index': index + 1,
                'selection_rule': 'first adjacent pair in original report order among exact numeric ties'}
            tied = 1
        elif increment == largest['increment']:
            tied += 1
    for label, values in [('cell', cell), ('wire', wire), ('total', cell + wire)]:
        result[label + '_increment'] = fsum(values)
        result[label + '_increment_ns'] = result[label + '_increment'] * 1e9
    result['cell_pair_count'], result['wire_pair_count'] = len(cell), len(wire)
    if largest is not None:
        largest['tie_count'] = tied
    result['largest_increment'] = largest
    return result
