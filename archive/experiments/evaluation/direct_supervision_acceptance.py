"""Exercise direct baseline supervision with real native and orphan processes."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from direct_native import cleanup_owned, start_ticks, supervise
from direct_operations import DirectOperations


def alive(pid):
    try:
        value = Path(f'/proc/{pid}/stat').read_text()
        return value[value.rfind(')') + 2:].split()[0] != 'Z'
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--host', action='store_true')
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.host:
        DirectOperations(config, args.output).native(
            {'snapshot_id': config['snapshots'][0], 'script': 'puts READY; after 15000'}, 20
        )
        return
    args.output.mkdir(exist_ok=False)
    normal = args.output / 'normal'
    normal.mkdir()
    receipt = DirectOperations(config, normal).native(
        {'snapshot_id': config['snapshots'][0], 'script': 'report_units; puts NATIVE_OK'}, 20
    )
    assert receipt['exit_code'] == 0 and 'NATIVE_OK' in receipt['text']
    timeout = args.output / 'timeout'
    timeout.mkdir()
    expired = DirectOperations(config, timeout).native(
        {'snapshot_id': config['snapshots'][0], 'script': 'puts READY; after 15000'}, 1.5
    )
    assert expired['timed_out']
    assert not alive(json.loads(next((timeout / 'native').glob('*/process.json')).read_text())['pid'])
    outer = args.output / 'outer'
    outer.mkdir()
    with (outer / 'host.log').open('w') as log:
        host = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), '--host', '--config',
             str(args.config.resolve()), '--output', str(outer.resolve())],
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
        deadline = time.monotonic() + 10
        process_path = None
        while time.monotonic() < deadline:
            process_path = next((outer / 'native').glob('*/process.json'), None)
            if process_path:
                break
            assert host.poll() is None, 'outer host failed before native process registration'
            time.sleep(.05)
        assert process_path, 'native registration timed out'
        identity = json.loads(process_path.read_text())
        assert start_ticks(identity['pid']) == identity['start_ticks']
        os.kill(host.pid, signal.SIGKILL)
        host.wait()
    started = time.monotonic()
    cleanup = cleanup_owned(outer)
    for _ in range(100):
        if not alive(identity['pid']):
            break
        time.sleep(.05)
    assert cleanup and not alive(identity['pid']), 'owned native survived outer host cleanup'
    cleanup_seconds = time.monotonic() - started
    orphan = args.output / 'orphan'
    orphan.mkdir()
    child_path = orphan / 'child.pid'
    code = (
        "import subprocess,sys; p=subprocess.Popen([sys.executable,'-c',"
        "'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(20)']);"
        f"open({str(child_path)!r},'w').write(str(p.pid))"
    )
    orphan_outcome = supervise([sys.executable, '-c', code], folder=orphan,
                               env=dict(os.environ), seconds=5)
    child_pid = int(child_path.read_text())
    child_alive = alive(child_pid)
    if child_alive:
        os.kill(child_pid, signal.SIGKILL)
    summary = {'normal': receipt, 'timeout': expired, 'outer_cleanup': cleanup,
               'cleanup_seconds': cleanup_seconds,
               'orphan': {'outcome': orphan_outcome, 'child_pid': child_pid,
                          'alive_after_supervision': child_alive},
               'status': 'failed' if child_alive else 'passed'}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': summary['status'], 'orphan_survived': child_alive}))
    assert not child_alive, 'child survived a completed process leader'


if __name__ == '__main__':
    main()
