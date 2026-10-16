"""A receipt reader survives a real import commit longer than SQLite's default."""

import concurrent.futures
import sqlite3
import time

import pytest
from openroad_app_data_foundation.connections import ReadPool
from openroad_app_data_foundation.repository import DataStore


@pytest.mark.parametrize("size", [1, 2])
def test_pooled_receipt_reader_waits_for_writer_without_losing_response(tmp_path, size):
    path = tmp_path / "snapshots.sqlite"
    store = DataStore(path)
    pool = ReadPool(path, size=size)
    try:
        with pool.connection() as reader:
            assert reader.import_receipt("not-yet-committed") is None
        writer = sqlite3.connect(path)
        writer.execute("BEGIN EXCLUSIVE")
        with concurrent.futures.ThreadPoolExecutor(max_workers=size) as workers:

            def query():
                with pool.connection() as reader:
                    return reader.import_receipt("not-yet-committed")

            pending = [workers.submit(query) for _ in range(size)]
            time.sleep(5.2)  # Reproduces the deployed reader's five-second failure.
            assert not any(f.done() for f in pending), (
                "reader dropped the request during import"
            )
            writer.rollback()
            assert all(f.result(timeout=2) is None for f in pending)
        writer.close()
        with (
            pool.connection() as reader,
            pytest.raises(sqlite3.OperationalError, match="readonly"),
        ):
            reader.connection.execute("DELETE FROM artifact_import_receipts")
        assert pool.opened == size
    finally:
        pool.close()
        store.close()
