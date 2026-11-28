"""Run only the twelve development cases; sealed answers are never inspected."""
import argparse,json,os,signal,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def main():
 p=argparse.ArgumentParser();p.add_argument('--sprint',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True);p.add_argument('--cases',nargs='+')
 p.add_argument('--models',nargs='+',default=['codex','flash']);p.add_argument('--flash-config',type=Path);a=p.parse_args()
 a.output.mkdir(exist_ok=False);specs=json.loads((Path(__file__).parent/'diagnosis-specs.json').read_text())[:12]
 availability=json.loads((a.sprint/'availability-v1/bindings.json').read_text())
 sid=lambda x:'physical-'+x+'-v3-finish'
 pairs={'diag-01':[sid('e00'),sid('e01')],'diag-02':[sid('e00'),sid('e02')],
        'diag-03':[sid('e00'),sid('e03')],'diag-04':[sid('e00'),sid('e04')],
        'diag-05':[sid('e00'),sid('e05')],'diag-06':[sid('e06'),sid('e07')],
        'diag-07':[sid('e00'),availability['e08']['snapshot_id']],
        'diag-09':[availability['e09']['snapshot_id']],
        'diag-10':[sid('e00'),sid('e10')],'diag-11':[sid('e00'),sid('e11')],
        'diag-12':[availability['e12']['snapshot_id']]}
 prompts={'diag-05':' Named path endpoint: resp_msg[12]; compare the same endpoint.',
          'diag-09':' The failed supplementary analysis is '+availability['e09']['failed_analysis_run_id']+'. Inspect its real execution record and logs.',
          'diag-12':' The directed original report used to_pin=clk; check object type, report selection and constraints.'}
 results=[]
 def episode(case,model):
  directory=a.output/(case['id']+'-'+model);directory.mkdir()
  command=[sys.executable,'-m','query_agent','investigate',case['question']+prompts.get(case['id'],''),
           '--state-root',str(directory),'--model',model]
  if case['id']=='diag-08':
   selectors=directory/'selectors.json';selectors.write_text('[{"design_id":"gcd","revision_id":"candidate","stage":"finish"}]')
   command+=['--scope-request',str(selectors)]
  else:
   for snapshot in pairs[case['id']]:command+=['--snapshot',snapshot]
  if model=='codex':command+=['--codex-mode','hosted']
  else:command+=['--flash-config',str(a.flash_config or a.sprint/'flash-low-settings.json'),
                '--cost-ledger',str(a.sprint/'cost-ledger.json')]
  (directory/'invocation.json').write_text(json.dumps(command,indent=2)+'\n')
  started=time.monotonic();timed_out=False
  with (directory/'result.json').open('w') as out,(directory/'stderr.txt').open('w') as errors:
   process=subprocess.Popen(command,stdout=out,stderr=errors,start_new_session=True)
   try:process.wait(timeout=190)
   except subprocess.TimeoutExpired:
    timed_out=True
    os.killpg(process.pid,signal.SIGTERM)
    try:process.wait(timeout=3)
    except subprocess.TimeoutExpired:
     os.killpg(process.pid,signal.SIGKILL);process.wait()
    # Cancel only analyses recorded by this episode, never other server jobs.
    from openroad_platform_client import KernelClient
    kernel=KernelClient('http://127.0.0.1:18700',timeout=5)
    cleanup=[]
    for f in (directory/'investigations').glob('*/state.json'):
     for ticket in json.loads(f.read_text()).get('pending_analyses',[]):
      if ticket['status'] in ('succeeded','failed','cancelled','timed_out'):continue
      try:cleanup.append({'run_id':ticket['run_id'],'result':kernel.cancel(ticket['run_id'])})
      except Exception as exc:cleanup.append({'run_id':ticket['run_id'],'error':str(exc)})
    (directory/'timeout-cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\n')
  try:state=json.loads((directory/'result.json').read_text())
  except ValueError:state={}
  record={'case_id':case['id'],'model':model,'status':state.get('status','no_state'),
          'seconds':time.monotonic()-started,'timed_out':timed_out,
          'exit_code':process.returncode if process else None,'stop_reason':state.get('stop_reason'),
          'answer_available':bool(state.get('answer')),'scope':'development only; not a formal grade'}
  (directory/'episode.json').write_text(json.dumps(record,indent=2)+'\n')
  print(json.dumps(record),flush=True)
  return record
 selected=[c for c in specs if not a.cases or c['id'] in a.cases]
 for model in a.models:
  with ThreadPoolExecutor(max_workers=2) as pool:results += list(pool.map(lambda c:episode(c,model),selected))
 (a.output/'summary.json').write_text(json.dumps(results,indent=2)+'\n')


if __name__=='__main__':main()
