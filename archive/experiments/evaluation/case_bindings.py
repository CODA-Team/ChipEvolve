"""Bind frozen public questions to real immutable inputs without opening any gold."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
 p=argparse.ArgumentParser();p.add_argument('--sprint',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 a.output.mkdir(exist_ok=False);avail=json.loads((a.sprint/'availability-v1/bindings.json').read_text())
 public=a.sprint/'evaluation-v1/public';questions=json.loads((public/'diagnosis.json').read_text());facts=json.loads((public/'facts.json').read_text())
 dev=lambda n:'physical-'+n+'-v3-finish';sealed=lambda n:'sealed-v1-'+n+'-finish'
 pairs={1:[dev('e00'),dev('e01')],2:[dev('e00'),dev('e02')],3:[dev('e00'),dev('e03')],4:[dev('e00'),dev('e04')],5:[dev('e00'),dev('e05')],6:[dev('e06'),dev('e07')],7:[dev('e00'),avail['e08']['snapshot_id']],8:[avail['candidate-a']['snapshot_id'],avail['candidate-b']['snapshot_id']],9:[avail['e09']['snapshot_id']],10:[dev('e00'),dev('e10')],11:[dev('e00'),dev('e11')],12:[avail['e12']['snapshot_id']],
 13:[sealed('e20'),sealed('e21')],14:[sealed('e20'),sealed('e22')],15:[sealed('e23'),sealed('e24')],16:[sealed('e20'),sealed('e25')],17:[sealed('e27'),sealed('e26')],18:[sealed('e20'),sealed('e28')],19:[sealed('e29'),sealed('e30')],20:[sealed('e31'),sealed('e32')],21:[sealed('e33'),sealed('e34')],22:[avail['trial-gcd']['snapshot_id'],avail['trial-ariane']['snapshot_id']],23:[avail['e35']['snapshot_id']],24:[avail['e36']['snapshot_id']],25:[avail['e37']['snapshot_id']],26:['sealed-v2-e38-finish'],27:[sealed('e40'),sealed('e39')],28:[sealed('e42'),sealed('e41')],29:[sealed('e20'),sealed('e43')],30:[sealed('e44')]}
 hints={5:'Path of interest: endpoint resp_msg[12]; compare the same endpoint.',12:'The original directed report used to_pin=clk. Inspect its actual selection and constraints.',20:'Path of interest: endpoint resp_val; retrieve this endpoint under the original conditions.',26:'The original directed report used to_pin=clk. Inspect selection and constraints.',30:'Only place178 may be resized, from original BUF_X1 to BUF_X2 or BUF_X4. Keep clocks, SDC, libraries, parasitics and evaluation conditions fixed. Prepare an explicit task package; receiver acceptance or repair is not assumed.'}
 failures={9:avail['e09']['failed_analysis_run_id'],25:avail['e37']['failed_analysis_run_id']}
 rows=[]
 for question in questions:
  n=int(question['id'].split('-')[1]);row={'case_id':question['case_id'],'snapshots':pairs[n],'public_context':hints.get(n,''),'allowed_execution_ids':[failures[n]] if n in failures else [],'scope_selectors':None}
  if n in failures:row['public_context']+=' The failed native analysis is '+failures[n]+'. Inspect its actual failure and logs.'
  if n==8:row['scope_selectors']=[{'design_id':'gcd','revision_id':'candidate','stage':'finish'}]
  if n==22:row['scope_selectors']=[{'revision_id':'trial'}]
  if n==30:row['handoff_permissions']={pairs[n][0]:[{'instance':'place178','original_master':'BUF_X1','allowed_masters':['BUF_X2','BUF_X4']}]}
  rows.append(row)
 fact_rows=[]
 for question in facts:
  design=question['design'];fact_rows.append({'case_id':question['case_id'],'snapshots':[design+'-formal20261002-'+stage+'-universal20261003' for stage in ['input','placeopt','global_route']]})
 for name,value in [('diagnosis-bindings.json',rows),('fact-bindings.json',fact_rows),('execution-bindings.json',{pairs[n][-1]:[rid] for n,rid in failures.items()})]:
  (a.output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 (a.output/'manifest.json').write_text(json.dumps({'gold_opened':False,'original_freeze_retained':True,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.output.glob('*.json')},'note':'Public input identities, endpoint requests and permissions only; no outcomes or mechanisms.'},indent=2)+'\n')
 print(json.dumps({'diagnosis':len(rows),'facts':len(fact_rows),'output':str(a.output)}))


if __name__=='__main__':main()
