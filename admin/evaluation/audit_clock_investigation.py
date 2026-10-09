"""Independently check development timing investigations against native oracle bytes."""
import argparse
import hashlib
import json
from pathlib import Path

from openroad_platform_client import KernelClient


def sources(value, result):
    if isinstance(value, dict):
        if isinstance(value.get('artifact_id'),str) and isinstance(value.get('sha256'),str):
            key=(value.get('run_id'),value['artifact_id'])
            if key[0]:result[key]=value
        for item in value.values():sources(item,result)
    elif isinstance(value,list):
        for item in value:sources(item,result)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sprint',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    native=args.sprint/'controlled-development-1/private'
    gold={}
    for alias in ('e00','e01'):
        setup=json.loads((native/alias/'setup.json').read_text())['checks']
        hold=json.loads((native/alias/'hold.json').read_text())['checks']
        gold[alias]={'setup':min(setup,key=lambda p:p['slack']),
                     'hold':min(hold,key=lambda p:p['slack'])}
    client=KernelClient('http://127.0.0.1:18700')
    answers=[]
    for name in ('clock-investigation-flash-2','clock-investigation-codex-host-6'):
        state=json.loads((args.sprint/(name+'.json')).read_text())
        refs={}
        for evidence in state['evidence']:sources(evidence['content'],refs)
        verified=[];errors=[]
        for (run_id,artifact_id),ref in refs.items():
            location=client.artifact_locator(run_id,artifact_id)
            digest=hashlib.sha256(Path(location['path']).read_bytes()).hexdigest()
            ok=digest==location['sha256']==ref['sha256']
            verified.append({'run_id':run_id,'artifact_id':artifact_id,'sha256':digest,'passed':ok})
            if not ok:errors.append('source digest mismatch: '+artifact_id)
        answer=state.get('answer')
        text=json.dumps(answer,ensure_ascii=False).replace('\u2212','-')
        numeric_tokens=['0.4316','0.27','0.22','-0.1616','-0.2116','0.08806']
        numeric_match=all(token in text for token in numeric_tokens)
        expected=[('e00',0.4316,0.27,-0.1616),('e01',0.4316,0.22,-0.2116)]
        native_match=all(all(abs(p[key]*1e9-value)<0.00001 for key,value in
                          [('data_arrival_time',arrival),('required_time',required),('slack',slack)])
                         for alias,arrival,required,slack in expected for p in [gold[alias]['setup']])
        known={e['evidence_id']:e for e in state['evidence']}
        critical_citations=bool(answer) and all(claim['evidence_ids'] and
            all(eid in known for eid in claim['evidence_ids']) for claim in answer['claims']
            if claim['kind'] in ('fact','comparison','causal'))
        scopes_match=all(e['scope'].get('snapshot_id') in
                         ('physical-e00-v3-finish','physical-e01-v3-finish') for e in state['evidence'])
        if not numeric_match:errors.append('missing required native numeric observations')
        if not native_match:errors.append('oracle values do not establish stated comparison')
        if not critical_citations:errors.append('missing critical evidence citation')
        if not scopes_match:errors.append('wrong experiment scope')
        # This explicit reviewer check is retained separately from lexical/numeric checks.
        review={'scope':'fixed gcd finish/typical/setup and hold',
                'mechanism':'same arrival, lower required follows changed original clock periods',
                'counterevidence':'registered ODB/netlist/library/SPEF identities agree; hold unchanged',
                'limits':'stored samples explicitly do not establish exhaustive closure',
                'unsupported_causal_assertion_found':False}
        answers.append({'model_run':name,'status':state['status'],'seconds':state['active_seconds'],
                        'native_numbers_match':numeric_match and native_match,
                        'source_checks':verified,'critical_citations_exist':critical_citations,
                        'scope_check':scopes_match,'review':review,'errors':errors,
                        'passed':state['status']=='answered' and not errors})
    result={'kind':'development audit, not sealed/effect measurement','answers':answers,
            'native_files':{str(p.relative_to(native)):hashlib.sha256(p.read_bytes()).hexdigest()
                            for alias in ('e00','e01') for p in (native/alias).glob('*.json')}}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':all(a['passed'] for a in answers),'answers':[
        {k:a[k] for k in ('model_run','passed','errors','seconds')} for a in answers]},indent=2))


if __name__=='__main__':main()
