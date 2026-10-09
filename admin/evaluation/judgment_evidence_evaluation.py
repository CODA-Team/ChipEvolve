"""Development-only stability and native-evidence judgment measurements.

Requests and reference labels are persisted before JEV calls. The already opened
sealed routing set is not used for selection or further threshold tuning.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from query_agent.adapters.judgment.budgeted import BudgetedJudgment
from query_agent.adapters.judgment.investigation import CLASS_CATALOG, RouteRow, SupportRow
from query_agent.adapters.judgment.stdio import StdioJudgmentClient
from query_agent.adapters.llm.budget import CostLedger


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--sprint',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--launcher',default='/home/wjyuan/plugins/jev-decision/scripts/start-jev-mcp')
    a=p.parse_args();a.output.mkdir(exist_ok=False)
    development=json.loads((a.sprint/'evaluation-v1/public/routing-development-labels.json').read_text())
    routes=[r for r in json.loads((a.sprint/'evaluation-v1/public/routing.json').read_text())
            if r['split']=='development'][:12]
    items=[];labels={};pairs=[]
    for row in routes:
        variants=[row['question'],'Please address this EDA request: '+row['question']]
        ids=[]
        for j,text in enumerate(variants):
            rid=row['id']+'-variant-'+str(j);items.append({'id':rid,'text':text});ids.append(rid)
            labels[rid]=development[row['id']]
        pairs.append(ids)
    route_request={'items':items,'classes':CLASS_CATALOG,
                   'purpose':'EDA workflow depth, not current evidence availability.',
                   'context':'Fixed explicit scopes are fixed. Variants are correlated stability probes, not new independent tasks.'}
    refs=[];native=[]
    for alias in ('e00','e01','e03'):
        path=a.sprint/'controlled-development-1/private'/alias/'setup.json'
        raw=path.read_bytes();checks=json.loads(raw)['checks'];row=min(checks,key=lambda x:x['slack'])
        native.append({'id':alias,'text':json.dumps({'experiment':alias,'units':'s',
                        'report_selection':'stored native setup report, not exhaustive timing closure',
                        **{k:row[k] for k in ('startpoint','endpoint','slack','data_arrival_time','required_time')}})})
        refs.append({'path':str(path),'sha256':hashlib.sha256(raw).hexdigest()})
    claims=[
      ('e00 worst reported setup slack is -0.1616 ns.','verified'),
      ('e01 worst reported setup slack is -0.2116 ns.','verified'),
      ('e00 to e01 worsens the reported setup slack by 0.05 ns.','verified'),
      ('e00 and e01 have the same reported data arrival time.','verified'),
      ('e01 reports required time 0.27 ns.','contradicted'),
      ('e00 reports setup slack -0.1616 seconds.','contradicted'),
      ('e01 improves setup slack compared with e00.','contradicted'),
      ('e03 proves all setup paths have nonnegative slack.','contradicted'),
      ('The cause of e01 degradation is exclusively increased wire resistance.','unsupported'),
      ('e03 decreased design area by exactly 1 square micrometre.','unsupported'),
      ('e00 hold timing is closed on every endpoint.','unsupported'),
      ('The same reported worst endpoint in e00 and e01 is resp_msg[12].','verified')]
    verify_request={'claims':[r[0] for r in claims],'evidence':native,'auto_accept':.8,'subject_at':.5}
    candidates=[*native,
       {'id':'area','text':'Area reference absent; no area observation supplied.'},
       {'id':'unrelated','text':'OpenROAD is an open source physical design tool.'}]
    rank_requests=[
        {'query':'Compare e00 with e01 setup slack, data arrival and required time.', 'candidates':candidates},
        {'query':'Check whether e03 has negative worst reported setup slack.', 'candidates':candidates}]
    relevant=[['e00','e01'],['e03']]
    write(a.output/'inputs-and-reference.json',{'route_request':route_request,'route_labels':labels,
          'pairs':pairs,'verify_request':verify_request,'verdict_labels':[r[1] for r in claims],
          'rank_requests':rank_requests,'relevance_labels':relevant,'native_sources':refs,
          'policy':'frozen 0.85/margin0.5 routing policy remains unchanged; no sealed tuning'})
    output={};started=time.monotonic()
    with StdioJudgmentClient([a.launcher],timeout=120) as client:
        judged=BudgetedJudgment(client,ledger=CostLedger(a.sprint/'cost-ledger.json'),
                  trace_root=a.output/'traces',pricing=json.loads((a.sprint/'jev-pricing.json').read_text()))
        for name,tool,request in [('route','jev_classify',route_request),('verify','jev_verify',verify_request),
                                 *[('rank-'+str(i),'jev_rerank',r) for i,r in enumerate(rank_requests)]]:
            began=time.monotonic();response=judged.call(tool,request)
            output[name]={'response':response,'seconds':time.monotonic()-began,'receipt':judged.last_receipt}
            write(a.output/(name+'.json'),output[name])
    route_rows={r['id']:RouteRow.model_validate(r) for r in output['route']['response']['results']}
    verify_rows=[SupportRow.model_validate(r) for r in output['verify']['response']['results']]
    assert len(verify_rows)==len(claims)
    confusion={gold:{label:0 for label in ('verified','contradicted','unsupported')} for gold in ('verified','contradicted','unsupported')}
    for row,(_,gold) in zip(verify_rows,claims):confusion[gold][row.verdict]+=1
    ranks=[]
    for i,gold in enumerate(relevant):
        rows=output['rank-'+str(i)]['response']['ranked']
        assert {r['id'] for r in rows}=={c['id'] for c in candidates}
        top=[r['id'] for r in sorted(rows,key=lambda r:-r['relevance'])[:len(gold)]]
        ranks.append({'top':top,'reference':gold,'precision_at_reference_count':len(set(top)&set(gold))/len(gold)})
    summary={'scope':'development native evidence and correlated expression-stability probes',
       'route_accuracy':sum(r.classification==labels[rid] for rid,r in route_rows.items())/len(labels),
       'stable_pair_count':sum(route_rows[x].classification==route_rows[y].classification for x,y in pairs),
       'pair_count':len(pairs),'verification_correct':sum(row.verdict==gold for row,(_,gold) in zip(verify_rows,claims)),
       'verification_total':len(claims),'verification_confusion_matrix':confusion,'ranking':ranks,
       'seconds':time.monotonic()-started,'raw_probabilities_retained':True,
       'thresholds_retuned':False,'probability_concentration_is_not_accuracy':True,
       'default_adoption':'Still requires frozen end-task E versus D quality and cost/time results.'}
    write(a.output/'summary.json',summary);print(json.dumps(summary))


if __name__=='__main__':main()
