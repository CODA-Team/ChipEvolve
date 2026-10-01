"""Complete native net classifications, including the distinct isSpecial flag."""
import re

from .identity import snapshot_identity
from .native_queries import submit_native_query


def net_inventory(store, client, snapshot_id, native_root):
    snapshot = store.snapshot(snapshot_id)
    script = '''set b [[[ord::get_db] getChip] getBlock]
set total 0
set special 0
set types [dict create]
foreach n [$b getNets] {
    incr total
    if {[$n isSpecial]} {incr special}
    dict incr types [$n getSigType]
}
puts "EDA_NET_TOTAL $total"
puts "EDA_NET_SPECIAL $special"
dict for {type count} $types {puts "EDA_NET_TYPE $type $count"}
'''
    outcome = submit_native_query(store, client, snapshot_id,
        {'script': script, 'with_timing': False, 'wait_seconds': 120, 'max_bytes': 4096}, native_root)
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
              'coverage_scope': 'every net in the original snapshot OpenDB',
              'native_query': {'run_id': outcome['run']['run_id'], 'status': outcome['status']}}
    if outcome['status'] != 'succeeded':
        result['native_query']['report'] = outcome
        result['availability'] = {'net_inventory': {'status': 'unavailable',
            'reason': 'native query did not succeed; actual process status and report retained'}}
        return result
    text = outcome['excerpt']['text']
    total = re.findall(r'^EDA_NET_TOTAL (\d+)\s*$', text, re.M)
    special = re.findall(r'^EDA_NET_SPECIAL (\d+)\s*$', text, re.M)
    types = re.findall(r'^EDA_NET_TYPE (\w+) (\d+)\s*$', text, re.M)
    counts = {kind: int(count) for kind, count in types}
    if (outcome['excerpt'].get('truncated') or len(total) != 1 or len(special) != 1
            or len(counts) != len(types) or sum(counts.values()) != int(total[0])
            or int(special[0]) > int(total[0])):
        raise ValueError('native net inventory report is incomplete or malformed')
    result.update(net_count=int(total[0]), special_net_count=int(special[0]),
                  counts_by_signal_type=counts,
                  special_count_basis='actual OpenDB dbNet.isSpecial flag, independent of SigType',
                  evidence=[outcome['source']])
    return result
