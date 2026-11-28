"""Paired real Codex pilot, preserving full exec events and hard time budgets.

Four separate comparisons; raw agents can write scripts and build indexes.
This is a small local pilot, not a statistically powered general performance claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

from eda_ai_client import EdaAiClient
from openroad_platform_client import KernelClient

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--acceptance', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--repetitions', type=int, default=2)
parser.add_argument('--timeout', type=int, default=180)
parser.add_argument('--cases', nargs='+', default=['execution', 'data', 'interface', 'query'])
parser.add_argument('--model', default='gpt-6.1-sol')
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
acceptance = args.acceptance.resolve()
previous = json.loads((acceptance / 'results.json').read_text())
assert previous.get('status') == 'passed', 'requires successful real acceptance'
successes = [row for row in previous['cases'] if row['execution_status'] == 'succeeded']
runs = [row['run_id'] for row in successes]
snapshots = [row['snapshot_id'] for row in successes]
http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
env = dict(os.environ, PYTHONNOUSERSITE='1', NO_PROXY='localhost,127.0.0.1,::1', no_proxy='localhost,127.0.0.1,::1')
for key in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'CONDA_PREFIX'):
    env.pop(key, None)


def call(url, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    with http.open(urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}), timeout=15) as response:
        return json.load(response)


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait(url):
    until = time.monotonic() + 15
    while True:
        try:
            return call(url)
        except OSError:
            if time.monotonic() >= until:
                raise
            time.sleep(0.1)


properties = {key: {'type': ['number', 'null']} for key in ('wns_ns', 'delta_wns_ns', 'cpu_seconds', 'peak_memory_bytes')}
properties.update({key: {'type': ['boolean', 'null']} for key in ('unique_scope', 'missing_object', 'unsupported_cause', 'exact_net_found', 'deduplicated')})
properties.update({key: {'type': ['string', 'null']} for key in ('run_id', 'snapshot_id')})
properties.update({'status': {'type': 'string'}, 'evidence': {'type': 'array', 'items': {'type': 'string'}}, 'notes': {'type': 'string'}})
schema = {'type': 'object', 'additionalProperties': False, 'properties': properties, 'required': list(properties)}
(out / 'schema.json').write_text(json.dumps(schema))
processes, handles, results = [], [], []
kernel_url, data_url = f'http://127.0.0.1:{port()}', f'http://127.0.0.1:{port()}'
prep_start = time.monotonic()
try:
    for name, command in [
        ('execution', [sys.executable, '-m', 'openroad_platform_gateway', '--state-root', str(acceptance / 'kernel'),
                       '--plugins-root', str(ROOT / 'execution-foundation/plugins'), '--admissions-root', str(ROOT / 'execution-foundation/admissions'),
                       '--port', kernel_url.rsplit(':', 1)[1]]),
        ('data', [sys.executable, '-m', 'openroad_app_data_foundation', '--db', str(acceptance / 'data.sqlite'), '--kernel-url', kernel_url,
                  '--no-auto-import', '--port', data_url.rsplit(':', 1)[1], '--native-root', str(out / 'native')]),
    ]:
        log = (out / (name + '.log')).open('w')
        handles.append(log)
        processes.append(subprocess.Popen(command, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT))
    wait(kernel_url + '/health')
    wait(data_url + '/health')
    sdk, client = EdaAiClient(data_url=data_url, kernel_url=kernel_url), KernelClient(kernel_url)
    raw_data = []
    for row in successes:
        raw = {'snapshot': call(data_url + '/snapshots/' + row['snapshot_id'] + '?detail=full')['data']['snapshot']}
        base = acceptance / ('direct-' + row['label'])
        raw['observations'] = [json.loads(line) for line in (base / 'query-data/observations.jsonl').read_text().splitlines()]
        raw['objects'] = [json.loads(line) for line in (base / 'query-data/objects.jsonl').read_text().splitlines()]
        raw['timing_paths'] = [json.loads(line) for line in (base / 'query-data/timing_paths.jsonl').read_text().splitlines()]
        raw['report'] = (base / 'report.rpt').read_text()
        raw['clock_period_ns'] = 1.0 if row['label'] == 'baseline' else 0.2
        raw_data.append(raw)
    regression = next(row for row in raw_data[1]['observations'] if row['observation_id'] == 'metric:ws')['value']
    assert regression < 0
    report_hashes = {ref['sha256'] for row in raw_data for ref in row['snapshot']['source_artifacts'] if ref.get('logical_path') == 'report.rpt'}
    fixture = {'snapshot': {'snapshot_id': 'interface:one', 'design_id': 'interface-fixture', 'revision_id': 'fixture',
                            'run_id': 'interface-run', 'stage': 'fixture', 'created_at': '2026-10-08T00:00:00Z'},
               'entities': [{'object_id': 'net:7', 'name': 'net:literal/name+space', 'kind': 'net'},
                            {'object_id': 'i:1', 'name': 'core/u1+test%1', 'kind': 'instance', 'cell_type': 'BUF_X1'}]}
    existing_fixture = call(data_url + '/snapshots?design_id=interface-fixture')['data']['snapshots']
    if not existing_fixture:
        call(data_url + '/snapshots', fixture)
    prep_seconds = time.monotonic() - prep_start
    # Execute paired arms in alternating order to avoid a fixed warm-cache advantage.
    for repeat in range(args.repetitions):
        for case in args.cases:
            for arm in (('raw', 'infra') if repeat % 2 == 0 else ('infra', 'raw')):
                label = f'{case}-{arm}-{repeat + 1}'
                record = out / label
                record.mkdir()
                workspace = Path(tempfile.mkdtemp(prefix='eda-codex-' + label + '-'))
                for name in ('extract_timing.py', 'design.v'):
                    shutil.copyfile(ROOT / 'admin/benchmarks' / name, workspace / name)
                (workspace / 'sources.json').write_text(json.dumps(raw_data, indent=2))
                instructions = f'''This is a controlled benchmark in {workspace}. Only write to this workspace. Do not inspect other project source code, other evaluations or production services. You may write Python/shell scripts, build indexes, inspect files and call tools. No confirmation is needed. The hard time limit is {args.timeout} seconds. Work efficiently. Final output must match the supplied schema; use null for irrelevant fields. Evidence must include the source path/URL and SHA256 when it exists. Do not invent facts or claim an EDA diagnosis from unavailable physical data.
Use Python interpreter {sys.executable}. OpenROAD wrapper is /home/wjyuan/projects/eda-ai-formal-20261002/openroad_exec. extract_timing.py is an actual tool invocation on design.v; the library is Nangate45 typical inside the wrapper image. Sources.json is identical in both arms and includes reports, immutable experiment metadata and source artifacts. WNS=min(0,worst setup slack). Values are nanoseconds. The fixture uses ideal nets without parasitics.
'''
                if arm == 'raw':
                    instructions += 'Use direct terminal tools and files for execution/data/query cases; do not call our SDK, Query Agent or foundation services. You may implement your own scripts or index. For the interface case you may call the public Data Foundation API directly, but not the SDK.\n'
                else:
                    instructions += f'''Use our infrastructure for this case. Public services: kernel={kernel_url}, data={data_url}. SDK is installed: from eda_ai_client import EdaAiClient; c=EdaAiClient(data_url="{data_url}",kernel_url="{kernel_url}"). SDK envelopes have status/missing/data/scope/evidence. resolve_scope(design_id/run_id/stage/snapshot_id) never chooses among ambiguous candidates. get_metrics(snapshot_id=...,name="WNS"), get_instance(snapshot_id,name), get_net_context(snapshot_id,net,by="name"), get_object_context(snapshot_id,kind,name) use service resolution. Read status first.
For Query Agent use {sys.executable} -m query_agent.interfaces.cli ask QUESTION --kernel-url {kernel_url} --data-url {data_url} --design buffer-chain --stage timing --compare-runs {runs[0]} {runs[1]} for comparison; root-cause questions may return NEEDS_MORE_DATA and this is an expected truthful outcome.
'''
                if case == 'execution':
                    key = 'codex-' + label
                    instructions += f'''Task: run one real timing experiment with clock period 0.3 ns on design.v and task key {key}. Repeat the submission of the same key and prevent duplicate execution. Return WNS, measured CPU seconds and peak memory bytes (any honest process measurement method is fine), whether deduplication actually happened, and report path/SHA256. Record enough evidence on disk to verify the run and failure reason if it fails. Do not use prior experiment output as the new result.\n'''
                    if arm == 'infra':
                        instructions += f'''Use public KernelClient from openroad_platform_client. upload_input(bytes) -> dict with input_id. submit(task,idempotency_key=KEY) -> {{"run":...}}; run(run_id), resources(run_id), artifacts(run_id), artifact_excerpt(run_id,artifact_id), artifact_bytes(run_id,artifact_id). Submit this schema: {{"schema_version":3,"task_id":"{key}","project_id":"codex-benchmark","design_id":"buffer-chain","plugin_id":"openroad-data","timeout_seconds":60,"inputs":{{"adapter":"command","extractor_command":["python3","extract_timing.py","--openroad","/home/wjyuan/projects/eda-ai-formal-20261002/openroad_exec","--period","0.3"],"netlist_path":"design.v","rc_script_path":"analysis.tcl","timing_report_path":"report.rpt"}},"staged_inputs":[{{"input_id":UPLOADED_ID,"destination":"extract_timing.py"}},{{"input_id":UPLOADED_ID,"destination":"design.v"}}]}}. Wait for a terminal status. Real WNS is in the report.rpt analysis_report artifact, not an execution-owned metric. All artifact downloads verify hashes.\n'''
                elif case == 'data':
                    instructions += f'''Task: for design buffer-chain, determine whether design-only scope identifies exactly one snapshot; do not select latest when ambiguous. Then get WNS for run {runs[1]} stage timing, identify the snapshot, and show exact source report/hash. Check that object ghost does not exist in that snapshot. Return unique_scope, wns_ns, missing_object, run_id and snapshot_id.\n'''
                elif case == 'interface':
                    instructions += f'''Task: query snapshot interface:one for net named literally "net:literal/name+space" and instance named "core/u1+test%1". Check ghost is absent. Preserve service outcomes. Return exact_net_found=true only if the matched net object_id is net:7; missing_object=true if ghost has not_found. Report lookup statuses in notes. There are no source evidence artifacts for this synthetic contract fixture; say so.
HTTP routes for both arms: GET {data_url}/snapshots/interface%3Aone/resolve-object?kind=net&name=URL_ENCODED_EXACT_NAME (instance similarly); all responses have envelopes. The raw arm can use curl/urllib/any standard client.\n'''
                else:
                    instructions += f'''Task: compare WNS between baseline run {runs[0]} and changed run {runs[1]}, changed minus baseline in ns. Is there enough evidence to claim buffer resizing caused the regression? Return delta_wns_ns, unsupported_cause (true means resizing is not established), missing data and source references with report hashes in notes/evidence. You may explain constraints that actually differ, but do not infer a physical root cause.\n'''
                    if arm == 'infra':
                        instructions += 'For this Query Agent comparison you must invoke query_agent.interfaces.cli for both the comparison and the causal question. SDK calls may supplement its evidence, but do not replace Query Agent with your own SDK-only comparison.\n'
                (record / 'prompt.txt').write_text(instructions)
                (record / 'workspace.txt').write_text(str(workspace))
                command = ['/home/wjyuan/.local/node/bin/codex', 'exec', '--ignore-user-config', '--ephemeral',
                           '--skip-git-repo-check', '-C', str(workspace), '-s', 'danger-full-access',
                           '-m', args.model, '-c', 'model_reasoning_effort="medium"', '-c', 'approval_policy="never"',
                           '--json', '--output-schema', str(out / 'schema.json'),
                           '--output-last-message', str(record / 'answer.json'), '-']
                start = time.monotonic()
                timed_out = False
                with (record / 'events.jsonl').open('w') as events, (record / 'stderr.txt').open('w') as errors:
                    try:
                        completed = subprocess.run(command, input=instructions, text=True, cwd=workspace, env=env,
                                                   stdout=events, stderr=errors, timeout=args.timeout, check=False)
                        exit_code = completed.returncode
                    except subprocess.TimeoutExpired:
                        timed_out, exit_code = True, None
                usage, calls, event_errors, commands_used = {}, 0, [], []
                for line in (record / 'events.jsonl').read_text().splitlines():
                    event = json.loads(line)
                    if event.get('type') == 'turn.completed':
                        usage = event.get('usage', {})
                    if event.get('type') == 'item.completed' and event.get('item', {}).get('type') == 'command_execution':
                        calls += 1
                        commands_used.append(event['item'].get('command', ''))
                    if event.get('type') in ('error', 'turn.failed'):
                        event_errors.append(event)
                answer = json.loads((record / 'answer.json').read_text()) if (record / 'answer.json').is_file() else {}
                checks = {}
                if case == 'execution':
                    checks['wns'] = answer.get('wns_ns') == 0.0
                    checks['measured_resources'] = isinstance(answer.get('cpu_seconds'), (int, float)) and answer['cpu_seconds'] > 0 and isinstance(answer.get('peak_memory_bytes'), (int, float)) and answer['peak_memory_bytes'] > 0
                    checks['deduplicated'] = answer.get('deduplicated') is True
                    if arm == 'infra':
                        matching = [row for row in client.runs(design_id='buffer-chain', limit=500) if row.get('task_id') == key]
                        checks['actual_single_run'] = len(matching) == 1 and matching[0]['status'] == 'succeeded'
                        aid = next((row for row in client.artifacts(matching[0]['run_id']) if row.get('store_key') == 'report.rpt'), None) if len(matching) == 1 else None
                        checks['verified_report'] = aid is not None and any(aid['sha256'] in ref for ref in answer.get('evidence', []))
                    else:
                        reports = [p for p in workspace.rglob('report.rpt') if 'WS_NS=' in p.read_text(errors='replace')]
                        checks['actual_single_run'] = len(reports) == 1
                        checks['verified_report'] = bool(reports) and any(hashlib.sha256(reports[0].read_bytes()).hexdigest() in ref for ref in answer.get('evidence', []))
                elif case == 'data':
                    checks = {'wns': abs(answer.get('wns_ns', 999) - regression) < 1e-7 if isinstance(answer.get('wns_ns'), (int, float)) else False,
                              'scope': answer.get('unique_scope') is False and answer.get('run_id') == runs[1] and answer.get('snapshot_id') == snapshots[1],
                              'missing': answer.get('missing_object') is True,
                              'source': any(digest in ref for digest in report_hashes for ref in answer.get('evidence', []))}
                elif case == 'interface':
                    cited = urllib.parse.unquote(answer.get('notes', '') + '\n' + '\n'.join(answer.get('evidence', [])))
                    checks = {'literal_net_name': answer.get('exact_net_found') is True, 'missing': answer.get('missing_object') is True,
                              'instance': 'available' in cited and 'core/u1+test%1' in cited}
                else:
                    checks = {'delta': abs(answer.get('delta_wns_ns', 999) - regression) < 1e-7 if isinstance(answer.get('delta_wns_ns'), (int, float)) else False,
                              'no_unsupported_cause': answer.get('unsupported_cause') is True,
                              'source': any(digest in ref for digest in report_hashes for ref in answer.get('evidence', []))}
                    if arm == 'infra':
                        checks['query_agent_used'] = any('query_agent.interfaces.cli' in command for command in commands_used)
                result = {'case': case, 'arm': arm, 'repeat': repeat + 1, 'model': args.model, 'reasoning_effort': 'medium',
                          'hard_timeout_seconds': args.timeout, 'seconds': time.monotonic() - start, 'exit_code': exit_code,
                          'timed_out': timed_out, 'tool_calls': calls, 'usage': usage, 'checks': checks,
                          'passed': bool(checks) and all(checks.values()) and exit_code == 0, 'errors': event_errors}
                (record / 'result.json').write_text(json.dumps(result, indent=2))
                results.append(result)
                (out / 'results.json').write_text(json.dumps({'setup_seconds': prep_seconds, 'results': results}, indent=2))
                print(json.dumps({key: result[key] for key in ('case', 'arm', 'repeat', 'seconds', 'passed', 'checks')}), flush=True)
finally:
    for process in processes:
        process.terminate()
    for process in processes:
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    for handle in handles:
        handle.close()
