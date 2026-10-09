"""Real native processes verify shared EF/direct serialization and cancel release."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

from eda_toolkits.inputs import SnapshotExecutionClient,snapshot_inputs
from eda_toolkits.jobs import native_task


def wait(client,run_id,seconds=30):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        run=client.run(run_id)
        if run['status'] in ('succeeded','failed','cancelled','timed_out','lost'):return run
        time.sleep(.1)
    raise TimeoutError('lease acceptance exceeded wait')


def child(a):
    with a.lease.open('a') as lock:
        print('DIRECT_WAIT '+str(time.time()),flush=True)
        fcntl.flock(lock,fcntl.LOCK_EX)
        print('DIRECT_ACQUIRED '+str(time.time()),flush=True)
        result=subprocess.run([a.binary,'-threads','1','-no_init','-no_splash','-exit','/work/direct.tcl'],cwd=a.output,
          env={**os.environ,'EDA_ORFS_IMAGE':a.image})
        print('DIRECT_RELEASE '+str(time.time()),flush=True)
        if result.returncode:raise RuntimeError('real direct OpenROAD process failed')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--lease',type=Path,required=True);p.add_argument('--child',action='store_true')
    p.add_argument('--binary',default='/home/wjyuan/projects/eda-development/toolkits/.venv/bin/eda-openroad')
    p.add_argument('--image',default='/home/wjyuan/projects/eda-toolchain/orfs-8e6ee7aac233da07.sif');a=p.parse_args()
    if a.child:return child(a)
    a.output.mkdir(exist_ok=False);client=SnapshotExecutionClient('http://127.0.0.1:18700')
    op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open('http://127.0.0.1:18924/snapshots/physical-e00-v3-finish/summary?detail=full') as r:snapshot=json.load(r)['data']['snapshot']
    original,staged=snapshot_inputs(snapshot)
    (a.output/'direct.tcl').write_text('puts DIRECT_NATIVE_BEGIN\nafter 4000\nputs DIRECT_NATIVE_END\n')
    command=[sys.executable,str(Path(__file__).resolve()),'--child','--output',str(a.output),'--lease',str(a.lease),'--binary',a.binary,'--image',a.image]
    records=[]
    with (a.output/'direct-1.log').open('w') as log:
        direct=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        end=time.monotonic()+10
        while 'DIRECT_ACQUIRED' not in (a.output/'direct-1.log').read_text():
            if time.monotonic()>end:raise TimeoutError('direct did not acquire lease')
            time.sleep(.05)
        task=native_task(snapshot,original,staged,'puts EF_SHOULD_NOT_BEGIN\n')
        rid=client.submit(task)['run']['run_id']
        end=time.monotonic()+10
        while 'waiting for native EDA host lease' not in client.logs(rid,max_bytes=65536).get('content',''):
            if time.monotonic()>end:raise TimeoutError('EF did not wait for shared native lease')
            time.sleep(.05)
        started=time.monotonic();client.cancel(rid);run=wait(client,rid)
        records.append({'run_id':rid,'status':run['status'],'cancel_seconds':time.monotonic()-started,
          'logs':client.logs(rid,max_bytes=65536),'resources':client.resources(rid)})
        assert run['status']=='cancelled' and records[-1]['cancel_seconds']<5
        assert 'EF_SHOULD_NOT_BEGIN' not in records[-1]['logs'].get('content','')
        direct.wait(timeout=10);assert direct.returncode==0
    held=native_task(snapshot,original,staged,'puts EF_NATIVE_HOLD_BEGIN\nafter 4000\nputs EF_NATIVE_HOLD_END\n')
    rid=client.submit(held)['run']['run_id'];end=time.monotonic()+15
    while 'EF_NATIVE_HOLD_BEGIN' not in client.logs(rid,max_bytes=65536).get('content',''):
        if time.monotonic()>end:raise TimeoutError('EF did not start real native holder')
        time.sleep(.05)
    (a.output/'direct.tcl').write_text('puts DIRECT_NATIVE_BEGIN\nputs DIRECT_NATIVE_END\n')
    with (a.output/'direct-2.log').open('w') as log:
        direct=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        time.sleep(.3)
        assert 'DIRECT_WAIT' in (a.output/'direct-2.log').read_text()
        assert 'DIRECT_ACQUIRED' not in (a.output/'direct-2.log').read_text()
        started=time.monotonic();client.cancel(rid);run=wait(client,rid)
        direct.wait(timeout=10);assert direct.returncode==0
        records.append({'run_id':rid,'status':run['status'],'cancel_seconds':time.monotonic()-started,
          'logs':client.logs(rid,max_bytes=65536),'resources':client.resources(rid)})
        assert run['status']=='cancelled'
    task=native_task(snapshot,original,staged,'puts EF_NATIVE_SUCCESSOR\n')
    rid=client.submit(task)['run']['run_id'];run=wait(client,rid)
    records.append({'run_id':rid,'status':run['status'],'logs':client.logs(rid,max_bytes=65536)})
    assert run['status']=='succeeded' and 'EF_NATIVE_SUCCESSOR' in records[-1]['logs'].get('content','')
    result={'passed':True,'shared_native_lock':str(a.lease),'cases':records,
      'direct_logs':['direct-1.log','direct-2.log'],'checks':['EF waited behind direct OpenROAD',
      'cancelled waiting EF did not enter native command','direct waited behind EF OpenROAD',
      'cancelling native EF released lease','next EF native task succeeded']}
    (a.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
