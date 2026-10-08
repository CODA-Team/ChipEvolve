"""Paged, explicit object relationships over immutable snapshot facts."""
from .identity import snapshot_identity
from .queries import _limit, _offset, _page
from .engineering import _entity


def object_relationships(store, snapshot_id, identifier, query):
    if set(query) - {'kind', 'limit', 'offset'}:
        raise ValueError('relationships accepts kind, limit and offset')
    kind = query.get('kind')
    if kind not in ('instance', 'pin', 'net'):
        raise ValueError('relationship target kind must be instance|pin|net')
    target = _entity(store, snapshot_id, identifier, kind)
    ids = [target['object_id']]
    if kind == 'instance':
        children = store.children_of(snapshot_id, target['object_id'])
        ids.extend(row['object_id'] for row in children)
    relations = store.relations_touching(snapshot_id, ids)
    relations.sort(key=lambda row: row['relation_id'])
    limit, offset = _limit(query), _offset(query)
    page = relations[offset:offset + limit]
    related = {target['object_id']}
    for row in page:
        related.update((row['subject_id'], row['object_id']))
    entities = store.entities_by_ids(snapshot_id, sorted(related))
    found = {row['object_id'] for row in entities}
    missing = sorted(related - found)
    return {'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
            'target': target, 'relations': page, 'entities': entities,
            'coverage': {'domain': 'all stored explicit relations touching the target and its pins',
                         'missing_entity_ids': missing},
            'availability': {'relation_endpoints': {'status': 'unavailable' if missing else 'available'}},
            **_page(len(relations), len(page), limit, offset)}
