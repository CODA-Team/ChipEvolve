"""Concurrent readers and worker crashes preserve committed runtime state."""
import sqlite3
import subprocess
import sys

from openroad_platform_contracts import TaskSpec
from openroad_platform_runtime import RuntimeStore


def test_open_reader_does_not_block_submission_and_keeps_its_snapshot(tmp_path):
    path = tmp_path / 'runtime.db'
    store = RuntimeStore(path)
    reader = sqlite3.connect(path, isolation_level=None, timeout=.1)
    try:
        reader.execute('BEGIN')
        assert reader.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0] == 0
        run = store.submit_run(TaskSpec(task_id='concurrent-reader', project_id='p',
                                       design_id='d', plugin_id='measurement'),
                               stage_key='main', plugin_version='1')
        assert reader.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0] == 0
        reader.execute('COMMIT')
        assert reader.execute('SELECT run_id FROM runtime_runs').fetchone()[0] == run.run_id
        assert store._connection.execute('PRAGMA synchronous').fetchone()[0] == 2
    finally:
        reader.close()
        store.close()


def test_committed_submission_survives_worker_exit_without_close(tmp_path):
    path = tmp_path / 'runtime.db'
    program = '''import os, sys
from openroad_platform_contracts import TaskSpec
from openroad_platform_runtime import RuntimeStore
store = RuntimeStore(sys.argv[1])
run = store.submit_run(TaskSpec(task_id='crash-committed', project_id='p',
                               design_id='d', plugin_id='measurement'),
                       stage_key='main', plugin_version='1')
print(run.run_id, flush=True)
os._exit(0)
'''
    completed = subprocess.run([sys.executable, '-c', program, str(path)],
                               check=True, capture_output=True, text=True)
    store = RuntimeStore(path)
    try:
        assert store.get_run(completed.stdout.strip()).task_id == 'crash-committed'
        assert store._connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    finally:
        store.close()
