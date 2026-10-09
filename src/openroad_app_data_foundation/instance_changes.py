"""Complete stored instance/master comparison, with explicit ambiguous identities."""
from collections import defaultdict

from .identity import snapshot_identity
from .queries import _limit, _offset, _page


def instance_changes(store,left_id,right_id,query):
    snapshots=[store.snapshot(sid) for sid in (left_id,right_id)]
    if snapshots[0]['design_id']!=snapshots[1]['design_id']:
        raise ValueError('instance comparison needs the same design')
    sides=[];coverage=[]
    for sid,snapshot in zip((left_id,right_id),snapshots):
        rows=store.connection_for(sid).execute("""SELECT record_id,
          json_extract(payload,'$.name') AS name,
          json_extract(payload,'$.attributes.master') AS master
          FROM records WHERE snapshot_id=? AND record_type='entities'
          AND json_extract(payload,'$.kind')='instance' ORDER BY name,record_id""",(sid,)).fetchall()
        grouped=defaultdict(list)
        for row in rows:grouped[row['name']].append(dict(row))
        sides.append(grouped)
        declared=snapshot.get('run_summary',{}).get('instance_count')
        coverage.append({'snapshot':snapshot_identity(snapshot),'indexed_instance_count':len(rows),
          'native_declared_instance_count':declared,
          'complete_native_inventory':isinstance(declared,int) and len(rows)==declared,
          'basis':'all indexed instance records, independent of response pages'})
    a,b=sides;names=sorted(set(a)|set(b),key=lambda name:'' if name is None else name)
    changes=[];ambiguous=[];missing_master=[];matched=0
    for name in names:
        left,right=a.get(name,[]),b.get(name,[])
        if name is None or len(left)>1 or len(right)>1:
            ambiguous.append(name);continue
        if left and right:
            if left[0]['master'] is None or right[0]['master'] is None:
                missing_master.append(name);continue
            matched+=1
            if left[0]['master']==right[0]['master']:continue
        changes.append({'name':name,'change':'master_changed' if left and right else 'removed' if left else 'added',
          'from':left[0] if left else None,'to':right[0] if right else None})
    limit,offset=_limit(query),_offset(query);page=changes[offset:offset+limit]
    complete=all(side['complete_native_inventory'] for side in coverage)
    return {'status':'available' if complete and not ambiguous and not missing_master else 'partial',
      'changes':page,**_page(len(changes),len(page),limit,offset),
      'master_changed_count':sum(row['change']=='master_changed' for row in changes),
      'added_indexed_count':sum(row['change']=='added' for row in changes),
      'removed_indexed_count':sum(row['change']=='removed' for row in changes),
      'matched_known_master_count':matched,'ambiguous_name_count':len(ambiguous),
      'ambiguous_names_preview':ambiguous[:20],'missing_master_count':len(missing_master),
      'missing_master_names_preview':missing_master[:20],'coverage':coverage,
      'matching_basis':'unique exact indexed instance name in each snapshot; snapshot-local object IDs are not assumed equal',
      'interpretation':'inventory facts only; master changes do not prove a timing cause, and absence from an incomplete inventory does not prove removal',
      'evidence':{label:[r for r in snapshot.get('source_artifacts',[]) if r.get('category')=='raw_design_database']
                  for label,snapshot in zip(('from','to'),snapshots)}}
