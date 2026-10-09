"""Retrieve registered original locators and verify citation/evidence digests.

The archive execution endpoint is read-only. No native analysis is submitted.
Hash checks establish byte identity, not semantic support or causal attribution.
"""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

from openroad_platform_client import KernelClient, KernelError
from score_formal import load_state


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def collect_refs(value, refs):
    if isinstance(value, dict):
        if all(isinstance(value.get(k), str) for k in ('run_id', 'artifact_id', 'sha256')):
            refs.setdefault((value['run_id'], value['artifact_id']), set()).add(value['sha256'])
        for child in value.values():
            collect_refs(child, refs)
    elif isinstance(value, list):
        for child in value:
            collect_refs(child, refs)


def direct_checks(evidence, config):
    """Verify the strong baseline's file/index/native receipts on their own terms."""
    stored = evidence.get('operation', {})
    operation = {key: value for key, value in stored.items() if key not in ('parameters', 'options_json')}
    operation.update({row['name']: row['value'] for row in stored.get('parameters', [])})
    operation.update(json.loads(stored.get('options_json') or '{}'))
    response = evidence.get('response', {})
    checks = []
    baseline = Path(config['baseline_root'])
    if operation.get('kind') == 'file' and response.get('sha256'):
        snapshot = operation.get('snapshot_id')
        if not isinstance(snapshot, str):
            return [{'kind': 'raw_file', 'passed': False, 'reason': 'missing effective snapshot identity'}]
        path = (baseline / snapshot / response['path']).resolve()
        allowed = snapshot in config['snapshots'] and (baseline / snapshot).resolve() in path.parents
        checks.append({'kind': 'raw_file', 'path': str(path), 'expected': response['sha256'],
                       'passed': allowed and path.is_file() and file_digest(path) == response['sha256']})
    for index in response.get('source_indices', []):
        path = baseline / index['snapshot_id'] / 'index.sqlite'
        checks.append({'kind': 'native_index', 'path': str(path), 'expected': index['sha256'],
                       'passed': index['snapshot_id'] in config['snapshots'] and path.is_file()
                                 and file_digest(path) == index['sha256']})
    if response.get('native_config_sha256'):
        path = baseline / response['snapshot_id'] / 'native.json'
        checks.append({'kind': 'fixed_native_input_manifest', 'path': str(path),
                       'expected': response['native_config_sha256'],
                       'passed': response['snapshot_id'] in config['snapshots'] and path.is_file()
                                 and file_digest(path) == response['native_config_sha256']})
        output = Path(response['source'])
        folder = Path(config['_episode_folder']) / 'native'
        checks.append({'kind': 'actual_native_output', 'path': str(output), 'expected': response['sha256'],
                       'passed': folder.resolve() in output.resolve().parents and output.is_file()
                                 and file_digest(output) == response['sha256']})
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--formal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--kernel-url', default='http://127.0.0.1:18700')
    parser.add_argument('--archive-kernel-url', default='http://127.0.0.1:8700')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    clients = [KernelClient(url, timeout=15) for url in (args.kernel_url, args.archive_kernel_url)]
    cache_path = args.output / 'original-locators.json'
    cache = json.loads(cache_path.read_text()) if cache_path.is_file() else {}
    refreshed = set()
    records = []
    for path in sorted((args.formal / 'receipts').glob('*.json')):
        receipt = json.loads(path.read_text())
        folder = Path(receipt['folder'])
        state = load_state(folder, receipt['arm'])
        if state is None:
            records.append({'episode_id': receipt['episode_id'], 'status': 'no_state'})
            continue
        known = {row['evidence_id']: row for row in state.get('evidence', [])}
        answer = state.get('answer') or {}
        critical = [row for row in answer.get('claims', []) if row['kind'] in ('fact', 'comparison', 'causal')]
        citations = [{'text': row['text'], 'ids': row.get('evidence_ids', []),
                      'passed': bool(row.get('evidence_ids')) and all(eid in known for eid in row['evidence_ids'])}
                     for row in critical]
        evidence_checks = []
        direct_source_checks = []
        config = json.loads((folder / 'config.json').read_text()) if (folder / 'config.json').is_file() else {}
        config['_episode_folder'] = str(folder)
        refs = {}
        for eid, evidence in known.items():
            if receipt['arm'] in ('D', 'E'):
                raw_path = folder / 'evidence' / (eid + '.json')
                expected = evidence.get('provenance', {}).get('source_hash')
            else:
                raw_path = folder / 'evidence' / (eid + '.json')
                expected = evidence.get('sha256')
            # Failed operations can have no returned bytes; do not manufacture a hash.
            if expected:
                actual = file_digest(raw_path) if raw_path.is_file() else None
                evidence_checks.append({'evidence_id': eid, 'path': str(raw_path),
                                        'expected': expected, 'actual': actual, 'passed': actual == expected})
            collect_refs(evidence, refs)
            if receipt['arm'] in ('A', 'B'):
                direct_source_checks.extend(direct_checks(evidence, config))
        original_checks = []
        for (run_id, artifact_id), expected in sorted(refs.items()):
            key = run_id + '/' + artifact_id
            if key not in cache:
                errors = []
                for client in clients:
                    try:
                        locator = client.artifact_locator(run_id, artifact_id)
                        native_path = Path(locator['path'])
                        cache[key] = {'endpoint': client.base_url, 'locator': locator,
                                      'actual_sha256': file_digest(native_path),
                                      'actual_size_bytes': native_path.stat().st_size}
                        break
                    except (KernelError, OSError, KeyError) as error:
                        errors.append({'endpoint': client.base_url, 'error': str(error)})
                else:
                    cache[key] = {'errors': errors}
                cache_path.write_text(json.dumps(cache, indent=2) + '\n')
            native = cache[key]
            if key not in refreshed and 'locator' in native:
                native_path = Path(native['locator']['path'])
                try:
                    native['actual_sha256'] = file_digest(native_path)
                    native['actual_size_bytes'] = native_path.stat().st_size
                    native['checked_at'] = datetime.now(timezone.utc).isoformat()
                except OSError as error:
                    native.pop('actual_sha256', None)
                    native.pop('actual_size_bytes', None)
                    native['rehash_error'] = str(error)
                refreshed.add(key)
            passed = len(expected) == 1 and native.get('actual_sha256') == native.get('locator', {}).get('sha256') == next(iter(expected))
            passed &= native.get('actual_size_bytes') == native.get('locator', {}).get('size_bytes') if 'locator' in native else False
            original_checks.append({'run_id': run_id, 'artifact_id': artifact_id,
                                    'expected': sorted(expected), 'passed': passed, 'registered_original': native})
        records.append({'episode_id': receipt['episode_id'], 'folder': str(folder),
                        'state_status': state['status'], 'critical_citations': citations,
                        'saved_evidence_digests': evidence_checks, 'registered_originals': original_checks,
                        'direct_source_checks': direct_source_checks,
                        'citation_ids_passed': all(row['passed'] for row in citations),
                        'saved_evidence_passed': all(row['passed'] for row in evidence_checks),
                        'registered_originals_passed': all(row['passed'] for row in original_checks),
                        'direct_sources_passed': all(row['passed'] for row in direct_source_checks),
                        'registered_original_count': len(original_checks),
                        'semantic_support': 'separate review required; byte identity does not establish support'})
    cache_path.write_text(json.dumps(cache, indent=2) + '\n')
    (args.output / 'records.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
    summary = {'audited_at': datetime.now(timezone.utc).isoformat(),
               'recorded_episodes': len(records), 'no_state_episodes': sum(row.get('status') == 'no_state' for row in records),
               'unique_originals': len(cache),
               'direct_source_check_count': sum(len(row.get('direct_source_checks', [])) for row in records),
               'registered_original_check_count': sum(len(row.get('registered_originals', [])) for row in records),
               'failed_original_checks': sum(not row['passed'] for rec in records for row in rec.get('registered_originals', [])),
               'failed_evidence_digests': sum(not row['passed'] for rec in records for row in rec.get('saved_evidence_digests', [])),
               'failed_direct_sources': sum(not row['passed'] for rec in records for row in rec.get('direct_source_checks', [])),
               'failed_citation_ids': sum(not row['passed'] for rec in records for row in rec.get('critical_citations', [])),
               'archive_actions': 'GET artifact locator only; no submission/cancellation/restart',
               'source_auditor_sha256': file_digest(Path(__file__))}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
