"""Honest synthetic workload: scans, one-time RAM index, persistent foundation.

All arms have identical objects; indexing/preparation time and data size count.
A RAM dictionary is an intentionally strong direct-Python baseline.
"""
import argparse
import json
from pathlib import Path
import statistics
import tempfile
import time

from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.catalog import named_context

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--rows', type=int, default=50000)
parser.add_argument('--queries', type=int, default=100)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='eda-data-mechanism-') as directory:
    base = Path(directory)
    objects = [{'object_id': f'instance:{i}', 'kind': 'instance', 'name': f'top/u{i}', 'cell_type': 'BUF_X1'} for i in range(args.rows)]
    payload = {'snapshot': {'snapshot_id': 'synthetic', 'design_id': 'synthetic', 'revision_id': 'r1',
                            'run_id': 'synthetic', 'stage': 'route', 'created_at': '2026-10-08T00:00:00Z'}, 'entities': objects}
    path = base / 'objects.json'
    begin = time.perf_counter()
    path.write_text(json.dumps(objects))
    serialization = time.perf_counter() - begin
    begin = time.perf_counter()
    loaded = json.loads(path.read_text())
    parse_seconds = time.perf_counter() - begin
    begin = time.perf_counter()
    indexed = {row['name']: row for row in loaded}
    ram_index_seconds = time.perf_counter() - begin
    names = [f'top/u{(i * 7919) % args.rows}' for i in range(args.queries)]
    begin = time.perf_counter()
    store = DataStore(base / 'facts.sqlite')
    store.register(payload)
    import_seconds = time.perf_counter() - begin
    samples = {key: [] for key in ('scan_loaded_json', 'ram_dictionary', 'persistent_foundation')}
    for name in names:
        begin = time.perf_counter()
        scanned = next(row for row in loaded if row['name'] == name)
        samples['scan_loaded_json'].append(time.perf_counter() - begin)
        begin = time.perf_counter()
        cached = indexed[name]
        samples['ram_dictionary'].append(time.perf_counter() - begin)
        begin = time.perf_counter()
        fact = named_context(store, 'synthetic', {'kind': 'instance', 'name': name})
        samples['persistent_foundation'].append(time.perf_counter() - begin)
        assert fact['target']['id'] == scanned['object_id'] == cached['object_id']
    # Persistence and exact identity still hold after the process connection closes.
    store.close()
    begin = time.perf_counter()
    reopened = DataStore(base / 'facts.sqlite')
    assert named_context(reopened, 'synthetic', {'kind': 'instance', 'name': names[-1]})['target']['id'] == indexed[names[-1]]['object_id']
    restart_seconds = time.perf_counter() - begin
    reopened.close()
    result = {'kind': 'synthetic mechanism benchmark, not Codex or full-design EDA', 'rows': args.rows, 'queries': args.queries,
              'json_bytes': path.stat().st_size, 'sqlite_bytes': (base / 'facts.sqlite').stat().st_size,
              'serialization_seconds': serialization, 'direct_parse_seconds': parse_seconds,
              'direct_ram_index_seconds': ram_index_seconds, 'foundation_import_seconds': import_seconds,
              'foundation_restart_query_seconds': restart_seconds,
              'latency_ms': {key: {'median': statistics.median(values) * 1000, 'total_seconds': sum(values)} for key, values in samples.items()},
              'correctness': 'all identical target identities; restart passed',
              'limitations': 'single process local hot-cache measurements; foundation includes relation/context and envelope preparation, RAM baseline only exact identity'}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
