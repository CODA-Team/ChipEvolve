"""Exercise the installed QA provider against the current DF serving native historical data."""
import argparse
import json
import re
import time
from pathlib import Path

from eda_ai_client import EdaAiClient
from query_agent.adapters.data_foundation import DataFoundationProvider
from query_agent.domain.query import QueryContext, QuerySource
from query_agent.domain.design import DesignRegion

parser = argparse.ArgumentParser()
parser.add_argument('--data-url',required=True)
parser.add_argument('--evidence',type=Path,required=True)
args=parser.parse_args()
client=EdaAiClient(args.data_url,timeout=60)
provider=DataFoundationProvider(client)
rows=[]
questions=json.loads((args.evidence/'evaluation-v1/public/facts.json').read_text())
for design in ('ariane','mempool_group','nvdla_c'):
    sid=design+'-formal20261002-global_route-universal20261003'
    scope=client.resolve_scope(snapshot_id=sid,origin='all')['data']['snapshot']
    context=QueryContext(snapshot_id=sid,run_id=scope['run_id'],source=QuerySource.MANAGED_RUN)
    q=next(q for q in questions if q['design']==design and q['id']=='formal-05')
    name=re.search(r'For macro (.+?) at global_route',q['question'])[1]
    started=time.monotonic()
    try:
        instance=provider.get_instance(context,name)
        assert instance is not None
        location=provider.get_location(context,instance.ref)
        connections=provider.get_connections(context,instance.ref)
        q=next(q for q in questions if q['design']==design and q['id']=='formal-06')
        bounds=json.loads(re.search(r'In region (\[[^\]]+\]) um',q['question'])[1])
        region=provider.get_instances_in_region(context,DesignRegion(x_min=bounds[0],y_min=bounds[1],x_max=bounds[2],y_max=bounds[3],units='um'))
        result={'design':design,'status':'passed','snapshot_id':sid,'instance':instance.model_dump(mode='json'),
            'location':location.model_dump() if location else None,'relationship_count':len(connections),
            'region_count':len(region),'region_units':'um'}
    except Exception as exc:
        result={'design':design,'status':'failed','error':str(exc)}
    result['seconds']=time.monotonic()-started
    rows.append(result)
    print(json.dumps(result),flush=True)
args.evidence.joinpath('qa-real-physical-relations.json').write_text(json.dumps(rows,indent=2)+'\n')
raise SystemExit(0 if all(r['status']=='passed' for r in rows) else 1)
