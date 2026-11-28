"""Exercise every new exam task through actual public interface queries."""
import json
import argparse
import re
import shutil
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlencode
from scoring import score

ROOT=Path('/home/wjyuan/projects/eda-ai-formal-20261002')
EVIDENCE=Path(__file__).resolve().parents[2]/'var/sprints/20261008-141846/deterministic-facts'
EVIDENCE.mkdir(parents=True,exist_ok=True)
BASE='http://127.0.0.1:18924'
STAGES=('input','placeopt','global_route')
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))


def box(value):
    return [value[k] for k in ('x_min','y_min','x_max','y_max')]


def union(boxes):
    return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]


def header(p):
    return {'startpoint':p['startpoint'],'endpoint':p['endpoint'],'slack_ns':p['slack']*1e9,
        'arrival_ns':p['data_arrival_time']*1e9,'required_ns':p['required_time']*1e9}


class Exam:
    def __init__(self,design):
        self.design=design
        self.questions={q['id']:q for q in json.loads((ROOT/f'bank/questions/{design}.json').read_text())['questions']}
        self.gold=json.loads((ROOT/f'bank/gold/{design}.json').read_text())['gold']
        self.questions={k:v for k,v in self.questions.items() if k.startswith('formal-')}
        self.trace=EVIDENCE/f'{design}.jsonl'
        self.trace.parent.mkdir(parents=True,exist_ok=True)
        self.calls=0;self.cache={};self.macros=None

    def request(self,path,payload=None):
        key=(path,json.dumps(payload,sort_keys=True))
        if payload is None and key in self.cache: return self.cache[key]
        req=urllib.request.Request(BASE+path,data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Content-Type':'application/json'})
        started=time.monotonic()
        with OPENER.open(req,timeout=185) as response: data=json.load(response)
        self.calls+=1
        result=data.get('data',data)
        with self.trace.open('a') as f:
            f.write(json.dumps({'path':path,'payload':payload,'seconds':time.monotonic()-started,'response':data})+'\n')
        if payload is None: self.cache[key]=result
        return result

    def get(self,route,stage='global_route',**params):
        base='/snapshots/'+self.design+'-formal20261002-'+stage+'-universal20261003/'
        if route.endswith('/pin-inventory'):
            identifier=route.split('/')[1]
            return self.request(base+'analyses/pin-inventory',{'name':urllib.parse.unquote(identifier),**params})
        if route=='timing-overview' and params.get('resolve')==1:
            return self.request(base+'analyses/timing-overview',params)
        if route.endswith('/engineering') and route.startswith('pins/'):
            return self.request(base+'analyses/pin-engineering',{'name':urllib.parse.unquote(route.split('/')[1]),**params})
        return self.request(base+route+('?' + urlencode(params) if params else ''))

    def objects(self,stage='global_route',**params):
        params={'limit':10000,**params};items=[];offset=0
        while True:
            result=self.get('objects',stage,offset=offset,**params)
            items+=result['objects']
            if result['next_offset'] is None: return items
            offset=result['next_offset']

    def macro_list(self):
        if self.macros is None:
            self.macros=self.objects(kind='instance',is_macro=1,sort='name',include_physical=1,
                fields='object_id,name,attributes.master,attributes.orientation,physical.bbox_um')
            for macro in self.macros:macro['name']=macro['name'].replace('\\','')
        return self.macros

    def instance(self,name,stage='global_route'):
        return self.get('instances/'+quote(name,safe='')+'/engineering',stage)['instance']

    def pins(self,name,stage='global_route',**params):
        return self.objects(stage,kind='pin',parent_instance=name,signal_type='SIGNAL',sort='name',
            fields='name,attributes.pin_name,attributes.direction,attributes.net_name',**params)

    def net(self,name,stage='global_route'):
        return self.get('nets/'+quote(name,safe='')+'/engineering',stage,traverse=1,limit=10000)

    def loads(self,name,stage='global_route',macros=False):
        return self.objects(stage,kind='instance',connected_to=name,net_role='load',include_physical=1,
            sort='name',**({'is_macro':1} if macros else {}))

    def counts(self,stage='global_route',region=None):
        params={'kind':'instance','group_by':'is_macro'}
        if region is not None:params.update(region=','.join(map(str,region)),region_units='um',intersection='positive_area')
        result=self.get('objects/statistics',stage,**params)
        groups={int(r['value']):r['count'] for r in result['groups']}
        return result['object_count'],groups.get(1,0),groups.get(0,0)

    def stage_counts(self,stage):
        instances,macros,_=self.counts(stage)
        nets=self.get('objects/statistics',stage,kind='net',group_by='kind')['object_count']
        return {'stage':stage,'instance_count':instances,'net_count':nets,'macro_count':macros}

    def path(self,stage='global_route',start=None,end=None,check='setup',fresh=False):
        if fresh:
            result=self.get('timing-overview',stage,resolve=1,check=check,startpoint=start,endpoint=end,
                limit=1,include_path_details=1,include_physical=1)
            if result['query_execution']['status']!='succeeded':
                raise RuntimeError('actual directed path analysis did not complete: '+str(result['query_execution']))
            return result['path_details'][0]
        params={'check':check,'sort':'slack','order':'worst','limit':1,'tie_break':'native_names'}
        if start: params['startpoint']=start
        if end: params['endpoint']=end
        rows=self.get('timing-paths',stage,**params)['timing_paths']
        if not rows:
            return self.path(stage,start,end,check,True)
        return self.get('timing-paths/'+quote(rows[0]['path_id'],safe='')+'/engineering',stage,limit=10000)

    def endpoints(self,qid):
        text=self.questions[qid]['question']
        match=re.search(r'(?:path (?:from )?|query for )(.+?) (?:->|to) (.+?)(?: at global_route|, report|; report|, sum|\)|\. This endpoint)',text)
        if not match: raise ValueError('cannot locate public question endpoints: '+qid)
        return match[1].lstrip('(').removeprefix('query for '),match[2]

    def region(self,qid):
        return json.loads(re.search(r'(?:region |bbox )(\[[^\]]+\])',self.questions[qid]['question'])[1])

    def answer(self,qid):
        if qid in ('formal-01','formal-17','dev-04'):
            if qid=='formal-01':
                c=self.stage_counts('global_route');return {k:v for k,v in c.items() if k!='stage'}|{'standard_cell_count':c['instance_count']-c['macro_count']}
            stages=[self.stage_counts(s) for s in (STAGES if qid=='formal-17' else STAGES[:2])]
            if qid=='formal-17':return {'stages':stages,'instance_change':stages[-1]['instance_count']-stages[0]['instance_count'],
                'net_change':stages[-1]['net_count']-stages[0]['net_count']}
            return {s['stage']:{'instances':s['instance_count'],'nets':s['net_count'],'macros':s['macro_count']} for s in stages}|{
                'instance_change':stages[-1]['instance_count']-stages[0]['instance_count']}
        macros=self.macro_list();m1=macros[0]['name'];m2=macros[-1]['name']
        if qid=='formal-02':
            b=box(self.get('summary',fields='run_summary.core_bbox')['run_summary']['core_bbox'])
            dbu=self.get('summary',fields='run_summary.dbu_per_micron')['run_summary']['dbu_per_micron'];b=[v/dbu for v in b]
            area=sum((x['physical']['bbox_um']['x_max']-x['physical']['bbox_um']['x_min'])*(x['physical']['bbox_um']['y_max']-x['physical']['bbox_um']['y_min']) for x in macros)
            return {'core_bbox_um':b,'macro_area_um2':area,'macro_area_percent':area*100/((b[2]-b[0])*(b[3]-b[1]))}
        if qid=='formal-03':
            clocks=self.get('constraints')['clocks']
            return {'clocks':[{'name':c['name'],'period_ns':c['period']*1e9,'virtual':bool(c['virtual'])} for c in sorted(clocks,key=lambda c:c['name'])]}
        if qid=='formal-04':
            return {delay:{k:header(self.path(check=check)['path'])[k] for k in ('startpoint','endpoint','slack_ns')} for delay,check in [('max','setup'),('min','hold')]}
        if qid in ('formal-05','dev-01'):
            m=m1 if qid=='formal-05' else re.search(r'For macro (.+?), report',self.questions[qid]['question'])[1]
            i=self.instance(m)
            if qid=='dev-01':return {'bbox_um':box(i['bbox_um']),'master':i['master'],'pin_count':i['signal_pin_count'],'net_count':i['distinct_signal_net_count']}
            return {'master':i['master'],'orientation':i['orientation'],'bbox_um':box(i['bbox_um']),
                'signal_pin_count':i['signal_pin_count'],'distinct_signal_net_count':i['distinct_signal_net_count']}
        if qid in ('formal-06','formal-16','dev-03'):
            if qid=='dev-03':
                m=re.search(r'Within macro (.+?) bbox',self.questions[qid]['question'])[1];region=box(self.instance(m)['bbox_um'])
            else:region=self.region(qid)
            _,mc,sc=self.counts(region=region);answer={'macro_count':mc,'standard_cell_count':sc}
            if qid=='formal-16':answer['macro_names']=sorted(x['name'].replace('\\','') for x in self.objects(kind='instance',is_macro=1,
                region=','.join(map(str,region)),region_units='um',intersection='positive_area'))
            if qid=='dev-03':answer['bbox_um']=region
            return answer
        if qid=='formal-07':
            pins=sorted(self.pins(m2,direction='INPUT'),key=lambda p:p['attributes']['pin_name'])[:3]
            return {'pins':[{'pin':p['attributes']['pin_name'],'net':p['attributes']['net_name'].replace('\\','')} for p in pins]}
        if qid=='formal-08':
            nets={p['attributes']['net_name'].replace('\\','') for p in self.pins(m2,direction='OUTPUT')}
            counts=[(n,self.net(n)['load_count']) for n in nets]
            ranked=sorted(counts,key=lambda x:(-x[1],x[0]))[:3]
            return {'nets':[{'name':n,'load_count':c,'receiving_macro_count':len(self.loads(n,macros=True))} for n,c in ranked]}
        if qid in ('formal-09','formal-14','formal-20'):
            pattern=r'(?:shared net |For net )(.+?), report'
            n=re.search(pattern,self.questions[qid]['question'])[1]
            if qid=='formal-20':
                answer={s:{'load_count':self.net(n,s)['load_count'],'drivers':self.net(n,s)['driver_traversal']['pin_names'],'macro_count':len(self.loads(n,s,True))} for s in ('input','global_route')}
                return answer|{'load_change':answer['global_route']['load_count']-answer['input']['load_count']}
            loads=self.loads(n);ms=sorted(i['name'].replace('\\','') for i in loads if i['attributes']['is_macro'])
            if qid=='formal-09':return {'load_count':self.net(n)['load_count'],'drivers':self.net(n)['driver_traversal']['pin_names'],
                'receiving_macro_count':len(ms),'first_three_macros':ms[:3],'last_three_macros':ms[-3:]}
            return {'instance_count':len(loads),'bbox_um':union([box(i['physical']['bbox_um']) for i in loads]),
                'macro_count':len(ms),'standard_cell_count':len(loads)-len(ms)}
        if qid=='formal-10':
            a,b=box(self.instance(m1)['bbox_um']),box(self.instance(m2)['bbox_um'])
            common=sorted({p['attributes']['net_name'].replace('\\','') for p in self.pins(m1)} & {p['attributes']['net_name'].replace('\\','') for p in self.pins(m2)})
            return {'distance_um':abs((a[0]+a[2]-b[0]-b[2])/2)+abs((a[1]+a[3]-b[1]-b[3])/2),'shared_net_count':len(common),'first_three_shared_nets':common[:3]}
        if qid in ('formal-11','formal-12','formal-13','dev-02'):
            start,end=self.endpoints(qid);p=self.path(start=start,end=end);points=p['points']
            if qid=='formal-12':return {'instance_count':p['instance_count'],'net_count':p['net_count'],'bbox_um':box(p['instance_bbox_union_um']),
                'macro_count':sum(bool(i['is_macro']) for i in p['instances'])}
            if qid=='dev-02':return header(p['path'])|{'instance_count':p['instance_count'],'net_count':p['net_count']}
            if qid=='formal-11':
                slew=max(points,key=lambda x:x.get('slew') if x.get('slew') is not None else float('-inf'))
                cap=max(points,key=lambda x:x.get('load') if x.get('load') is not None else float('-inf'))
                return header(p['path'])|{'max_slew_pin':slew['pin_name'],'max_slew_ns':slew['slew']*1e9,
                    'max_capacitance_pin':cap['pin_name'],'max_capacitance_ff':cap['load']*1e15}
            cell=wire=0;increments=[]
            for a,b in zip(points,points[1:]):
                d=(b['arrival']-a['arrival'])*1e9
                if a.get('instance_name') and a['instance_name']==b.get('instance_name'):cell+=d
                else:wire+=d
                increments.append((d,a['pin_name'],b['pin_name']))
            largest=max(enumerate(increments),key=lambda x:(x[1][0],-x[0]))[1]
            return {'cell_increment_ns':cell,'wire_increment_ns':wire,'largest_increment_ns':largest[0],'from_pin':largest[1],'to_pin':largest[2]}
        if qid=='formal-15':
            result=self.get('congestion',file=f'reports/asap7/{self.design}/formal20261002/global_route.congestion.tsv',
                layers=','.join(f'M{i}' for i in range(2,10)),limit=1)
            return {k:result['cells'][0][k] for k in ('layer','x_index','y_index','capacity','usage','overflow')}
        if qid=='formal-18':
            states=[]
            for stage in STAGES:
                i=self.instance(m1,stage)
                pins=self.get('instances/'+quote(m1,safe='')+'/pin-inventory',stage,limit=1)
                states.append({'stage':stage,'bbox_um':box(i['bbox_um']),'orientation':i['orientation'],
                    'signal_pin_count':pins['connected_pin_counts_by_native_type'].get('SIGNAL',0),
                    'signal_net_count':pins['distinct_net_counts_by_native_pin_type'].get('SIGNAL',0)})
            return {'stages':states,'unchanged':all({k:v for k,v in s.items() if k!='stage'}=={k:v for k,v in states[0].items() if k!='stage'} for s in states)}
        if qid in ('formal-19','formal-21','formal-23'):
            start,end=self.endpoints(qid)
            if qid=='formal-19':
                states=[{'stage':s,**header(self.path(s,start,end,fresh=True)['path'])} for s in STAGES]
                return {'stages':states,'slack_change_ns':states[-1]['slack_ns']-states[0]['slack_ns']}
            p=self.path(start=start,end=end,fresh=True)
            return header(p['path'])|{'data_pin_names':p['data_pin_names']}
        if qid=='formal-22':
            name=re.search(r'for macro pin (.+?), its parent',self.questions[qid]['question'])[1]
            result=self.get('pins/'+quote(name,safe='')+'/engineering')['pin']
            pin=self.objects(kind='pin',name=name)[0]
            parent=name.rsplit('/',1)[0]
            return {'x_um':result['position_um'][0],'y_um':result['position_um'][1],'orientation':self.instance(parent)['orientation'],
                'net':pin['attributes']['net_name'].replace('\\','')}
        if qid=='formal-24':
            macro=re.search(r'for macro (.+?) at global_route',self.questions[qid]['question'])[1]
            encoded='"'+macro.replace('\\','\\\\').replace('"','\\"').replace('$','\\$').replace('[','\\[').replace(']','\\]')+'"'
            data=self.request('/snapshots/'+self.design+'-formal20261002-global_route-universal20261003/native-queries',
                {'script':'report_power -instances [get_cells -quiet [list '+encoded+']] -format json','with_timing':True,'wait_seconds':120,'max_bytes':8192})
            if data['status']!='succeeded':raise RuntimeError('actual power query not complete')
            text=data['excerpt']['text'];begin=text.index('[\n{');end=text.index('\n]',begin)+2
            power=json.loads(text[begin:end].replace(r'\[','[').replace(r'\]',']'))
            return {k+'_w':power[0][k] for k in ('internal','switching','leakage','total')}
        raise ValueError('unimplemented actual task '+qid)

    def run(self,only=None,resume_passed=False):
        receipt_path=EVIDENCE/f'{self.design}.json'
        previous=json.loads(receipt_path.read_text())['results'] if receipt_path.exists() else []
        if receipt_path.exists():
            history=EVIDENCE/'history';history.mkdir(exist_ok=True)
            shutil.copyfile(receipt_path,history/f'{self.design}.interface_acceptance.{time.time_ns()}.json')
        retained={r['question']:r for r in previous if (only and r['question'] not in only) or (resume_passed and r['passed'])}
        results=[]
        for qid in self.questions:
            if qid in retained:
                results.append(retained[qid]);continue
            if only and qid not in only:continue
            started=time.monotonic();before=self.calls
            try:
                answer={'answer':self.answer(qid)}
                result={'question':qid,'answer':answer,**score(answer,self.gold[qid])}
            except Exception as error:
                result={'question':qid,'passed':False,'error':type(error).__name__+': '+str(error)}
            result.update(seconds=time.monotonic()-started,actual_query_count=self.calls-before)
            results.append(result)
            receipt={'design':self.design,'total':len(results),'passed':sum(r['passed'] for r in results),'results':results}
            receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
            print(self.design,qid,'PASS' if result['passed'] else 'FAIL',result.get('error',''),flush=True)
        complete={r['question'] for r in results}==set(self.questions)
        receipt={'design':self.design,'total':len(results),'expected_total':len(self.questions),
            'passed':sum(r['passed'] for r in results),'complete':complete,'results':results}
        receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
        return complete and all(r['passed'] for r in results)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--designs',nargs='+',default=['nvdla_c','ariane','mempool_group'])
    parser.add_argument('--only',nargs='+')
    parser.add_argument('--resume-passed',action='store_true')
    args=parser.parse_args()
    passed=[]
    for design in args.designs:
        passed.append(Exam(design).run(args.only,args.resume_passed))
    raise SystemExit(0 if all(passed) else 1)
