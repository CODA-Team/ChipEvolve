"""Observe real OpenROAD cancellation through EF on fresh owned state."""
import argparse
import json
import os
from pathlib import Path
import threading
import time

from openroad_platform_contracts import InputFile, PluginManifest, ResourceRequest, TaskSpec
from openroad_platform_runtime import RuntimeStore, WorkflowRuntime
from openroad_platform_runtime.guardian import ProcessGuardian

OPENROAD = '/opt/EDAs/OpenROAD-flow-scripts/versions/20260409/tools/install/OpenROAD/bin/openroad'
TOOLKIT_PYTHON = '/home/wjyuan/projects/eda-development/toolkits/.venv/bin/python'


def identity(pid):
    try:
        tail = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return {'state': tail[0], 'start_ticks': tail[19]}
    except FileNotFoundError:
        return None


class Resolver:
    def __init__(self):
        self.manifest = PluginManifest(
            plugin_id='openroad-data', plugin_version='0.1.0',
            adapter_entry=(TOOLKIT_PYTHON, '-I', '-m', 'eda_toolkits.openroad.adapter'),
            supported_arch=('x86_64',), capabilities=('analysis.report',),
            artifact_rules=({'kind': 'extractor_log', 'required': False},
                            {'kind': 'extractor_receipt', 'required': False}),
            progress_marker='[progress]',
        )

    def resolve(self, plugin_id, **options):
        assert plugin_id == self.manifest.plugin_id
        return self.manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', type=int, default=3)
    args = parser.parse_args()
    if args.state.exists() or args.output.exists():
        raise SystemExit('Use fresh state and output paths.')
    args.state.mkdir(parents=True)
    script = args.state / 'cancel.tcl'
    script.write_text('puts "P1_NATIVE_CANCEL_STARTED"\nexec sleep 90\n')
    store = RuntimeStore(args.state / 'runtime.sqlite')
    runtime = WorkflowRuntime(store, Resolver(), workspace_root=args.state / 'attempts',
                              worker_id='cancel-measurement', lease_seconds=30)
    rows = []
    for number in range(args.cases):
        task = TaskSpec(task_id=f'cancel-{number}', project_id='p2-acceptance', design_id='native',
                        plugin_id='openroad-data', timeout_seconds=120,
                        inputs={'adapter': 'command', 'extractor_command':
                                [OPENROAD, '-no_init', '-exit', 'inputs/cancel.tcl']},
                        staged_inputs=(InputFile(source=str(script.resolve()), destination='inputs/cancel.tcl'),),
                        resources=ResourceRequest(cpu_cores=1, memory_bytes=2 << 30, processes=32))
        run = runtime.submit(task)
        started = threading.Event()
        completed = threading.Event()
        errors = []

        def execute():
            try:
                runtime.execute_once(run.run_id, on_line=lambda line: started.set()
                                     if 'P1_NATIVE_CANCEL_STARTED' in line else None)
            except BaseException as error:
                errors.append(repr(error))
            finally:
                completed.set()

        execution = threading.Thread(target=execute)
        execution.start()
        if not started.wait(60):
            store.request_cancel(run.run_id)
            execution.join(60)
            raise RuntimeError('Native tool start handshake failed: ' + repr(errors))
        stage = store.list_stages(run.run_id)[0]
        attempt = store.list_attempts(stage.stage_run_id)[0]
        pids = ProcessGuardian._process_tree(attempt.process_id)
        originals = {pid: identity(pid) for pid in pids}
        if len(originals) < 3 or any(value is None for value in originals.values()):
            raise RuntimeError('Expected live adapter, OpenROAD and sleep processes.')
        timing = {}
        stopped = threading.Event()
        begin = time.monotonic()

        def observe():
            while not stopped.is_set():
                present = []
                runnable = []
                for pid, original in originals.items():
                    current = identity(pid)
                    if current and current['start_ticks'] == original['start_ticks']:
                        present.append(pid)
                        if current['state'] != 'Z':
                            runnable.append(pid)
                elapsed = time.monotonic() - begin
                if not runnable and 'runnable_gone_seconds' not in timing:
                    timing['runnable_gone_seconds'] = elapsed
                if not present:
                    timing['all_pids_gone_seconds'] = elapsed
                    return
                stopped.wait(0.025)

        observer = threading.Thread(target=observe)
        observer.start()
        store.request_cancel(run.run_id)
        timing['cancel_request_seconds'] = time.monotonic() - begin
        if not completed.wait(60):
            raise RuntimeError('EF did not complete cancellation within observation budget.')
        timing['terminal_seconds'] = time.monotonic() - begin
        observer.join(timeout=10)
        stopped.set()
        observer.join()
        execution.join()
        view = store.describe_run(run.run_id)
        row = {'number': number, 'run_id': run.run_id, 'identities': originals,
               'times': timing, 'terminal_run': view, 'execution_errors': errors,
               'passed': view['status'] == 'cancelled' and not errors
               and timing.get('all_pids_gone_seconds', float('inf')) <= 5
               and timing['terminal_seconds'] <= 5}
        rows.append(row)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({'state': str(args.state.resolve()), 'cases': rows,
                                          'passed': all(item['passed'] for item in rows)}, indent=2) + '\n')
        print(json.dumps({'number': number, 'passed': row['passed'], **timing}), flush=True)
    store.close()
    return 0 if all(item['passed'] for item in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
