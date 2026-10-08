"""New analyses can reference old facts without copying or modifying an archive."""
import hashlib
import sqlite3
from copy import deepcopy

import pytest
from openroad_platform_contracts import ContractError

from test_data_foundation import pack
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.connections import ReadPool


def archive(tmp_path):
    path = tmp_path / 'archive.sqlite'
    store = DataStore(path)
    store.register(pack())
    store.close()
    return path


def test_union_reads_and_primary_writes_preserve_archive_bytes(tmp_path):
    path = archive(tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    primary = tmp_path / 'new.sqlite'
    store = DataStore(primary, archives=[path])
    child = deepcopy(pack())
    child['snapshot']['snapshot_id'] = 'analysis'
    try:
        assert store.find_instance('snap-1', 'u1')[0]['object_id'] == 'top/u1'
        store.register(child)
        assert {s['snapshot_id'] for s in store.snapshots()} == {'analysis','snap-1'}
        assert store.run_summary('analysis')['record_counts']['entities'] == 2
        with pytest.raises(ContractError, match='already exists'):
            store.register(pack())
        with pytest.raises(ContractError, match='cannot be modified'):
            store.store_fragments('snap-1', {'query-data/timing_report.json':b'{}'})
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            store.connection.execute('INSERT INTO archive0.imported_artifacts VALUES (?)',('x',))
        pool = ReadPool(primary, archives=store.archives)
        with pool.connection() as reader:
            assert len(reader.snapshots()) == 2
            assert reader.read_only
        pool.close()
    finally:
        store.close()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    reader = DataStore(primary, read_only=True, archives=[path])
    assert len(reader.snapshots()) == 2
    reader.close()


def test_cross_database_snapshot_collisions_are_rejected(tmp_path):
    path = archive(tmp_path)
    primary = tmp_path / 'new.sqlite'
    store = DataStore(primary)
    store.register(pack())
    store.close()
    with pytest.raises(ContractError, match='multiple databases'):
        DataStore(primary, archives=[path])
