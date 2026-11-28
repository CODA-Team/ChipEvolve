"""Check pilot answers against actual native report bytes, not QA/DF parsers."""
import hashlib
import json
from pathlib import Path

from openroad_platform_client import KernelClient


def main():
    root = Path(__file__).resolve().parents[2] / 'var/sprints/20261008-141846'
    client = KernelClient('http://127.0.0.1:18700')
    source = client.artifact_locator('run-bff2197543cc4192aa559ce48c829fcf',
                                     'art-1de33a147a9c4483b9a78fee2743cd85')
    original = Path(source['path']).read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    raw = json.loads(original)
    checks = [path for path in raw['checks'] if path['path_type'] == 'max']
    worst = min(checks, key=lambda path: path['slack'])
    results = []
    for name, model in [('qa-investigation-codex-1.json', 'codex'),
                        ('qa-investigation-flash-5.json', 'deepseek-flash')]:
        state = json.loads((root/name).read_text())
        answer = state['answer']
        text = json.dumps(answer, ensure_ascii=False).replace("\u2212", "-")
        main_match = all(value in text for value in (
            worst['startpoint'], worst['endpoint'], str(round(worst['slack']*1e9,4))))
        sources_match = digest in text and digest == source['sha256']
        errors = []
        if model == 'deepseek-flash' and 'within 0.3 ps' in answer['summary']:
            errors.append({'kind':'incorrect_extra_arithmetic',
                           'claim':'Runners-up are within 0.3 ps',
                           'actual_gaps_ps':[0.8,2.1]})
        results.append({'model':model, 'state_status':state['status'],
                        'main_endpoint_and_slack_match_native':main_match,
                        'source_digest_verified':sources_match,
                        'sample_scope_stated':'sample' in text.lower(),
                        'secondary_errors':errors, 'seconds':state['active_seconds'],
                        'answer_file':name,
                        'overall_passed':main_match and sources_match and not errors})
    report = {'kind':'development pilot; not formal effect evidence',
              'native_source':{key:source[key] for key in ('sha256','size_bytes')},
              'native_worst_setup':{key:worst[key] for key in ('startpoint','endpoint','slack')},
              'results':results,
              'next_change':'restrict unrequested comparisons and use deterministic returned deltas; retain first failure'}
    (root/'investigation-pilot-audit-2.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
