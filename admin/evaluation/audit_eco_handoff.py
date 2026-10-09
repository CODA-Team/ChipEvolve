"""Independent native/byte review of a real receiver, without product-parser gold."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import time
import urllib.request

from eda_toolkits.inputs import SnapshotExecutionClient, snapshot_inputs
from eda_toolkits.jobs import native_task
from openroad_platform_client import KernelClient


def main():
    p=argparse.ArgumentParser();p.add_argument('--sprint',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--package',type=Path);p.add_argument('--receiver-directory',type=Path)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    root=args.sprint;kernel=KernelClient('http://127.0.0.1:18700')
    execution=SnapshotExecutionClient('http://127.0.0.1:18700')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    package=json.loads((args.package or root/'eco-package-1.json').read_text())
    receiver=args.receiver_directory or root/'codex-eco-receiver-2/receiver'
    proposal=json.loads((receiver/'identity.json').read_text())['proposal']['changes']
    assert len(proposal)==1,'audit expects one explicitly permitted resize'
    change=proposal[0]
    before=json.loads((root/'physical-development-v3/e00/result.json').read_text())
    after=json.loads((receiver/'export.json').read_text())
    physical=json.loads((receiver/'physical.json').read_text())
    verified=[]
    def raw(result,path):
        ref=next(a for a in result['artifacts'] if a['store_key']==path)
        location=kernel.artifact_locator(result['run']['run_id'],ref['artifact_id'])
        data=Path(location['path']).read_bytes();digest=hashlib.sha256(data).hexdigest()
        assert digest==ref['sha256']==location['sha256']
        verified.append({'run_id':result['run']['run_id'],'artifact_id':ref['artifact_id'],
                         'store_key':path,'sha256':digest})
        return data
    old=raw(before,'outputs/candidate.v').decode();new=raw(after,'outputs/candidate.v').decode()
    allowed=next(p for p in package['buffer_permissions'] if p['instance']==change['instance'])
    assert change['target_master'] in allowed['allowed_masters']
    expected=old.replace(' '+allowed['original_master']+' '+allowed['instance']+' (',
                         ' '+change['target_master']+' '+allowed['instance']+' (')
    assert old!=new and expected==new,'unpermitted netlist change'
    (args.output/'netlist.diff').write_text(''.join(difflib.unified_diff(
        old.splitlines(True),new.splitlines(True),fromfile='baseline',tofile='candidate')))
    fixed={path:raw(before,path)==raw(after,path) for path in
           ('inputs/6_final.sdc','inputs/6_final.spef','inputs/library.lib')}
    checks={}
    for check,suffix in [('setup',''),('hold','_hold')]:
        key='query-data/timing_report'+suffix+'.json'
        old_checks=json.loads(raw(before,key))['checks']
        fresh_checks=json.loads(raw(after,key))['checks']
        immediate=json.loads(raw(physical,'outputs/'+check+'.json'))['checks']
        a=min(old_checks,key=lambda x:x['slack']);b=min(fresh_checks,key=lambda x:x['slack'])
        # Fresh-process reports are the evaluation authority; verify no stale resize cache.
        assert fresh_checks==immediate, 'resize cache differs from fresh-process STA'
        checks[check]={'baseline_worst_slack_ns':a['slack']*1e9,
                       'candidate_worst_slack_ns':b['slack']*1e9,
                       'delta_ns':(b['slack']-a['slack'])*1e9,
                       'baseline_endpoint':a['endpoint'],'candidate_endpoint':b['endpoint'],
                       'fresh_process_agrees_with_resize_process':True,
                       'baseline_reported_paths':len(old_checks),'candidate_reported_paths':len(fresh_checks)}
    area={}
    script='''set block [ord::get_db_block]
set dbu [$block getDbUnitsPerMicron]
set sum 0.0
foreach inst [$block getInsts] {
  set master [$inst getMaster]
  set sum [expr {$sum + double([$master getWidth])*[$master getHeight]/$dbu/$dbu}]
}
puts [format "EDA_EXACT_INSTANCE_AREA_UM2 %.12g" $sum]
puts "EDA_INSTANCE_COUNT [llength [$block getInsts]]"
'''
    for label,sid in [('baseline',package['scope']['snapshot_id']),
                      ('candidate',package['handoff_id']+'-candidate')]:
        with opener.open('http://127.0.0.1:18924/snapshots/'+sid+'/summary?detail=full') as r:
            snapshot=json.load(r)['data']['snapshot']
        original,staged=snapshot_inputs(snapshot)
        task=native_task(snapshot,original,staged,script)
        task['task_id']='receiver-review-area-'+hashlib.sha256(json.dumps(task,sort_keys=True).encode()).hexdigest()[:24]
        (args.output/(label+'-area-task.json')).write_text(json.dumps(task,indent=2))
        run_id=execution.submit(task,idempotency_key=task['task_id'])['run']['run_id']
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            run=execution.run(run_id)
            if run['status'] in ('succeeded','failed','cancelled','timed_out'):break
            time.sleep(.2)
        if run['status']!='succeeded':raise RuntimeError('native area did not succeed')
        result={'run':run,'artifacts':execution.artifacts(run_id),'logs':execution.logs(run_id,max_bytes=65536)}
        (args.output/(label+'-area-result.json')).write_text(json.dumps(result,indent=2))
        text=raw(result,'reports/native.rpt').decode();(args.output/(label+'-area.rpt')).write_text(text)
        line=next(s for s in text.splitlines() if s.startswith('EDA_EXACT_INSTANCE_AREA_UM2 '))
        area[label]=float(line.split()[-1])
    area['delta_um2']=area['candidate']-area['baseline']
    result={'kind':'development independent receiver audit; not sealed benchmark',
            'permissions_passed':True,'only_change':{'instance':allowed['instance'],'from':allowed['original_master'],'to':change['target_master']},
            'fixed_input_checks':fixed,'timing':checks,'area_um2':area,'sources':verified,
            'handoff_execution_passed':all(fixed.values()),
            'repair_success':checks['setup']['candidate_worst_slack_ns']>=0 and checks['hold']['candidate_worst_slack_ns']>=0,
            'limits':['Fixed original extracted wire parasitics; no reroute or signoff claim.',
                      'Native report_checks produces a path sample; no exhaustive timing closure claim.']}
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='sources'},indent=2))


if __name__=='__main__':main()
