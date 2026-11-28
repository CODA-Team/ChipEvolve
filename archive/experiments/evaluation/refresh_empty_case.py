"""Keep the first bad empty-report export; produce a new fixed export identity."""
import json,time,urllib.request
from pathlib import Path
from eda_toolkits.inputs import SnapshotExecutionClient
r=Path('/home/wjyuan/projects/eda-development/var/sprints/20261008-141846')
task=json.loads((r/'controlled-sealed-v1/public/e38/export-task.json').read_text())
sid='sealed-v2-e38-finish';task['task_id']=task['inputs']['snapshot_id']=sid
client=SnapshotExecutionClient('http://127.0.0.1:18700');out=r/'empty-report-recovery-1';out.mkdir(exist_ok=False)
(out/'task.json').write_text(json.dumps(task,indent=2)+'\n')
run_id=client.submit(task,idempotency_key=sid)['run']['run_id'];deadline=time.monotonic()+120
while time.monotonic()<deadline:
 run=client.run(run_id)
 if run['status'] in ('succeeded','failed','timed_out','cancelled'):break
 time.sleep(.2)
artifacts=client.artifacts(run_id)
(out/'result.json').write_text(json.dumps({'run':run,'artifacts':artifacts,'logs':client.logs(run_id,max_bytes=32768)},indent=2)+'\n')
assert run['status']=='succeeded'
bundle=next(a for a in artifacts if a['kind']=='data_snapshot')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
req=urllib.request.Request('http://127.0.0.1:18924/snapshots/from-run',data=json.dumps({'run_id':run_id,'artifact_id':bundle['artifact_id']}).encode(),headers={'Content-Type':'application/json'})
with opener.open(req,timeout=30) as response:(out/'import.json').write_text(json.dumps(json.load(response),indent=2)+'\n')
print(sid,run_id)
