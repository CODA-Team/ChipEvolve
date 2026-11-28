"""A real Codex consumer proposes an allowed size and invokes the receiver CLI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

from query_agent.domain.handoff import HandoffPackage


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--timeout',type=int,default=300)
    args=parser.parse_args()
    package_path=args.package.resolve()
    payload=package_path.read_bytes()
    package=HandoffPackage.model_validate_json(payload)
    args.output.mkdir(parents=True,exist_ok=False)
    workspace=args.output.resolve()/'workspace'
    workspace.mkdir()
    receiver=args.output.resolve()/'receiver'
    receiver.mkdir()
    schema={'type':'object','additionalProperties':False,
            'properties':{'handoff_id':{'type':'string'},'accepted':{'type':'boolean'},
                          'physical_run_id':{'type':['string','null']},
                          'snapshot_id':{'type':['string','null']},'reason':{'type':'string'}},
            'required':['handoff_id','accepted','physical_run_id','snapshot_id','reason']}
    (workspace/'outcome-schema.json').write_text(json.dumps(schema))
    prefix=shlex.join([sys.executable,'-m','query_agent','receive-handoff',
        '--package',str(package_path),
        '--package-sha256',hashlib.sha256(payload).hexdigest(),
        '--receiver-output',str(receiver)])
    prompt=f'''You are the real Codex ECO task receiver. Consume the handed-off package below.
Use only this package and public interfaces. Never inspect private evaluation/oracle files, source code,
other cases or production services. The original package is outside your writable workspace.
Select one permitted buffer size adjustment with a short reason; write proposal.json with exactly
{{"changes":[{{"instance":"EXACT_ALLOWED_NAME","target_master":"EXACT_ALLOWED_MASTER"}}],"reason":"WHY"}}.
Execute this exact public receiver prefix followed by --proposal ABSOLUTE_PROPOSAL_PATH:
{prefix}
Do not alter clock/SDC/library/corner/RC inputs or submit an alternative direct native task.
The receiver validates the original package hashes/permissions, submits one candidate, re-evaluates
setup and hold in a new tool process, imports its new snapshot, and returns actual IDs. Wait for the
command to finish. You must actually invoke it; a proposed plan is not an accepted task.
No improvement is a valid result; do not claim success until a later independent QA review.
If rejected, explain the real error rather than guessing results. Return the requested outcome schema.
PACKAGE:
{package.model_dump_json(indent=2)}
'''
    (args.output/'prompt.txt').write_text(prompt)
    command=[shutil.which('codex'),'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check',
        '-C',str(workspace),'-s','workspace-write','--add-dir',str(receiver),
        '-m','gpt-6.1-sol','-c','model_reasoning_effort="medium"','-c','approval_policy="never"',
        '-c','sandbox_workspace_write.network_access=true','--json',
        '--output-schema',str(workspace/'outcome-schema.json'),
        '--output-last-message',str(args.output.resolve()/'model-outcome.json'),'-']
    (args.output/'invocation.json').write_text(json.dumps(command,indent=2))
    start=time.monotonic();timed_out=False
    with (args.output/'events.jsonl').open('w') as events,(args.output/'stderr.txt').open('w') as errors:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=events,stderr=errors,
                                 text=True,start_new_session=True)
        try:process.communicate(prompt,timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
    actions=[];usage={}
    for line in (args.output/'events.jsonl').read_text().splitlines():
        event=json.loads(line)
        if event.get('type')=='turn.completed':usage=event.get('usage',{})
        if event.get('type')=='item.completed' and event.get('item',{}).get('type')=='command_execution':actions.append(event['item'])
    actual=receiver/'receipt.json'
    receipt=json.loads(actual.read_text()) if actual.is_file() else None
    submitted=any('receive-handoff' in action['command'] and action.get('exit_code')==0 for action in actions)
    result={'handoff_id':package.handoff_id,'actual_receiver_completed':bool(receipt) and submitted,
            'receiver':receipt,'model':'gpt-6.1-sol','effort':'medium','usage':usage,
            'seconds':time.monotonic()-start,'timed_out':timed_out,'exit_code':process.returncode,
            'command_actions':actions,'cash_cost_usd':None,'billing':'Codex subscription',
            'outcome':'awaiting independent QA review, not improvement success'}
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='command_actions'},indent=2))
    return 0 if result['actual_receiver_completed'] else 1


if __name__=='__main__':raise SystemExit(main())
