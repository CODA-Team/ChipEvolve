"""Strong direct baseline: scoped raw files, generic SQL and native OpenROAD.

No Data Foundation/parser/query-workflow imports. The index was prepared from
native bytes, and every query retains a receipt and source manifest identity.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time

from direct_native import supervise
from direct_session import run_session


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def quote(text):
    return '"'+str(text).replace('\\','\\\\').replace('"','\\"').replace('$','\\$').replace('[','\\[').replace(']','\\]')+'"'


class DirectOperations:
    def __init__(self,config,episode):
        self.config=config;self.episode=Path(episode)
        self.root=Path(config['baseline_root']).resolve()
        self.scopes=config['snapshots']

    def dataset(self,snapshot):
        if snapshot not in self.scopes:raise ValueError('snapshot outside fixed scope')
        directory=(self.root/snapshot).resolve()
        if directory.parent!=self.root:raise ValueError('invalid dataset path')
        return directory,json.loads((directory/'native.json').read_text())

    def describe(self):
        result=[]
        for sid in self.scopes:
            directory,info=self.dataset(sid)
            dataset={'snapshot_id':sid,'native':info}
            if self.config['arm']=='B':
                with sqlite3.connect('file:'+str(directory/'index.sqlite')+'?mode=ro',uri=True) as db:
                    schema=[row[0] for row in db.execute("SELECT sql FROM sqlite_master WHERE type='table'")]
                dataset.update(sql_alias='s'+str(len(result)),sql_tables=schema if len(result)==0 else 'same schema as s0')
            result.append(dataset)
        return {'datasets':result,'native_time_unit':'native JSON fields are seconds; convert to ns explicitly',
          'operations':['file','sql','native'] if self.config['arm']=='B' else ['file','native'],
          'file_protocol':'snapshot_id,path (relative raw/... or native.json),offset,max_bytes; newline/regex filters are optional.',
          'sql_protocol':'Read-only SQLite SQL; fixed scopes pre-attached as s0,s1,...; LIMIT and JSON1 supported. No task-specific answer helpers.',
          'native_session': 'B reuses fixed-input OpenROAD processes, suspended between queries under the global EDA lease; A loads per call.',
          'native_protocol':'snapshot_id,script,with_timing(default true); original inputs loaded first. Script contains only bounded queries, no mutations or external commands. Log/output are retained. Get report_checks JSON with -format json -digits 9; exact pin/port resolution is your responsibility.'}

    def perform(self,operation,remaining):
        kind=operation['kind']
        if kind=='file':return self.file(operation)
        if kind=='sql':
            if self.config['arm']!='B':raise ValueError('arm A has no prepared SQL helper')
            return self.sql(operation,remaining)
        if kind=='native':return self.native(operation,remaining)
        raise ValueError('unknown direct operation')

    def file(self,operation):
        directory,_=self.dataset(operation['snapshot_id'])
        relative=operation['path'];path=(directory/relative).resolve()
        if directory not in path.parents or not (relative.startswith('raw/') or relative=='native.json'):
            raise ValueError('file must be a scoped original raw input/report')
        limit=int(operation.get('max_bytes',8192));offset=int(operation.get('offset',0))
        if not 1<=limit<=65536 or offset<0:raise ValueError('invalid file page')
        expression=operation.get('regex')
        if expression:
            pattern=re.compile(expression);matches=[];size=0
            with path.open(errors='replace') as stream:
                for line_number,line in enumerate(stream,1):
                    if not pattern.search(line):continue
                    if size+len(line.encode())>limit:break
                    matches.append({'line':line_number,'text':line.rstrip('\n')});size+=len(line.encode())
            return {'path':relative,'sha256':digest(path),'matches':matches,
                    'coverage':'bounded regex matches, not exhaustive unless independently counted'}
        with path.open('rb') as stream:stream.seek(offset);raw=stream.read(limit)
        return {'path':relative,'sha256':digest(path),'size_bytes':path.stat().st_size,
          'offset':offset,'next_offset':offset+len(raw) if offset+len(raw)<path.stat().st_size else None,
          'text':raw.decode(errors='replace')}

    def sql(self,operation,remaining):
        statement=operation['sql'];db=sqlite3.connect(':memory:',uri=True)
        for index,sid in enumerate(self.scopes):
            directory,_=self.dataset(sid)
            db.execute('ATTACH DATABASE ? AS s'+str(index),('file:'+str(directory/'index.sqlite')+'?mode=ro',))
        db.execute('PRAGMA query_only=ON')
        # Deny file attachment and all writes after the fixed databases are attached.
        forbidden={sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH,sqlite3.SQLITE_PRAGMA,
          sqlite3.SQLITE_INSERT,sqlite3.SQLITE_UPDATE,sqlite3.SQLITE_DELETE,sqlite3.SQLITE_CREATE_TABLE}
        db.set_authorizer(lambda action,*args:sqlite3.SQLITE_DENY if action in forbidden else sqlite3.SQLITE_OK)
        deadline=time.monotonic()+min(15,remaining)
        db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
        db.row_factory=sqlite3.Row
        try:
            cursor=db.execute(statement);rows=cursor.fetchmany(1001)
            return {'sql':statement,'rows':[dict(row) for row in rows[:1000]],
              'truncated':len(rows)>1000,'source_indices':[{'snapshot_id':sid,
                'sha256':json.loads((self.root/sid/'preparation-v2.json').read_text())['index_sha256']} for sid in self.scopes]}
        except sqlite3.DatabaseError as error:
            raise ValueError('native SQL query failed: '+str(error)) from error
        finally:db.close()

    def native(self,operation,remaining):
        directory,info=self.dataset(operation['snapshot_id'])
        script=operation['script']
        if re.search(r'\b(exec|socket|load|source|read_\w+|write_\w+|resize_cell|swapMaster|create_clock|set_clock\w*|set_output_delay|set_input_delay|remove_\w+|delete_\w+)\b',script):
            raise ValueError('native baseline permits queries with fixed inputs only')
        persistent=self.config['arm']=='B'
        session_key=hashlib.sha256((operation['snapshot_id']+str(operation.get('with_timing',True))).encode()).hexdigest()[:24]
        folder=self.episode/'native'/('session-'+session_key if persistent else str(time.time_ns()))
        folder.mkdir(parents=True,exist_ok=persistent)
        raw=folder/'raw';raw.mkdir(exist_ok=persistent)
        fixed=[info['odb'],*info['libraries'],info['constraints'],info['parasitics'],
               info['rc_script'],info['global_routing_segments']]
        for name in fixed:
            if name and (directory/'raw'/name).exists():
                target=raw/name;target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists():shutil.copyfile(directory/'raw'/name,target)
        lines=['read_db '+quote('/work/raw/'+info['odb'])]
        if operation.get('with_timing',True):
            for library in info['libraries']:
                if not (raw/library).is_file():raise ValueError('missing fixed library '+library)
                lines.append('read_liberty '+quote('/work/raw/'+library))
            if not info['constraints'] or not (raw/info['constraints']).is_file():raise ValueError('missing fixed SDC')
            lines.append('read_sdc '+quote('/work/raw/'+info['constraints']))
            if info.get('ideal_clocks'):lines.append('set_ideal_network [all_clocks]')
            for name,command in [('rc_script','source'),('parasitics','read_spef'),('global_routing_segments','read_global_route_segments')]:
                if info.get(name):
                    if not (raw/info[name]).exists():raise ValueError('missing fixed '+name)
                    lines.append(command+' '+quote('/work/raw/'+info[name]))
            if info['parasitic_mode'] in ('placement','global_routing'):
                lines.append('estimate_parasitics -'+info['parasitic_mode'])
        command=[info['executor'],'-threads','8','-no_init','-no_splash','-exit',
                 '/work/session.tcl' if persistent else '/work/query.tcl']
        if not persistent:
            (folder/'query.tcl').write_text('\n'.join(lines+[script])+'\n')
        env=dict(os.environ,EDA_ORFS_IMAGE=self.config['orfs_image'])
        lease=Path(self.config['activity_lock']);lease.parent.mkdir(parents=True,exist_ok=True)
        started=time.monotonic()
        with lease.open('a') as lock:
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.monotonic()-started>=remaining:raise TimeoutError('native lease wait used task deadline')
                    time.sleep(.05)
            available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
            if available<16*1024**3:raise RuntimeError('new EDA paused: less than 16 GiB available')
            seconds=max(.1,remaining-(time.monotonic()-started))
            outcome=run_session(folder,command=command,lines=lines,script=script,env=env,seconds=seconds) if persistent else supervise(command,folder=folder,env=env,seconds=seconds)
        receipt={'command':command,'seconds':time.monotonic()-started,**outcome,
                 'snapshot_id':info['snapshot_id'],'native_config_sha256':digest(directory/'native.json')}
        output_path=Path(outcome.get('output_path',folder/'output.txt'))
        receipt_path=output_path.with_suffix('.receipt.json') if persistent else folder/'receipt.json'
        receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
        output=output_path.read_text();limit=int(operation.get('max_bytes',16000))
        return {**receipt,'source':str(output_path),'sha256':digest(output_path),
                'text':output[:limit],'truncated':len(output)>limit}
