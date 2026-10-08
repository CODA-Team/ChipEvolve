"""Scope and name ambiguity belong to the service, including HTTP envelopes."""
from copy import deepcopy

import pytest

from test_data_foundation import pack
from openroad_app_data_foundation.catalog import design_catalog, named_context, resolve_scope, snapshot_metrics
from openroad_app_data_foundation.envelope import envelope
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler


@pytest.fixture
def store(tmp_path):
    db = DataStore(tmp_path / 'catalog.sqlite')
    db.register(pack())
    yield db
    db.close()


def test_catalog_counts_and_ambiguous_scope_are_authoritative(store):
    other = deepcopy(pack())
    other['snapshot'].update(snapshot_id='snap-2', stage='finish')
    # register normalizes the record-local snapshot ids.
    for collection in ('entities', 'timing_paths', 'physical_context'):
        for row in other[collection]:
            row['snapshot_id'] = 'snap-2'
    store.register(other)
    assert design_catalog(store)['designs'][0]['snapshot_count'] == 2
    result = envelope('/scope', {}, resolve_scope(store, {'run_id': 'run-1'}))
    assert result['status'] == 'partial'
    assert result['missing'] == ['unique_snapshot']
    assert resolve_scope(store, {'run_id': 'run-1', 'stage': 'route'})['snapshot']['snapshot_id'] == 'snap-1'
    assert resolve_scope(store, {'snapshot_id': 'snap-1', 'run_id': 'wrong'})['resolution_status'] == 'not_found'


def test_object_exact_name_id_and_missing_do_not_guess(store):
    query = {'kind': 'instance', 'name': 'u1'}
    result = named_context(store, 'snap-1', query)
    assert result['target']['id'] == 'top/u1'
    assert named_context(store, 'snap-1', {'kind': 'net', 'name': 'n1'})['target']['id'] == 'net:n1'
    missing = named_context(store, 'snap-1', {**query, 'name': 'missing'})
    assert envelope('/snapshots/snap-1/resolve-object', {}, missing)['status'] == 'not_found'
    with pytest.raises(ValueError, match='exactly one'):
        named_context(store, 'snap-1', {**query, 'object_id': 'top/u1'})


def test_duplicate_objects_are_partial(store):
    value = pack()
    value['snapshot']['snapshot_id'] = 'ambiguous'
    value['entities'].append({'object_id': 'top/u9', 'kind': 'instance', 'name': 'u1'})
    for key in ('entities', 'timing_paths', 'physical_context'):
        for row in value[key]:
            row['snapshot_id'] = 'ambiguous'
    store.register(value)
    result = named_context(store, 'ambiguous', {'kind': 'instance', 'name': 'u1'})
    assert result['resolution_status'] == 'partial'
    assert len(result['matches']) == 2


def test_snapshot_metric_owner_and_routes(store):
    assert snapshot_metrics(store, 'snap-1', {})['scope']['run_id'] == 'run-1'
    with pytest.raises(ValueError, match='conflicts'):
        snapshot_metrics(store, 'snap-1', {'run_id': 'wrong'})
    handler = object.__new__(Handler)
    handler.store, handler.auto_import = store, False
    assert handler._get('/designs', {})['designs'][0]['design_id'] == 'chip'
    assert handler._get('/scope', {'snapshot_id': 'snap-1'})['snapshot']['run_id'] == 'run-1'
    assert handler._get('/snapshots/snap-1/resolve-object', {'kind': 'net', 'name': 'n1'})['target']['id'] == 'net:n1'
    assert handler._get('/snapshots/snap-1/metrics', {})['scope']['snapshot_id'] == 'snap-1'
