"""Wait for the current complete campaign, audit it, and run the real P2 chain."""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from flow_native_baseline import WORKSPACE, now, write_json


def advance(native, state):
    output = native / 'p1-p2-handoff.json'
    if output.exists() or state.exists():
        raise SystemExit('Handoff or P2 state already exists; inspect it before continuing.')
    record = {'status': 'waiting_for_native', 'started_at': now(),
              'native_run': str(native), 'p2_state': str(state)}
    write_json(output, record)
    try:
        while True:
            receipt = json.loads((native / 'receipt.json').read_text())
            if receipt['status'] != 'running' and 'capture_exit_code' in receipt:
                break
            elapsed = (datetime.now(timezone.utc)
                       - datetime.fromisoformat(receipt['started_at'])).total_seconds()
            if elapsed > receipt['wall_budget_seconds'] + 120:
                raise TimeoutError('Native supervisor did not publish its complete terminal receipt.')
            time.sleep(5)
        if receipt['status'] != 'completed' or receipt['exit_code'] != 0:
            raise RuntimeError('Native campaign failed; preserve its receipt and diagnose before retrying.')
        record['status'] = 'auditing_p1'
        write_json(output, record)
        for script in ('review_native_consumption.py', 'accept_native_campaign.py'):
            subprocess.run([sys.executable, str(WORKSPACE / 'admin' / script),
                            '--run-root', str(native)], cwd=WORKSPACE, check=True)
        record['status'] = 'executing_p2'
        write_json(output, record)
        command = [sys.executable, str(WORKSPACE / 'dev.py'), 'execution-foundation',
                   'python', str(WORKSPACE / 'admin/run_a2_stage_acceptance.py'),
                   '--native-run', str(native), '--state', str(state)]
        record['p2_command'] = command
        write_json(output, record)
        subprocess.run(command, cwd=WORKSPACE, check=True)
        result = json.loads((state / 'receipt.json').read_text())
        if result.get('accepted') is not True:
            raise RuntimeError('P2 did not produce an accepted terminal receipt.')
        record.update(status='completed', finished_at=now(), p2_accepted=True)
        write_json(output, record)
    except Exception as error:
        record.update(status='failed', finished_at=now(),
                      error=type(error).__name__ + ': ' + str(error))
        write_json(output, record)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-run', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    advance(args.native_run.resolve(), args.state.resolve())
