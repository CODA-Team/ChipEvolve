"""Retain model command actions and flag capability/answer contamination.

This is a review aid, not a sandbox or proof from prompts. Actual bridge receipts
and all unclassified commands remain available for independent inspection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex


def executable_script(command):
    try:
        parts=shlex.split(command)
        script=parts[-1] if len(parts)>=3 and parts[-2] in ('-lc','-c') else command
    except ValueError:return command
    lines=script.splitlines();out=[];delimiter=None
    for line in lines:
        if delimiter:
            if line.strip()==delimiter:delimiter=None
            continue
        match=re.search(r'<<-?\s*[\'"]?([A-Za-z_][A-Za-z0-9_]*)[\'"]?',line)
        out.append(line)
        if match:delimiter=match.group(1)
    return '\n'.join(out)


def assigned_bridge(script, event_path):
    """Recognize only execution of this episode's exact, assigned bridge file."""
    try:
        parts = shlex.split(script)
    except ValueError:
        return False, script
    if len(parts) < 2 or not re.fullmatch(r'python(?:3(?:\.\d+)?)?', Path(parts[0]).name):
        return False, script
    candidate = Path(parts[1])
    if not candidate.is_absolute():
        candidate = event_path.parent / candidate
    expected = event_path.parent / 'action.py'
    if candidate.resolve() != expected.resolve() or not expected.is_file():
        return False, script
    # Remove just the executable token. Other arguments/commands remain scanned.
    parts[1] = '<assigned-bridge>'
    return True, shlex.join(parts)


def audit(root):
    episodes=[]
    for path in sorted(root.rglob('events.jsonl')):
        actions=[];changes=[];external_tools=[]
        for line in path.read_text().splitlines():
            try:event=json.loads(line)
            except ValueError:continue
            if event.get('type')!='item.completed':continue
            item=event.get('item',{})
            if item.get('type')=='command_execution':
                script=executable_script(item['command'])
                bridge,risk_script=assigned_bridge(script,path)
                suspicious=re.findall(r'\b(?:curl|wget|sqlite3|codex|ssh|requests|urlopen)\b|(?:private/|/bank/gold|state\.json|config\.json|traces/|evidence/)',risk_script)
                local_schema=bool(re.fullmatch(r'\s*(?:cat|head[^\n]*|sed[^\n]*) (?:decision-schema|host-schema|action-schema)\.json\s*',script))
                harmless=script.strip() in ('pwd','ls') or ('rg --files' in script and '/' not in script)
                actions.append({'command':item['command'],'executable_preview':script,
                   'exit_code':item.get('exit_code'),'risk_matches':suspicious,
                   'status':'requires_review' if suspicious or not (bridge or local_schema or harmless) else 'recognized_bridge_or_local_setup'})
            elif item.get('type')=='file_change':
                for change in item.get('changes',[]):
                    name=Path(change.get('path',''));resolved=name if name.is_absolute() else path.parent/name
                    allowed=resolved.resolve().parent==path.parent.resolve() and resolved.suffix=='.json'
                    allowed=allowed and resolved.name not in ('state.json','config.json','decision-schema.json','host-schema.json','action-schema.json')
                    changes.append({'path':str(name),'status':'local_decision_file' if allowed else 'requires_review'})
            elif item.get('type') in ('web_search','mcp_tool_call'):
                external_tools.append({'type':item['type'],'item':item,'status':'requires_review',
                                       'reason':'external tool was not assigned to the episode'})
        episodes.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                         'actions':actions,'file_changes':changes,'external_tools':external_tools,
                         'requires_review':any(a['status']=='requires_review' for a in actions+changes+external_tools)})
    return {'scope':str(root),'episodes':episodes,'episode_count':len(episodes),
            'flagged_episodes':sum(e['requires_review'] for e in episodes),
            'note':'Recognized commands are an audit aid; prompts alone are not evidence of isolation.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=audit(a.root)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('episode_count','flagged_episodes')}))


if __name__=='__main__':main()
