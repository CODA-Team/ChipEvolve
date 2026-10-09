"""Explicit partial imports and real failed analyses; native history stays intact."""
import argparse,copy,json,time,urllib.request
from pathlib import Path

from eda_ai_client import EdaAiClient
from eda_toolkits.inputs import SnapshotExecutionClient,snapshot_inputs
from eda_toolkits.jobs import native_task


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sprint',type=Path,required=True)
    args=parser.parse_args();root=args.sprint;out=root/'availability-v1';out.mkdir(exist_ok=True)
    data=EdaAiClient('http://127.0.0.1:18924',timeout=30)
    execution=SnapshotExecutionClient('http://127.0.0.1:18700')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));bindings={}
    def clone(source,target,*,revision=None,remove=(),objects=True,paths=True,metrics_only=False):
        folder=out/target;folder.mkdir(exist_ok=True)
        if (folder/'binding.json').exists():
            return json.loads((folder/'binding.json').read_text())
        summary=data.read_query('/snapshots/'+source+'/summary',parameters={'detail':'full'})['data']
        snapshot=copy.deepcopy(summary['snapshot']);snapshot['snapshot_id']=target
        if revision:snapshot['revision_id']=revision
        removed=[r for r in snapshot.get('source_artifacts',[]) if r['category'] in remove]
        snapshot['source_artifacts']=[r for r in snapshot.get('source_artifacts',[]) if r['category'] not in remove]
        context=copy.deepcopy(summary['run_summary'])
        context['availability_fixture']={'parent_snapshot_id':source,
            'purpose':'explicit partial import; original run and files were not deleted',
            'removed_sources':[{'logical_path':r['logical_path'],'sha256':r['sha256']} for r in removed]}
        context.setdefault('timing_context',{}).pop('parent_snapshot_id',None)
        pack={'snapshot':snapshot,'run_summary':context,
              'coverage':{'source':'verified native export, explicit subset import',
                          'relations':'not imported','physical':'not imported',
                          'timing':'parsed subset' if paths else 'not imported'},
              'entities':[], 'timing_paths':[], 'observations':[]}
        if objects:
            response=data.read_query('/snapshots/'+source+'/objects',parameters={'limit':10000,'fields':'object_id,kind,name,parent_id,attributes'})
            if response['data']['next_offset'] is not None:raise ValueError('fixture cannot omit unseen object rows')
            pack['entities']=response['data']['objects']
        if paths or metrics_only:
            timing=data.read_query('/snapshots/'+source+'/timing-paths',parameters={'limit':200,'detail':'full'})['data']
            if timing['next_offset'] is not None:raise ValueError('fixture path copy must be complete over stored records')
            if paths:pack['timing_paths']=timing['timing_paths']
            elif metrics_only:
                samples=[row for row in timing['timing_paths'] if row.get('check')=='setup']
                if not samples:samples=[row for row in timing['timing_paths'] if row.get('check_type')=='setup']
                if not samples:raise ValueError('metrics subset needs original setup records')
                worst=min(samples,key=lambda x:x['slack'])
                pack['observations']=[{'observation_id':'metric:stored_worst_setup_slack',
                    'snapshot_id':target,'name':'stored_worst_setup_slack','kind':'metric',
                    'value':worst['slack'],'unit':'s','scope':{'stage':snapshot['stage']},
                    'evidence':worst.get('evidence',[]),
                    'detail':{'stored_reported_paths':len(samples),'coverage':'stored report sample, not full closure'}}]
        for key in ('entities','timing_paths','observations'):
            for row in pack[key]:row['snapshot_id']=target
        (folder/'pack.json').write_text(json.dumps(pack,indent=2)+'\n')
        req=urllib.request.Request(data.data_url+'/snapshots',data=json.dumps(pack).encode(),headers={'Content-Type':'application/json'})
        with opener.open(req,timeout=30) as r:result=json.load(r)
        (folder/'import.json').write_text(json.dumps(result,indent=2)+'\n')
        binding={'snapshot_id':target,'source_snapshot_id':source,'physical_run_id':snapshot['run_id'],
                 'fixture':'explicit subset of a verified native export','removed_sources':[r['logical_path'] for r in removed]}
        (folder/'binding.json').write_text(json.dumps(binding,indent=2)+'\n')
        return binding
    bindings['e08']=clone('physical-e01-v3-finish','development-e08-metrics',objects=False,paths=False,metrics_only=True,
                         remove=('raw_timing_report','raw_constraints','data_snapshot'))
    # Restore original SDC source for purposeful reanalysis, but not derived report sources.
    summary=data.read_query('/snapshots/physical-e01-v3-finish/summary',parameters={'detail':'full'})['data']
    pack=json.loads((out/'development-e08-metrics/pack.json').read_text())
    originals=[r for r in summary['snapshot']['source_artifacts'] if r['logical_path']=='inputs/6_final.sdc']
    if not originals:raise ValueError('original SDC unavailable')
    # The first import is retained as an explicit failed preparation; new immutable identity.
    pack['snapshot']['snapshot_id']='development-e08-metrics-fixed-inputs'
    pack['snapshot']['source_artifacts']+=originals
    for row in pack['observations']:row['snapshot_id']=pack['snapshot']['snapshot_id']
    if not (out/'e08-fixed-input-import.json').exists():
        req=urllib.request.Request(data.data_url+'/snapshots',data=json.dumps(pack).encode(),headers={'Content-Type':'application/json'})
        with opener.open(req,timeout=30) as r:result=json.load(r)
        (out/'e08-fixed-input-import.json').write_text(json.dumps(result,indent=2)+'\n')
    bindings['e08']['snapshot_id']=pack['snapshot']['snapshot_id']
    bindings['candidate-a']=clone('physical-e00-v3-finish','development-candidate-a',revision='candidate',objects=False)
    bindings['candidate-b']=clone('physical-e01-v3-finish','development-candidate-b',revision='candidate',objects=False)
    bindings['e09']=clone('physical-e00-v3-finish','development-e09-failure')
    bindings['e12']=clone('sealed-v2-e38-finish','development-e12-empty')
    bindings['e35']=clone('sealed-v1-e35-finish','sealed-e35-missing-sdc',remove=('raw_constraints',))
    bindings['e36']=clone('sealed-v1-e36-finish','sealed-e36-missing-library',remove=('raw_library',))
    bindings['trial-gcd']=clone('sealed-v1-e20-finish','sealed-trial-gcd',revision='trial',objects=False)
    bindings['trial-ariane']=clone('ariane-formal20261002-global_route-universal20261003','sealed-trial-ariane',revision='trial',objects=False,paths=False)
    for alias,sid in [('e09',bindings['e09']['snapshot_id']),('e37','sealed-v1-e37-finish')]:
        folder=out/alias;folder.mkdir(exist_ok=True)
        receipt=folder/'failure.json'
        if receipt.exists():record=json.loads(receipt.read_text())
        else:
            snapshot=data.read_query('/snapshots/'+sid+'/summary',parameters={'detail':'full'})['data']['snapshot']
            original,staged=snapshot_inputs(snapshot)
            task=native_task(snapshot,original,staged,'report_checks -this-option-does-not-exist\n')
            task['task_id']='availability-'+alias+'-real-failure-v1'
            task['labels'].update(run_type='analysis',analysis_of_run_id=snapshot['run_id'])
            (folder/'task.json').write_text(json.dumps(task,indent=2)+'\n')
            run_id=execution.submit(task,idempotency_key='availability-real-failure-'+alias)['run']['run_id']
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                run=execution.run(run_id)
                if run['status'] in ('succeeded','failed','timed_out','cancelled'):break
                time.sleep(.2)
            if run['status']!='failed':raise RuntimeError('actual invalid native command did not fail')
            record={'run':run,'logs':execution.logs(run_id,max_bytes=32768),'resources':execution.resources(run_id)}
            receipt.write_text(json.dumps(record,indent=2)+'\n')
        bindings.setdefault(alias,{'snapshot_id':sid})['failed_analysis_run_id']=record['run']['run_id']
    (out/'bindings.json').write_text(json.dumps(bindings,indent=2)+'\n')
    print(json.dumps(bindings,indent=2))


if __name__=='__main__':main()
