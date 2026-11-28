"""Real OpenROAD session reuse, isolation, timeout and stopped-process cleanup."""
import argparse
import json
from pathlib import Path
import time

from direct_operations import DirectOperations
from direct_native import cleanup_owned, group_alive


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); a.output.mkdir(exist_ok=False)
    config=json.loads(a.config.read_text());config['arm']='B'
    ops=DirectOperations(config,a.output)
    sid=config['snapshots'][0]
    receipts=[]
    try:
        first=ops.native({'snapshot_id':sid,'script':'set baseline_sentinel 778; puts SESSION_ONE; report_worst_slack -max'},20)
        receipts.append(first)
        second=ops.native({'snapshot_id':sid,'script':'puts "SESSION_TWO $baseline_sentinel"; report_worst_slack -max'},20)
        receipts.append(second)
        assert first['exit_code']==second['exit_code']==0
        assert not first['session_reused'] and second['session_reused']
        assert first['session_identity']['pid']==second['session_identity']['pid']
        assert 'SESSION_TWO 778' in second['text']
        assert first['text'].split('SESSION_ONE',1)[1].strip()==second['text'].split('SESSION_TWO 778',1)[1].strip()
        started=time.monotonic();clean=cleanup_owned(a.output)
        assert clean and not group_alive(first['session_identity']['pid'])
        cleanup_seconds=time.monotonic()-started
        assert cleanup_seconds<5
        timeout_root=a.output/'timeout';timeout_root.mkdir()
        expired=DirectOperations(config,timeout_root).native({'snapshot_id':sid,'script':'puts BEFORE_TIMEOUT; after 15000'},1.5)
        assert expired['timed_out'] and not group_alive(expired['session_identity']['pid'])
        summary={'status':'passed','first':first,'second':second,'timeout':expired,
                 'suspended_cleanup_seconds':cleanup_seconds,'cleanup':clean,
                 'native_session_design_scope_fixed':True,'product_packages_used':False}
        (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps({'status':'passed','same_pid':True,'cleanup_seconds':cleanup_seconds,
                          'first_seconds':first['seconds'],'second_seconds':second['seconds']}))
    finally:
        cleanup_owned(a.output)
        cleanup_owned(a.output/'timeout')


if __name__=='__main__':main()
