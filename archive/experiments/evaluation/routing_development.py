"""Development-only routing comparison. Sealed labels are never read here."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time

from query_agent.adapters.judgment.budgeted import BudgetedJudgment
from query_agent.adapters.judgment.stdio import StdioJudgmentClient
from query_agent.adapters.llm.budget import CostLedger


CLASSES = [
    {'id':'L0', 'description':'Single recorded fact, identity, count already indexed, resource/error or source lookup. No comparison, derivation or causal diagnosis.'},
    {'id':'L1', 'description':'Deterministic comparison, ranking, domain aggregation or geometry calculation over explicitly fixed records. No causal attribution or adaptive evidence investigation.'},
    {'id':'L2', 'description':'Causal diagnosis, competing explanations, verification, missing-detail investigation, targeted analysis or supported recovery from tool failure. Scope resolution can be its first step; missing detail alone does not make it unclear.'},
    {'id':'unclear', 'description':'The question explicitly leaves target identities, intended objective, units or conflicting scope unresolved so meaningful action first needs clarification. Takes precedence when explicit ambiguity prevents interpreting the request.'},
]


def rules(question):
    text = question.lower()
    unclear = ('not said which', 'do not know which', 'two snapshots and corners',
               'two different final', 'no target', 'same creation time',
               'unspecified', 'unclear whether', 'three designs', 'no coordinate unit')
    if any(phrase in text for phrase in unclear):
        return 'unclear'
    if re.search(r'\b(why|cause|caused|blaming|investigate|determine|justify)\b', text) or 'find evidence for and against' in text:
        return 'L2'
    if re.search(r'\b(compute|compare|rank|aggregate|union)\b', text) or 'additional buffers' in text or 'count all placed' in text:
        return 'L1'
    return 'L0'


def metrics(rows, labels, threshold=0.85, margin=0.5):
    matrix = {label:{other:0 for other in ('L0','L1','L2','unclear')} for label in ('L0','L1','L2','unclear')}
    automatic, errors, downgrade = [], [], []
    for row in rows:
        truth = labels[row['id']]
        predicted = row['classification']
        matrix[truth][predicted] += 1
        auto = row.get('top_probability',1) >= threshold and row.get('margin',1) >= margin
        if auto:
            automatic.append(row['id'])
        if truth != predicted:
            errors.append({'id':row['id'],'gold':truth,'prediction':predicted,'auto':auto})
        if auto and truth == 'L2' and predicted in ('L0','L1'):
            downgrade.append(row['id'])
    complex_count = sum(value=='L2' for value in labels.values())
    return {'confusion_matrix':matrix,'classified':len(rows),'denominator':len(labels),
            'accuracy':(len(rows)-len(errors))/len(labels),
            'auto_coverage':len(automatic)/len(labels),
            'complex_wrong_downgrade_rate':len(downgrade)/complex_count,
            'errors':errors,'complex_wrong_downgrades':downgrade}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ledger',type=Path,required=True)
    parser.add_argument('--pricing',type=Path,required=True)
    parser.add_argument('--launcher',default='/home/wjyuan/plugins/jev-decision/scripts/start-jev-mcp')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    items=[{'id':row['id'],'text':row['question']} for row in json.loads((args.dataset/'routing.json').read_text()) if row['split']=='development']
    labels=json.loads((args.dataset/'routing-development-labels.json').read_text())
    if len(items)!=40 or set(labels)!={row['id'] for row in items}:
        raise ValueError('routing development split must remain exactly 40 fixed questions')
    request={'items':items,'classes':CLASSES,
             'purpose':'Choose required EDA query workflow complexity, not whether a database currently contains evidence.',
             'context':'Snapshot/run names are opaque placeholders. Treat explicit fixed identities as fixed. Do not infer missing runtime data. L2 investigations may need scope resolution; explicit ambiguity is unclear. These levels describe work needed, not whether a cause is already proven.'}
    (args.output/'request.json').write_text(json.dumps(request,indent=2)+'\n')
    rule_rows=[{'id':item['id'],'classification':rules(item['text'])} for item in items]
    report={'split':'development','rule':metrics(rule_rows,labels),
            'dataset_sha256':hashlib.sha256((args.dataset/'routing.json').read_bytes()).hexdigest()}
    started=time.monotonic()
    with StdioJudgmentClient([args.launcher],timeout=120) as client:
        judged=BudgetedJudgment(client,ledger=CostLedger(args.ledger),trace_root=args.output/'traces',
                               pricing=json.loads(args.pricing.read_text()))
        response=judged.call('jev_classify',request)
        (args.output/'jev-result.json').write_text(json.dumps(response,indent=2)+'\n')
        report['jev_receipt']=judged.last_receipt
    rows=response['results']
    if {row['id'] for row in rows}!={item['id'] for item in items}:
        raise ValueError('JEV did not return every fixed development item')
    report['jev_default']=metrics(rows,labels)
    report['wall_seconds']=time.monotonic()-started
    candidates=[]
    for threshold in (0.6,0.7,0.8,0.85,0.9,0.95,0.98):
        for margin in (0.2,0.3,0.5,0.7,0.9):
            scored=metrics(rows,labels,threshold,margin)
            if scored['complex_wrong_downgrade_rate']==0:
                candidates.append({'threshold':threshold,'margin':margin,**scored})
    report['threshold_candidates']=candidates
    report['adoption']='not enabled by development classification alone; needs sealed and end-task outcomes'
    (args.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ('rule','jev_default','jev_receipt','adoption')}))


if __name__=='__main__':
    main()
