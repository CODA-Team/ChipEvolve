"""Prepare reusable raw-file/SQLite baseline, without questions or answer gold.

Uses public snapshot metadata solely to locate immutable native inputs/reports.
Historical inventories are original flow TSV, never gold_native or DF tables.
The generic index has no per-question answer functions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import urllib.request

from openroad_platform_client import KernelClient, KernelError
from eda_toolkits.activity import native_activity
from direct_native import supervise


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024**2),b''):h.update(block)
    return h.hexdigest()


def index(directory):
    target=directory/'index.sqlite'
    if target.exists():raise ValueError('index already exists')
    db=sqlite3.connect(target)
    db.executescript('''
      CREATE TABLE instances(name TEXT PRIMARY KEY,master TEXT,is_macro INT,
        orientation TEXT,xmin REAL,ymin REAL,xmax REAL,ymax REAL,pin_count INT);
      CREATE TABLE nets(name TEXT PRIMARY KEY,signal_type TEXT,load_count INT);
      CREATE TABLE connections(net TEXT,pin TEXT,instance TEXT,role TEXT,is_macro INT);
      CREATE TABLE macro_pins(name TEXT,instance TEXT,local_name TEXT,direction TEXT,signal_type TEXT,net TEXT);
      CREATE TABLE design(dbu_per_micron INT,instance_count INT,net_count INT,port_count INT,
        die_xmin REAL,die_ymin REAL,die_xmax REAL,die_ymax REAL,
        core_xmin REAL,core_ymin REAL,core_xmax REAL,core_ymax REAL);
      CREATE TABLE clocks(name TEXT,period_seconds REAL,virtual INT,propagated INT);
      CREATE TABLE paths(check_kind TEXT,path_index INT,startpoint TEXT,endpoint TEXT,
        slack_seconds REAL,arrival_seconds REAL,required_seconds REAL,raw_json TEXT);
      CREATE TABLE points(check_kind TEXT,path_index INT,point_index INT,pin TEXT,
        instance TEXT,net TEXT,arrival_seconds REAL,slew_seconds REAL,load_farads REAL,raw_json TEXT);
      CREATE TABLE congestion(layer TEXT,x_index INT,y_index INT,x_dbu INT,y_dbu INT,capacity INT,usage INT,overflow INT);
      CREATE TABLE files(path TEXT PRIMARY KEY,sha256 TEXT,size_bytes INT);
    ''')
    files=list((directory/'raw').rglob('*'))
    for path in files:
        if path.is_file():db.execute('INSERT INTO files VALUES (?,?,?)',(str(path.relative_to(directory)),sha(path),path.stat().st_size))
    def table(suffix):
        matches=[f for f in files if f.name.endswith(suffix)]
        if len(matches)>1:raise ValueError('ambiguous original table '+suffix)
        return matches[0] if matches else None
    def lines(path):
        if path is not None:
            with path.open() as f:
                for line in f:
                    if line.strip():yield line.rstrip('\n').split('\t')
    dbu=1
    for r in lines(table('.design.tsv')):
        dbu=int(r[1]);db.execute('INSERT INTO design VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
          [dbu,*map(int,r[2:5]),*[int(v)/dbu for v in r[5:13]]])
    for r in lines(table('.instances.tsv')):
        db.execute('INSERT INTO instances VALUES (?,?,?,?,?,?,?,?,?)',
          [r[0].replace('\\',''),r[2],int(r[3]),r[4],*[int(v)/dbu for v in r[7:11]],int(r[11])])
    for r in lines(table('.nets.tsv')):
        name=r[0].replace('\\','');db.execute('INSERT INTO nets VALUES (?,?,?)',(name,r[2],int(r[3])))
        macros={v.replace('\\','') for value in r[6:8] for v in value.split('\x1e') if v}
        for role,column in [('driver',4),('load',5)]:
            for value in r[column].split('\x1e'):
                if not value:continue
                pin=value.replace('\\','');instance=pin.rsplit('/',1)[0] if '/' in pin else None
                db.execute('INSERT INTO connections VALUES (?,?,?,?,?)',(name,pin,instance,role,int(pin in macros)))
    for r in lines(table('.macro_pins.tsv')):
        db.execute('INSERT INTO macro_pins VALUES (?,?,?,?,?,?)',
          [r[0].replace('\\',''),r[2].replace('\\',''),r[3],r[4],r[5],r[6].replace('\\','')])
    for r in lines(table('.clocks.tsv')):
        db.execute('INSERT INTO clocks VALUES (?,?,?,?)',(r[0],float(r[1]),int(r[2]),int(r[3])))
    for r in lines(table('.congestion.tsv')):
        db.execute('INSERT INTO congestion VALUES (?,?,?,?,?,?,?,?)',[r[0],*[int(float(v)) for v in r[1:8]]])
    for path in files:
        if path.suffix!='.json' or 'timing' not in path.name:continue
        if 'original-flow' in path.parts and any(f.parent.name=='query-data' and f.name=='timing_report.json' for f in files):continue
        try:value=json.loads(path.read_text())
        except ValueError:continue
        if not isinstance(value,dict) or 'checks' not in value:continue
        check='hold' if ('hold' in path.name or '_min' in path.name) else 'setup'
        for i,row in enumerate(value['checks']):
            db.execute('INSERT INTO paths VALUES (?,?,?,?,?,?,?,?)',
             (check,i,row['startpoint'],row['endpoint'],row['slack'],row['data_arrival_time'],row['required_time'],json.dumps(row)))
            for j,point in enumerate(row.get('source_path',[])):
                db.execute('INSERT INTO points VALUES (?,?,?,?,?,?,?,?,?,?)',
                  (check,i,j,point.get('pin'),point.get('instance'),point.get('net'),point.get('arrival'),point.get('slew'),point.get('capacitance'),json.dumps(point)))
    db.executescript('''CREATE INDEX connections_net ON connections(net,role);
      CREATE INDEX macro_pin_instance ON macro_pins(instance,direction,signal_type);
      CREATE INDEX path_endpoints ON paths(check_kind,startpoint,endpoint);
      CREATE INDEX point_path ON points(check_kind,path_index,point_index);''')
    counts={name:db.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in
      ['instances','nets','connections','macro_pins','design','clocks','paths','points','congestion','files']}
    db.commit();db.close();return counts


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--snapshots',nargs='+',required=True);p.add_argument('--history',type=Path)
    p.add_argument('--execution-bindings',type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    kernels=[KernelClient('http://127.0.0.1:18700'),KernelClient('http://127.0.0.1:8700')]
    execution_bindings=json.loads(a.execution_bindings.read_text()) if a.execution_bindings else {}
    for sid in a.snapshots:
        directory=a.output/sid
        if (directory/'preparation-v2.json').exists():continue
        directory.mkdir(parents=True,exist_ok=True);started=time.monotonic()
        with opener.open('http://127.0.0.1:18924/snapshots/'+sid+'/summary?detail=full') as r:
            snapshot=json.load(r)['data']['snapshot']
        context=snapshot['run_summary'].get('timing_context',{});refs=[]
        for ref in snapshot.get('source_artifacts',[]):
            needed={context.get(k) for k in ('constraints','parasitics','rc_script','global_routing_segments')}
            needed.update(context.get('libraries',[]))
            if ref['category'] not in ('raw_design_database','raw_netlist','raw_library',
                'raw_constraints','raw_parasitics','raw_technology','raw_timing_report','analysis_report') and ref['logical_path'] not in needed:continue
            path=directory/'raw'/ref['logical_path'];path.parent.mkdir(parents=True,exist_ok=True)
            location=None
            for client in kernels:
                try:location=client.artifact_locator(ref['run_id'],ref['artifact_id']);break
                except KernelError as error:
                    if error.status!=404:raise
            if location is None:raise ValueError('unavailable raw artifact '+ref['artifact_id'])
            if not path.exists():shutil.copyfile(location['path'],path)
            if sha(path)!=ref['sha256']:raise ValueError('raw digest mismatch')
            refs.append({'path':str(path.relative_to(directory)),'sha256':ref['sha256'],
              'size_bytes':ref['size_bytes'],'origin':'original native artifact','artifact_id':ref['artifact_id']})
        if a.history and snapshot['design_id'] in ('ariane','mempool_group','nvdla_c'):
            stage=snapshot['stage'];source=a.history/'OpenROAD-flow-scripts/flow/reports/asap7'/snapshot['design_id']/'formal20261002'
            for path in sorted(source.glob(stage+'.*')):
                if path.suffix not in ('.tsv','.json','.rpt'):continue
                # Original flow reports, no gold_native or bank/gold is read.
                target=directory/'raw/original-flow'/path.name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,target)
                refs.append({'path':str(target.relative_to(directory)),'sha256':sha(target),
                  'size_bytes':target.stat().st_size,'origin':'original flow report'})
        execution_records=[]
        for rid in execution_bindings.get(sid,[]):
            for name,value in [('run',kernels[0].run(rid)),('logs',kernels[0].logs(rid,max_bytes=65536)),('resources',kernels[0].resources(rid))]:
                target=directory/'raw/failed-analysis'/rid/(name+'.json');target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(json.dumps(value,indent=2)+'\n')
                ref={'path':str(target.relative_to(directory)),'sha256':sha(target),'size_bytes':target.stat().st_size,'origin':'actual execution record'}
                refs.append(ref);execution_records.append(ref)
        native={'snapshot_id':sid,'design_id':snapshot['design_id'],'stage':snapshot['stage'],
          'revision_id':snapshot['revision_id'],'run_id':snapshot['run_id'],
          'executor':context.get('executor'),'corner':context.get('corner'),
          'ideal_clocks':context.get('ideal_clocks',False),'parasitic_mode':context.get('parasitic_mode'),
          'odb':next((ref['logical_path'] for ref in snapshot['source_artifacts'] if ref['category']=='raw_design_database'),None),
          'libraries':context.get('libraries',[]),'constraints':context.get('constraints'),
          'parasitics':context.get('parasitics'),'rc_script':context.get('rc_script'),
          'global_routing_segments':context.get('global_routing_segments'),
          'files':refs,'execution_records':execution_records}
        (directory/'native.json').write_text(json.dumps(native,indent=2)+'\n')
        inventory=directory/'raw/generated-inventory'
        inventory.mkdir(parents=True,exist_ok=True)
        if not (inventory/'inventory.design.tsv').exists():
            quote=lambda x:'{'+str(x)+'}'
            lines=['read_db '+quote('/work/raw/'+native['odb'])]
            for library in native['libraries']:
                if (directory/'raw'/library).exists():lines.append('read_liberty '+quote('/work/raw/'+library))
            if native['constraints'] and (directory/'raw'/native['constraints']).exists():
                lines.append('read_sdc '+quote('/work/raw/'+native['constraints']))
            lines.append('cd /work/raw/generated-inventory')
            lines.append((Path(__file__).parent/'native_inventory.tcl').read_text())
            script=directory/'inventory.tcl';script.write_text('\n'.join(lines)+'\n')
            command=[native['executor'],'-threads','8','-no_init','-no_splash','-exit','/work/inventory.tcl']
            env=dict(os.environ);env['EDA_ACTIVITY_LOCK']=str(a.output.parent/'eda-activity.lock')
            # Use configured public mirror, without changing the fixed native inputs.
            env['EDA_ORFS_IMAGE']='/home/wjyuan/projects/eda-toolchain/orfs-8e6ee7aac233da07.sif'
            began=time.monotonic()
            with native_activity(env) as active:
                process=supervise(command,folder=directory,env=active,seconds=180,output_path=directory/'inventory.log')
            (directory/'inventory-execution.json').write_text(json.dumps({'command':command,
              'seconds':time.monotonic()-began,**process},indent=2)+'\n')
            if process['exit_code'] or process['timed_out'] or process['exceeded']:raise RuntimeError('native baseline inventory failed; original log retained')
        # Rebuild a failed partial index; every original raw file stays available.
        if (directory/'index.sqlite').exists():(directory/'index.sqlite').unlink()
        counts=index(directory)
        receipt={'snapshot_id':sid,'seconds':time.monotonic()-started,'counts':counts,
          'index_sha256':sha(directory/'index.sqlite'),'native_sha256':sha(directory/'native.json'),
          'gold_accessed':False,'preparation_kind':'general raw-file index; no task-specific answers'}
        (directory/'preparation-v2.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
