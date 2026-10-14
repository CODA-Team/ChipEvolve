"""Concurrent use of a qualified binary must keep an intact atomic receipt."""

import json
from concurrent.futures import ThreadPoolExecutor

from goalevolve.platform.execution import write_json


def test_concurrent_receipts_have_independent_temporary_files(tmp_path):
    path = tmp_path / "platform-build.json"
    packets = [
        {"binary_sha256": str(i), "source_files": {"file": str(i)}} for i in range(32)
    ]
    with ThreadPoolExecutor(max_workers=8) as workers:
        list(workers.map(lambda packet: write_json(path, packet), packets))
    assert json.loads(path.read_text()) in packets
    assert not list(tmp_path.glob("*.tmp"))
