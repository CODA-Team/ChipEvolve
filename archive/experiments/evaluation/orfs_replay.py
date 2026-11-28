"""Replay the public GCD flow profile, export and explicitly import its facts."""
import argparse
import json
from pathlib import Path
import time
import urllib.request

from eda_toolkits.environment import doctor
from eda_toolkits.orfs import OrfsToolkit
from openroad_platform_client import KernelClient


def record(client, run_id, path):
    result = {'run': client.run(run_id), 'logs': client.logs(run_id, max_bytes=65536),
              'resources': client.resources(run_id), 'artifacts': client.artifacts(run_id)}
    path.write_text(json.dumps(result, indent=2) + '\n')
    return result


def wait(client, run_id, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.run(run_id)
        if run['status'] in ('succeeded', 'failed', 'timed_out', 'cancelled', 'lost'):
            return run
        time.sleep(0.25)
    raise TimeoutError('acceptance wait expired; inspect persisted execution status')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--kernel-url', default='http://127.0.0.1:18700')
    parser.add_argument('--data-url', default='http://127.0.0.1:18924')
    parser.add_argument('--revision', required=True)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--resume-flow')
    parser.add_argument('--resume-export')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    config = json.loads(args.config.read_text())
    diagnosis = doctor(config)
    (args.output/'doctor.json').write_text(json.dumps(diagnosis, indent=2)+'\n')
    if not diagnosis['passed']:
        raise RuntimeError('toolchain doctor did not pass')
    client = KernelClient(args.kernel_url)
    toolkit = OrfsToolkit(client, config, args.output / 'assets')
    submitted = ({'run': client.run(args.resume_flow)} if args.resume_flow
                 else toolkit.submit_flow(revision=args.revision))
    if submitted['run']['task_id'] != args.revision:
        raise ValueError('resume flow revision differs from fixed replay input')
    (args.output/'flow-submission.json').write_text(json.dumps(submitted, indent=2)+'\n')
    run_id = submitted['run']['run_id']
    run = wait(client, run_id, 600)
    flow = record(client, run_id, args.output/'flow-result.json')
    if run['status'] != 'succeeded':
        raise RuntimeError('actual ORFS run failed; full record retained')
    export = ({'run': client.run(args.resume_export)} if args.resume_export
              else toolkit.export_flow(run_id, args.snapshot))
    if export['run']['task_id'] != args.snapshot:
        raise ValueError('resume export snapshot differs from fixed replay input')
    (args.output/'export-submission.json').write_text(json.dumps(export, indent=2)+'\n')
    export_id = export['run']['run_id']
    result = wait(client, export_id, 180)
    exported = record(client, export_id, args.output/'export-result.json')
    if result['status'] != 'succeeded':
        raise RuntimeError('OpenROAD export failed; full record retained')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    manifests = [item for item in exported['artifacts'] if item['kind'] == 'data_snapshot']
    if len(manifests) != 1:
        raise ValueError('expected exactly one exported snapshot manifest')
    request = urllib.request.Request(args.data_url+'/snapshots/from-run',
                                    data=json.dumps({'run_id':export_id,
                                                     'artifact_id':manifests[0]['artifact_id']}).encode(),
                                    headers={'Content-Type':'application/json'})
    with opener.open(request, timeout=30) as response:
        imported = json.load(response)
    (args.output/'import.json').write_text(json.dumps(imported, indent=2)+'\n')
    with opener.open(args.data_url+'/snapshots/'+args.snapshot+'/summary?detail=full',timeout=30) as response:
        summary = json.load(response)
    (args.output/'snapshot.json').write_text(json.dumps(summary, indent=2)+'\n')
    accepted = {'passed': summary.get('status') == 'available', 'flow_run':run_id,
                'export_run':export_id, 'snapshot_id':args.snapshot,
                'image_sha256':diagnosis['image_sha256'], 'flow_resources':flow['resources']}
    (args.output/'summary.json').write_text(json.dumps(accepted, indent=2)+'\n')
    print(json.dumps(accepted))
    return 0 if accepted['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
