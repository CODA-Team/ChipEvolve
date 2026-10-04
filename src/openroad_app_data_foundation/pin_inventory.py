"""Native pin types and connected-net types are separate engineering facts."""
import base64

from .engineering import _entity
from .identity import snapshot_identity
from .native_queries import submit_native_query, complete_native_text
from .queries import _limit, _offset, _page
from .pin_net_ranking import ranking_script, ranked_nets
from .pin_summary import pin_type_summary


def _parse(text):
    rows, totals = [], []
    for line in text.splitlines():
        if line.startswith('EDA_PIN_TOTAL '):
            totals.append(int(line.split()[1]))
        if not line.startswith('EDA_PIN\t'):
            continue
        fields = line.split('\t')
        if len(fields) != 7:
            raise ValueError('native pin inventory row is malformed')
        _, native_id, local, pin_type, direction, net, net_type = fields
        if not native_id.isdecimal() or int(native_id) <= 0:
            raise ValueError('native pin inventory ID is invalid')
        native_net = base64.b64decode(net, validate=True).decode() if net else None
        rows.append({'native_id': native_id,
            'local_name': base64.b64decode(local, validate=True).decode(),
            'native_pin_signal_type': pin_type, 'direction': direction,
            'net_name': native_net.replace('\\', '') if native_net is not None else None,
            'net_native_name': native_net,
            'connected_net_signal_type': net_type or None})
    if len(totals) != 1 or totals[0] != len(rows) or len({r['native_id'] for r in rows}) != len(rows):
        raise ValueError('native pin inventory is incomplete or has duplicate pins')
    return sorted(rows, key=lambda r: r['local_name'])


def pin_inventory(store, client, snapshot_id, identifier, query, root):
    if set(query) - {'limit', 'offset', 'fields', 'pin_type', 'direction', 'net_sort', 'sort', 'order', 'tail_limit'}:
        raise ValueError('pin inventory accepts limit,offset,fields,pin_type,direction,net_sort,sort,order,tail_limit')
    query = {**query, 'pin_type': query.get('pin_type', '').upper(), 'direction': query.get('direction', '').upper()}
    if query.get('pin_type', '') not in ('', 'SIGNAL', 'CLOCK', 'POWER', 'GROUND'):
        raise ValueError('pin_type must be SIGNAL|CLOCK|POWER|GROUND')
    if query.get('direction', '') not in ('', 'INPUT', 'OUTPUT', 'INOUT'):
        raise ValueError('direction must be INPUT|OUTPUT|INOUT')
    if query.get('sort', 'name') != 'name' or query.get('order', 'asc') not in ('asc', 'desc'):
        raise ValueError('pin sort must be name; order must be asc|desc')
    limit, offset = _limit(query), _offset(query)
    tail_size = _limit({'limit': query['tail_limit']}) if 'tail_limit' in query else 0
    net_script = ranking_script(query) if query.get('net_sort') else ''
    instance = _entity(store, snapshot_id, identifier, 'instance')
    native_id = instance.get('attributes', {}).get('native_id')
    if not isinstance(native_id, str) or not native_id.isdecimal() or int(native_id) <= 0:
        raise ValueError('instance lacks a valid native ID')
    script = '''set b [ord::get_db_block]
set i [odb::dbInst_getInst $b NATIVE_ID]
if {$i eq "NULL"} {error "original instance not found"}
puts "EDA_PIN_TOTAL [llength [$i getITerms]]"
foreach p [$i getITerms] {
    set m [$p getMTerm]
    set n [$p getNet]
    set name {}; set type {}
    if {$n ne "NULL"} {set name [$n getName]; set type [$n getSigType]}
    puts [join [list EDA_PIN [$p getId] [binary encode base64 -maxlen 0 [$m getName]] \
        [$m getSigType] [$m getIoType] [binary encode base64 -maxlen 0 $name] $type] "\\t"]
}'''.replace('NATIVE_ID', native_id)
    script += '\n' + net_script
    outcome = submit_native_query(store, client, snapshot_id,
        {'script': script, 'with_timing': False, 'wait_seconds': 120, 'max_bytes': 65536}, root)
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
        'instance': {'object_id': instance['object_id'], 'name': instance['name']},
        'native_query': {'run_id': outcome['run']['run_id'], 'status': outcome['status']}}
    if outcome['status'] != 'succeeded':
        result['native_query']['report'] = outcome
        return result
    text = complete_native_text(client, outcome)
    rows = _parse(text)
    for row in rows:
        row['full_name'] = instance['name'].replace('\\', '') + '/' + row['local_name'].replace('\\', '')
    selected = [r for r in rows if all(not query.get(k) or r[field] == query[k]
        for k, field in [('pin_type', 'native_pin_signal_type'), ('direction', 'direction')])]
    if query.get('order', 'asc') == 'desc':
        selected.reverse()
    native_nets = {r['net_native_name'] for r in selected if r['net_native_name'] is not None}
    result.update(**pin_type_summary(rows, net_key='net_native_name'),
        pins=selected[offset:offset + limit],
        selection={'pin_type': query.get('pin_type') or None, 'direction': query.get('direction') or None,
            'pin_count': len(selected), 'connected_pin_count': sum(r['net_native_name'] is not None for r in selected),
            'distinct_net_count': len(native_nets),
            'count_scope': 'all filtered native pins before pagination; distinct nets use exact native names'},
        order='local pin name lexicographically ' + ('descending' if query.get('order') == 'desc' else 'ascending'),
        name_spelling={'net_name': 'unescaped native name, as in object/engineering queries',
                       'net_native_name': 'exact original dbNet.getName spelling'},
        coverage_scope='every original native instance ITerm; summary counts independent of filtering and pagination',
        evidence=[outcome['source']], **_page(len(selected), len(selected[offset:offset + limit]), limit, offset))
    if tail_size:
        start = max(len(selected) - tail_size, 0)
        result['pins_tail'] = {'items': selected[start:],
            'order': result['order'], **_page(len(selected), len(selected[start:]), tail_size, start)}
    if query.get('net_sort'):
        result['net_ranking'] = ranked_nets(text, query)
    return result
