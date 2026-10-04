"""Complete native pin classification counts from either original source view."""
from collections import Counter, defaultdict


def pin_type_summary(rows, net_key='net_name'):
    counts, connected, nets = Counter(), Counter(), defaultdict(set)
    missing = 0
    for row in rows:
        pin_type = row.get('native_pin_signal_type')
        if pin_type is None:
            missing += 1
            continue
        counts[pin_type] += 1
        if row[net_key] is not None:
            connected[pin_type] += 1
            nets[pin_type].add(row[net_key])
    return {'total_pin_count': len(rows), 'pin_counts_by_native_type': dict(counts),
            'connected_pin_counts_by_native_type': dict(connected),
            'distinct_net_counts_by_native_pin_type': {key: len(value) for key, value in nets.items()},
            'native_pin_classification_coverage': {'status': 'partial' if missing else 'complete',
                'unclassified_pin_count': missing, 'classified_pin_count': len(rows) - missing,
                'count_scope': 'classified original pins; complete only when no native classification is absent'},
            'classification_basis': 'dbMTerm.getSigType for instance pins; dbBTerm.getSigType for ports; connected-net type is a separate fact'}
