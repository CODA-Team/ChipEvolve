"""Complete estimates from original global-route segment records, separate from dbWire."""
from eda_toolkits.openroad.routes import segment_totals
from pathlib import Path

from .artifacts import _run_dirs, native_excerpt
from .engineering import _entity, net_engineering
from .identity import snapshot_identity
from .metadata import recovery_path
from .queries import _limit, _offset, _page




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
            connectivity = net_engineering(store, snapshot_id, row['net_id'], {
                'include_instances': '1', 'limit': query.get('route_pin_limit', '20'),
                'offset': query.get('route_pin_offset', '0'), 'instance_limit': query.get('route_instance_limit', '20'),
                'instance_offset': query.get('route_instance_offset', '0')})
            if not query.get('fields') and query.get('detail', 'summary') == 'summary':
                omitted = [key for key in ('snapshot_id', 'snapshot', 'net', 'evidence', 'load_pins')
                           if key in connectivity]
                for key in omitted:
                    del connectivity[key]
                for role in ('driver', 'load'):
                    key = role + '_instances'
                    if 'names' in connectivity[key]:
                        del connectivity[key]['names']
                        omitted.append(key + '.names')
                original_query = {'include_instances': '1',
                    'limit': query.get('route_pin_limit', '20'), 'offset': query.get('route_pin_offset', '0'),
                    'instance_limit': query.get('route_instance_limit', '20'),
                    'instance_offset': query.get('route_instance_offset', '0')}
                connectivity['delivery'] = {'detail': 'summary', 'omitted_fields': omitted,
                    'full_details': recovery_path('/snapshots/' + snapshot_id + '/nets/' +
                                                 row['net_id'] + '/engineering', original_query),
                    'selection': 'complete connection and distinct-owner counts; driver pin page retained; '
                                 'load pin and owner name pages remain accessible through full_details'}
            row['connectivity'] = connectivity
    missing = sum(row['fanout'] is None for row in rows)
    result = {**{k: v for k, v in facts.items() if k != 'nets'}, 'nets': selected,
            'candidate_path_net_count': len(entities), 'signal_type_filter': query.get('signal_type'),
            'ranking_scope': 'all selected original data-path nets with original global-route records; before pagination',
            'ranking': 'native fanout descending, full native name ascending',
            'missing_fanout_count': missing, 'ranking_status': 'partial' if missing else 'complete',
            **_page(len(rows), len(selected), limit, offset)}
    if missing:
        result['availability'] = {'complete_fanout_ranking': {'status': 'unavailable',
            'reason': 'some routed nets lack native fanout; null fanouts are not verified zeros',
            'native_completion': '/snapshots/' + snapshot_id + '/native-queries'}}
    return result
