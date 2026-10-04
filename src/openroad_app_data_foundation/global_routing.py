"""Complete estimates from original global-route segment records, separate from dbWire."""
from pathlib import Path

from .artifacts import _run_dirs, native_excerpt
from .engineering import _entity, net_engineering
from .identity import snapshot_identity
from .queries import _limit, _offset, _page


def segment_totals(path, names, scale):
    """Read each selected net's complete sections; repeated/zero-length rows count."""
    if not isinstance(scale, (int, float)) or scale <= 0:
        raise ValueError('global-route lengths require a positive original dbu_per_micron')
    selected, active, totals = None, False, {}
    with Path(path).open(encoding='utf-8') as stream:
        for line_number, text in enumerate(stream, 1):
            line = text.strip()
            if not line:
                continue
            if line == '(':
                if selected is None or active:
                    raise ValueError('invalid route section opening at line ' + str(line_number))
                active = True
                if selected in names:
                    value = totals.setdefault(selected, {'record_count': 0, 'same_layer_segment_count': 0,
                        'interlayer_transition_count': 0, 'layers': {}, 'source_sections': []})
                    value['source_sections'].append({'start_line': line_number - 1, 'end_line': None})
            elif line == ')':
                if not active:
                    raise ValueError('invalid route section closing at line ' + str(line_number))
                if selected in names:
                    totals[selected]['source_sections'][-1]['end_line'] = line_number
                selected, active = None, False
            elif not active:
                if selected is not None:
                    raise ValueError('route net name requires a section at line ' + str(line_number))
                selected = line.replace('\\', '')
            elif selected in names:
                fields = line.split()
                if len(fields) != 6:
                    raise ValueError('route record requires six columns at line ' + str(line_number))
                x1, y1, layer1, x2, y2, layer2 = fields
                x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))
                value = totals[selected]
                value['record_count'] += 1
                if layer1 == layer2:
                    length = abs(x2 - x1) + abs(y2 - y1)
                    row = value['layers'].setdefault(layer1, {'wirelength_dbu': 0, 'segment_count': 0})
                    row['wirelength_dbu'] += length
                    row['segment_count'] += 1
                    value['same_layer_segment_count'] += 1
                else:
                    value['interlayer_transition_count'] += 1
    if active or selected is not None:
        raise ValueError('incomplete original route section')
    for value in totals.values():
        value['wirelength_um'] = sum(r['wirelength_dbu'] for r in value['layers'].values()) / scale
        value['layers'] = [{'layer': layer, 'wirelength_um': row['wirelength_dbu'] / scale,
                            'segment_count': row['segment_count']}
                           for layer, row in sorted(value['layers'].items(), key=lambda pair: (int(pair[0][1:]), pair[0]))]
    return totals


def original_route_totals(store, snapshot_id, names, root, query):
    snapshot, root = store.snapshot(snapshot_id), Path(root)
    requested = query.get('route_path')
    if not requested:
        directory = _run_dirs(snapshot, root)['results']
        if directory['candidate_count'] != 1:
            raise ValueError('original route query requires one results directory or route_path')
        requested = (Path(directory['path']) / (snapshot['stage'] + '.segments')).relative_to(root).as_posix()
    source = native_excerpt(store, snapshot_id, {'path': requested, 'max_bytes': '1'}, root)['source']
    scale = snapshot.get('run_summary', {}).get('dbu_per_micron')
    totals = segment_totals(source['path'], set(names), scale)
    return {'source': source, 'dbu_per_micron': scale, 'nets': totals,
            'source_type': 'original_global_route_segments', 'length_unit': 'um',
            'length_basis': 'same-layer Manhattan lengths over ALL original rows; zero-length rows count as segments',
            'transition_basis': 'interlayer rows as written; global-route estimates, not detailed-route via counts'}


def global_route_summary(store, snapshot_id, identifier, query, root):
    entity = _entity(store, snapshot_id, identifier, 'net')
    name = entity['name'].replace('\\', '')
    result = original_route_totals(store, snapshot_id, [name], root, query)
    rows = result.pop('nets')
    return {**result, 'snapshot': snapshot_identity(store.snapshot(snapshot_id)), 'snapshot_id': snapshot_id,
            'object_id': entity['object_id'], 'net_name': name, 'has_route_section': name in rows,
            'route': rows.get(name), 'evidence': [{**result['source'], 'source_type': result['source_type']}]}


def path_global_routes(store, snapshot_id, net_names, query, root):
    entities = [_entity(store, snapshot_id, name, 'net') for name in net_names]
    facts = original_route_totals(store, snapshot_id, net_names, root, query)
    rows = []
    for entity in entities:
        name, attributes = entity['name'].replace('\\', ''), entity.get('attributes') or {}
        route = facts['nets'].get(name)
        if route is None or route['record_count'] == 0:
            continue
        rows.append({'name': name, 'net_id': entity['object_id'], 'fanout': attributes.get('fanout'),
                     'signal_type': attributes.get('signal_type'), 'route': route})
    if query.get('signal_type'):
        rows = [row for row in rows if row['signal_type'] == query['signal_type']]
    rows.sort(key=lambda row: (-(row['fanout'] if row['fanout'] is not None else -1), row['name']))
    limit, offset = _limit({'limit': query.get('route_net_limit', '5')}), _offset({'offset': query.get('route_offset', '0')})
    selected = rows[offset:offset + limit]
    if query.get('include_route_connections') == '1':
        for row in selected:
            row['connectivity'] = net_engineering(store, snapshot_id, row['net_id'], {
                'include_instances': '1', 'limit': query.get('route_pin_limit', '20'),
                'offset': query.get('route_pin_offset', '0'), 'instance_limit': query.get('route_instance_limit', '20'),
                'instance_offset': query.get('route_instance_offset', '0')})
    return {**{k: v for k, v in facts.items() if k != 'nets'}, 'nets': selected,
            'candidate_path_net_count': len(entities), 'signal_type_filter': query.get('signal_type'),
            'ranking_scope': 'all selected original data-path nets with original global-route records; before pagination',
            'ranking': 'native fanout descending, full native name ascending',
            'unranked_missing_fanout_count': sum(row['fanout'] is None for row in rows),
            **_page(len(rows), len(selected), limit, offset)}
