"""Complete native net classifications, including the distinct isSpecial flag."""
from eda_toolkits.openroad.inventory import net_inventory_script, parse_net_inventory
import re

from .identity import snapshot_identity
from .native_queries import submit_native_query


def net_inventory(store, client, snapshot_id, native_root):
    snapshot = store.snapshot(snapshot_id)
    script = net_inventory_script()
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
    total_count, special_count, counts = parse_net_inventory(text, outcome['excerpt'].get('truncated', False))
    result.update(net_count=total_count, special_net_count=special_count,
                  counts_by_signal_type=counts,
                  special_count_basis='actual OpenDB dbNet.isSpecial flag, independent of SigType',
                  evidence=[outcome['source']])
    return result


def design_area(store, client, snapshot_id, native_root):
    """Report the actual selected database area instead of an earlier stage value."""
    outcome = submit_native_query(store, client, snapshot_id,
        {'script': 'report_design_area', 'with_timing': False, 'wait_seconds': 120, 'max_bytes': 4096}, native_root)
    result = {'snapshot_id': snapshot_id, 'status': outcome['status'],
              'run_id': outcome['run']['run_id'], 'unit': 'um^2',
              'basis': 'native report_design_area on the selected original database; reported precision retained'}
    if outcome['status'] != 'succeeded':
        result['report'] = outcome
        return result
    matches = re.findall(r'^Design area ([\d.eE+-]+) um\^2 ([\d.eE+-]+)% utilization\.\s*$',
                         outcome['excerpt']['text'], re.M)
    if len(matches) != 1 or outcome['excerpt'].get('truncated'):
        raise ValueError('native design area report is incomplete or malformed')
    result.update(value=float(matches[0][0]), utilization_percent=float(matches[0][1]),
                  evidence=[outcome['source']])
    return result
