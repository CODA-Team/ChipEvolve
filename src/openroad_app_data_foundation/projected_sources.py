"""Compact projections retain real sources and routes to every original locator."""
import json
from urllib.parse import quote


def projected_sources(snapshot_id, record_type, id_key, rows):
    sources, links = {}, []
    for row in rows:
        record_id = row[id_key]
        root = '/snapshots/' + quote(snapshot_id, safe='') + '/records/' + record_type + '/' + quote(record_id, safe='')
        links.append({'record_id': record_id, 'evidence_path': root + '/evidence',
                      'fragments_path': root + '/fragments'})
        for entry in row.get('evidence', []):
            ref = {key: value for key, value in entry.items() if key not in ('detail', 'locator')}
            sources[json.dumps(ref, sort_keys=True)] = ref
    return {'evidence': list(sources.values()), 'record_sources': links,
            'source_delivery': 'sources of returned records are deduplicated; complete original locators/fragments remain at record_sources routes'}
