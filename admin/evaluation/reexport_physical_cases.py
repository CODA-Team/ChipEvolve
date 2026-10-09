"""Re-export physical experiments without falsely declaring them STA supplements."""
import argparse
import json
from pathlib import Path
import urllib.request

from controlled_native_cases import wait, write
from eda_toolkits.inputs import SnapshotExecutionClient


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cases',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--kernel-url',default='http://127.0.0.1:18700')
    parser.add_argument('--data-url',default='http://127.0.0.1:18924')
    parser.add_argument('--version',default='v3')
    args=parser.parse_args()
    client=SnapshotExecutionClient(args.kernel_url)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    bindings={}
    for path in sorted((args.cases/'public').glob('*/binding.json')):
        binding=json.loads(path.read_text())
        name=binding['case_experiment']
        folder=args.output/name
        if (folder/'binding.json').exists():
            bindings[name]=json.loads((folder/'binding.json').read_text())
            continue
        task=json.loads((path.parent/'export-task.json').read_text())
        sid='physical-'+name+'-'+args.version+'-finish'
        task['task_id']=task['inputs']['snapshot_id']=sid
        parent = task['inputs'].pop('parent_snapshot_id', None)
        if parent:
            task['labels']['experiment_parent_snapshot_id']=parent
        public_outputs = client.artifacts(binding['physical_run_id'])
        for original_path, destination in (
            ('reports/native.rpt', 'inputs/physical.rpt'),
            ('outputs/candidate.v', 'outputs/candidate.v'),
        ):
            source = next(item for item in public_outputs if item['store_key'] == original_path)
            task['staged_inputs'].append({'artifact_id':source['artifact_id'],
                                         'destination':destination})
        task['inputs']['native_extra_paths']=['inputs/physical.rpt', 'outputs/candidate.v']
        write(folder/'task.json',task)
        result=client.submit(task,idempotency_key=sid)
        run_id=result['run']['run_id']
        run=wait(client,run_id)
        artifacts=client.artifacts(run_id)
        write(folder/'result.json',{'run':run,'artifacts':artifacts,
                                  'logs':client.logs(run_id,max_bytes=65536)})
        if run['status']!='succeeded':
            raise RuntimeError('physical export failed: '+name)
        bundle=next(item for item in artifacts if item['kind']=='data_snapshot')
        request=urllib.request.Request(args.data_url+'/snapshots/from-run',
            data=json.dumps({'run_id':run_id,'artifact_id':bundle['artifact_id']}).encode(),
            headers={'Content-Type':'application/json'})
        with opener.open(request,timeout=30) as response:
            write(folder/'import.json',json.load(response))
        with opener.open(args.data_url+'/snapshots/'+sid+'/timing-overview',timeout=30) as response:
            overview=json.load(response)
            write(folder/'timing-overview.json',overview)
        binding.update(snapshot_id=sid,export_run_id=run_id,
                       corrected_from_snapshot=binding['snapshot_id'])
        write(folder/'binding.json',binding)
        bindings[name]=binding
        print(name,sid,overview['status'],flush=True)
    write(args.output/'bindings.json',bindings)


if __name__=='__main__':
    main()
