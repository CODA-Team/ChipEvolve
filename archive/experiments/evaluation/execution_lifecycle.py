"""Actual native failure, deadline and process-tree cancellation acceptance."""
import argparse
import json
from pathlib import Path
import time
import urllib.request

from eda_toolkits.inputs import snapshot_inputs
from eda_toolkits.jobs import native_task
from openroad_platform_client import KernelClient


def wait(client, run_id, *, wanted=None, timeout=120):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        run=client.run(run_id)
        if run['status'] in ('succeeded','failed','cancelled','timed_out','lost') or run['status']==wanted:
            return run
        time.sleep(0.1)
    raise TimeoutError('job did not reach expected status within acceptance bound')


def process_tree_for_workspace(workspace):
    found=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal():continue
        try:
            args=(proc/'cmdline').read_bytes().split(b'\0')
            if any(str(workspace).encode() in arg for arg in args):
                stat=(proc/'stat').read_text().rsplit(')',1)[1].split()
                found.append({'pid':int(proc.name),'ppid':int(stat[1]),'command':[a.decode(errors='replace') for a in args if a]})
        except (OSError,ProcessLookupError):continue
    all_children={row['pid'] for row in found}
    # Descendants may have a /work path after the container translation.
    changed=True
    while changed:
        changed=False
        for proc in Path('/proc').iterdir():
            if not proc.name.isdecimal() or int(proc.name) in all_children:continue
            try:
                stat=(proc/'stat').read_text().rsplit(')',1)[1].split()
                if int(stat[1]) in all_children:
                    all_children.add(int(proc.name));changed=True
                    args=(proc/'cmdline').read_bytes().split(b'\0')
                    found.append({'pid':int(proc.name),'ppid':int(stat[1]),'command':[a.decode(errors='replace') for a in args if a]})
            except (OSError,ProcessLookupError):continue
    return found


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--kernel-url',default='http://127.0.0.1:18700')
    parser.add_argument('--data-url',default='http://127.0.0.1:18924')
    parser.add_argument('--snapshot',default='gcd-sprint30h2-finish')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    snapshot=json.load(opener.open(args.data_url+'/snapshots/'+args.snapshot+'/summary?detail=full'))['data']['snapshot']
    inputs,staged=snapshot_inputs(snapshot,False);client=KernelClient(args.kernel_url)
    cases=[('success','puts "LIFECYCLE_NATIVE_SUCCESS"',20,False),
           ('tool_failure','error "LIFECYCLE_REAL_OPENROAD_FAILURE"',20,False),
           ('timeout','puts "LIFECYCLE_NATIVE_STARTED"; exec sleep 90',3,False)]
    cases += [(f'cancel-{i}','puts "LIFECYCLE_NATIVE_STARTED"; exec sleep 90',120,True) for i in range(1,4)]
    results=[]
    for name,script,timeout,cancel in cases:
        task=native_task(snapshot,inputs,staged,script);task['timeout_seconds']=timeout
        task['task_id']='lifecycle-'+name+'-'+str(time.time_ns())
        task['project_id']='sprint-lifecycle'
        task['expected_artifacts']=[] if cancel or name=='timeout' else ['analysis_report']
        (args.output/(name+'-task.json')).write_text(json.dumps(task,indent=2)+'\n')
        submission=client.submit(task);run_id=submission['run']['run_id']
        trees=[];seconds=None;live=[]
        if cancel:
            running=wait(client,run_id,wanted='running')
            if running['status']!='running':raise RuntimeError('cancel case never entered a real running attempt')
            workspace=running['stages'][0]['attempts'][0]['workspace']
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                trees=process_tree_for_workspace(workspace)
                if any(row['command'] and Path(row['command'][0]).name=='sleep' for row in trees):break
                time.sleep(0.1)
            else:raise RuntimeError('cancel acceptance requires actual native tool and sleep child')
            start=time.monotonic();client.cancel(run_id);result=wait(client,run_id,timeout=10)
            live=[row['pid'] for row in trees if Path('/proc',str(row['pid'])).exists()]
            seconds=time.monotonic()-start
        else:
            result=wait(client,run_id)
        expected='cancelled' if cancel else {'success':'succeeded','tool_failure':'failed','timeout':'timed_out'}[name]
        row={'name':name,'run_id':run_id,'expected_status':expected,'run':result,
             'resources':client.resources(run_id),'artifacts':client.artifacts(run_id),
             'logs':client.logs(run_id,max_bytes=65536),'process_tree_before_cancel':trees,
             'remaining_recorded_pids':live,'cancel_seconds':seconds,
             'passed':result['status']==expected and (not cancel or seconds<=5 and not live)}
        (args.output/(name+'-result.json')).write_text(json.dumps(row,indent=2)+'\n')
        results.append(row)
        print(name,result['status'],seconds,row['passed'],flush=True)
    summary={'passed':all(row['passed'] for row in results),'results':[
        {key:row[key] for key in ('name','run_id','passed','cancel_seconds','remaining_recorded_pids')} for row in results]}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return 0 if summary['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
