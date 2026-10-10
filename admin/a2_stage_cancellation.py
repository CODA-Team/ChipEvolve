"""Cancel actual AES routing through HTTP and measure the owned process tree."""
import json
from pathlib import Path
import threading
import time

from flow_native_baseline import now, write_json
from measure_http_cancellation import identity


def process_snapshot():
    processes = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')', 1)[1].split()
            pid = int(path.parent.name)
            processes[pid] = {'parent': int(fields[1]), 'state': fields[0],
                              'start_ticks': fields[19],
                              'command': (path.parent / 'cmdline').read_bytes().replace(b'\0', b' ').decode()}
        except (FileNotFoundError, ProcessLookupError):
            continue
    return processes


def measure_routing_cancel(client, task, output):
    key = task['experiment_id'] + ':actual-routing-cancel'
    record = {'started_at': now(), 'task': task, 'idempotency_key': key, 'accepted': False}
    write_json(output, record)
    run = client.submit(task, idempotency_key=key)['run']
    run_id = run['run_id']
    record['run_id'] = run_id
    write_json(output, record)
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        run = client.run(run_id)
        if run['status'] in {'failed', 'succeeded', 'timed_out', 'lost', 'cancelled'}:
            raise RuntimeError('Routing ended before the cancellation handshake: ' + json.dumps(run))
        attempts = [attempt for stage in run.get('stages', []) for attempt in stage.get('attempts', [])]
        if attempts:
            workspace = Path(attempts[-1]['workspace'])
            log = workspace / 'extractor.log'
            if log.is_file() and '[INFO GRT-0019] Found ' in log.read_text():
                processes = process_snapshot()
                adapters = [pid for pid, value in processes.items()
                            if 'eda_toolkits.openroad.adapter' in value['command']
                            and Path(f'/proc/{pid}/cwd').resolve() == workspace]
                if len(adapters) == 1:
                    owned = set(adapters)
                    while children := {pid for pid, value in processes.items()
                                       if value['parent'] in owned} - owned:
                        owned.update(children)
                    originals = {pid: processes[pid] for pid in owned}
                    if any('openroad' in value['command'] and 'global_route.tcl' in value['command']
                           for value in originals.values()):
                        record['routing_log_before_cancel'] = log.read_text()
                        break
        time.sleep(.1)
    else:
        client.cancel(run_id)
        raise RuntimeError('Actual AES routing did not reach the cancellation handshake in 600 seconds')
    record.update(identities=originals, resources_before=client.resources(run_id))
    write_json(output, record)
    stop = threading.Event()
    errors, listing, timing = [], [], {}

    def list_load():
        try:
            while not stop.is_set():
                begin = time.monotonic()
                client.runs(project_id=task['project_id'], limit=10)
                listing.append(time.monotonic() - begin)
                stop.wait(.05)
        except Exception as error:
            errors.append(repr(error))

    def observe():
        while not stop.is_set():
            present = [pid for pid, original in originals.items()
                       if (current := identity(pid)) and current['start_ticks'] == original['start_ticks']]
            if not present:
                timing['all_pids_gone_seconds'] = time.monotonic() - begin
                return
            stop.wait(.025)

    loader = threading.Thread(target=list_load)
    loader.start()
    begin = time.monotonic()
    observer = threading.Thread(target=observe)
    observer.start()
    try:
        client.cancel(run_id)
        timing['cancel_response_seconds'] = time.monotonic() - begin
        while time.monotonic() - begin < 60:
            run = client.run(run_id)
            if run['status'] in {'cancelled', 'failed', 'succeeded', 'timed_out', 'lost'}:
                timing['terminal_seconds'] = time.monotonic() - begin
                break
            time.sleep(.1)
        observer.join(10)
    finally:
        stop.set()
        observer.join()
        loader.join()
    resources = client.resources(run_id)
    record.update(finished_at=now(), terminal_run=run, times=timing,
                  resources_after=resources, listing_seconds=listing, errors=errors,
                  timeline=client.timeline(run_id), artifacts=client.artifacts(run_id))
    record['accepted'] = (run['status'] == 'cancelled' and not errors
                          and timing.get('terminal_seconds', float('inf')) <= 5
                          and timing.get('all_pids_gone_seconds', float('inf')) <= 5
                          and resources['reserved'] == {'cpu_cores': 0, 'memory_bytes': 0})
    write_json(output, record)
    if not record['accepted']:
        raise RuntimeError('Actual routing cancellation failed acceptance; inspect ' + str(output))
    return record
