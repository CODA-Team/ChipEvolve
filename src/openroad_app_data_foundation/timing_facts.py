"""Associate supplemental STA paths with the exact database they analysed."""
from .identity import snapshot_identity


def timing_fact_snapshot(store, snapshot):
    def database_digests(item):
        return {r['sha256'] for r in item.get('source_artifacts', [])
                if r.get('category') == 'raw_design_database'}
    seen = set()
    while snapshot.get('run_summary', {}).get('timing_context', {}).get('parent_snapshot_id'):
        if snapshot['snapshot_id'] in seen:
            raise ValueError('timing query parent cycle')
        seen.add(snapshot['snapshot_id'])
        parent_id = snapshot['run_summary']['timing_context']['parent_snapshot_id']
        parent = store.snapshot(parent_id)
        for key in ('design_id', 'revision_id', 'run_id', 'stage'):
            if snapshot[key] != parent[key]:
                raise ValueError('timing query parent has a different ' + key)
        digests = database_digests(snapshot)
        if len(digests) != 1 or digests != database_digests(parent):
            raise ValueError('timing query and parent must cite the same original database digest')
        snapshot = parent
    return snapshot


def fact_source(snapshot):
    return {'snapshot': snapshot_identity(snapshot),
            'database': [r for r in snapshot.get('source_artifacts', [])
                         if r.get('category') == 'raw_design_database']}
