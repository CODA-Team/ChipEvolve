"""Measure a fixed listing workload on fresh durable state, without old services."""
import argparse
import json
from pathlib import Path
import statistics
import time

from openroad_platform_contracts import TaskSpec
from openroad_platform_runtime import RuntimeStore
from openroad_platform_provenance import EvidenceIndex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=150)
    args = parser.parse_args()
    if args.state.exists() or args.output.exists():
        raise SystemExit('Use fresh state and output paths.')
    args.state.mkdir(parents=True)
    store = RuntimeStore(args.state / 'runtime.sqlite')
    begin = time.monotonic()
    for i in range(args.count):
        store.submit_run(TaskSpec(task_id=f'listing-{i}', project_id='wanted' if i == 0 else 'other',
                                 design_id='benchmark', plugin_id='measurement'),
                         stage_key='main', plugin_version='1.0.0')
    population_seconds = time.monotonic() - begin
    index = EvidenceIndex(store)
    observations = []
    for filters in ({}, {'project_id': 'wanted'}, {'project_id': 'missing'}):
        samples, queries = [], []
        for _ in range(3):
            sql = []
            store._connection.set_trace_callback(sql.append)
            begin = time.monotonic()
            rows = index.runs(limit=10, **filters)
            samples.append(time.monotonic() - begin)
            store._connection.set_trace_callback(None)
            queries.append(len(sql))
        observations.append({'filters': filters, 'returned': len(rows), 'seconds': samples,
                             'median_seconds': statistics.median(samples), 'sql_queries': queries})
    store.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'runs': args.count, 'state': str(args.state.resolve()),
                                      'population_seconds': population_seconds,
                                      'observations': observations}, indent=2) + '\n')
    print(args.output)


if __name__ == '__main__':
    main()
