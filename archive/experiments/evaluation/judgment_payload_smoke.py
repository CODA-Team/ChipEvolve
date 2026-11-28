"""Real bounded judgments, retaining exact payloads and paid-call receipts."""
import argparse,json
from pathlib import Path
from query_agent.adapters.judgment.stdio import StdioJudgmentClient
from query_agent.adapters.judgment.budgeted import BudgetedJudgment
from query_agent.adapters.llm.budget import CostLedger

p=argparse.ArgumentParser();p.add_argument('--sprint',type=Path,required=True);a=p.parse_args()
r=a.sprint/'judgment-payload-smoke-1';r.mkdir(exist_ok=False)
with StdioJudgmentClient(['/home/wjyuan/plugins/jev-decision/scripts/start-jev-mcp'],timeout=15) as c:
 j=BudgetedJudgment(c,ledger=CostLedger(a.sprint/'cost-ledger.json'),trace_root=r/'traces',pricing=json.loads((a.sprint/'jev-pricing.json').read_text()))
 for tool,request in [
  ('jev_rerank',{'query':'Which evidence discriminates changed required time from slower data arrival?', 'candidates':[{'id':'timing','text':'Matched setup path arrival 0.4316 ns in both runs, required 0.27 and 0.22 ns.'},{'id':'area','text':'Rounded design area reports 944 square micrometers in both runs.'},{'id':'clock','text':'Original SDC clocks have periods 0.25 ns and 0.20 ns respectively.'}]}),
  ('jev_verify',{'claims':['The matched path arrived 0.05 ns later in the candidate.','Required time decreased by 0.05 ns.','The same rounded area reports prove exact equal area.'], 'evidence':[{'id':'timing','text':'Matched setup path arrival 0.4316 ns in both runs, required 0.27 and 0.22 ns.'},{'id':'area','text':'Rounded design area reports 944 square micrometers in both runs; report precision is integer square micrometers.'}]})]:
  response=j.call(tool,request)
  (r/(tool+'.json')).write_text(json.dumps({'result':response,'receipt':j.last_receipt},indent=2)+'\n')
  print(tool,json.dumps(response),flush=True)
