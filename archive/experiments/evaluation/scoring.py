"""Compare structured answers with the question bank's declared rules."""
import json
import math
import re

MISSING=object()


def resolve(value,path):
    for part in path.split('.'):
        if not isinstance(value,dict) or part not in value:return MISSING
        value=value[part]
    return value


def rule_at(rules,path):
    plain=re.sub(r'\[\d+\]','[]',path)
    return rules.get(path,rules.get(plain,{}))


def compare(actual,expected,path,rules,inherited=None):
    rule=rule_at(rules,path) or inherited or {}
    kind=rule.get('match_rule')
    if kind=='background':return []
    if actual is MISSING:return [path+': missing']
    if kind == 'enum_casefold':
        return [] if isinstance(actual, str) and actual.casefold() == str(expected).casefold() else [path+': enum mismatch']
    if kind == 'absent_name' and expected is None:
        return [] if actual is None or (isinstance(actual,str) and actual=='') else [path+': expected absent object name']
    if kind == 'report_cell' and expected is not None:
        cell = re.search(r'\(([A-Za-z_][A-Za-z_0-9]*)\)',str(expected))
        if cell is None:
            raise ValueError('reference report line has no cell name')
        found = isinstance(actual,str) and re.search(r'(?<![A-Za-z_0-9])'+re.escape(cell[1])+r'(?![A-Za-z_0-9])',actual)
        return [] if found else [path+': report cell mismatch']
    if kind == 'source_file':
        if not isinstance(actual, str) or '..' in actual.split('/'):
            return [path + ': valid source filename required']
        def canonical(value):
            value = value.replace('\\', '/').strip()
            if '/flow/' in value:
                return value.split('/flow/', 1)[1]
            if value.startswith('/data/'):
                return value[6:]
            return value.removeprefix('OpenROAD-flow-scripts/flow/').removeprefix('./')
        a, e = canonical(actual), canonical(str(expected))
        same = a == e or ('/' not in a and a == e.rsplit('/', 1)[-1]) or ('/' not in e and e == a.rsplit('/', 1)[-1])
        return [] if same else [path + ': different original source']
    if kind == 'unit_literal':
        normalize = lambda v: re.sub(r'[\s,"()]', '', str(v))
        return [] if normalize(actual) == normalize(expected) else [path + ': unit mismatch']
    if kind == 'quoted_text':
        return [] if isinstance(actual, str) and actual.replace('"', '') == str(expected).replace('"', '') else [path + ': text mismatch']
    if kind == 'clock_role':
        roles = lambda v: set(re.findall(r'\b(?:launch|capture)\b', str(v).lower()))
        return [] if roles(actual) == roles(expected) else [path + ': clock role mismatch']
    if kind=='keywords':
        text=json.dumps(actual,ensure_ascii=False).lower()
        return [path+': missing phrase '+word for word in rule['keywords'] if word.lower() not in text]
    if isinstance(expected,bool):
        return [] if isinstance(actual,bool) and actual==expected else [path+': boolean mismatch']
    if isinstance(expected,(int,float)):
        if not isinstance(actual,(int,float)) or isinstance(actual,bool) or not math.isfinite(actual):return [path+': numeric value required']
        atol=rule.get('atol',0);rtol=rule.get('rtol',1e-6)
        if path.endswith(('_ns','_ff')) and 'atol' not in rule_at(rules,path):
            atol=0.001 if path.endswith('_ns') else 0.01
        return [] if abs(actual-expected)<=max(atol,abs(expected)*rtol) else [f'{path}: {actual} != {expected}']
    if isinstance(expected,dict):
        if not isinstance(actual,dict):return [path+': object required']
        keys=rule.get('fields',list(expected))
        numeric_defaults={key:rule[key] for key in ('atol','rtol') if key in rule}
        return [failure for key in keys for failure in compare(actual.get(key,MISSING),expected[key],path+'.'+key,rules,numeric_defaults)]
    if isinstance(expected,list):
        if not isinstance(actual,list):return [path+': array required']
        if len(actual)!=len(expected) and rule.get('tie_protocol')!='allow_extras':return [f'{path}: list count {len(actual)} != {len(expected)}']
        if rule.get('order')=='any':
            unused=list(actual);errors=[]
            for i,value in enumerate(expected):
                matched=next((j for j,candidate in enumerate(unused) if not compare(candidate,value,f'{path}[{i}]',rules,rule)),None)
                if matched is None:errors.append(f'{path}[{i}]: missing expected member {str(value)[:120]}')
                else:unused.pop(matched)
            if unused and rule.get('tie_protocol')!='allow_extras':errors.append(path+': extra members')
            # Tied extras must match the declared boundary value, never arbitrary rows.
            if unused and rule.get('tie_protocol')=='allow_extras' and expected:
                numeric_key=next((k for k in ('slack_ns','fanout') if isinstance(expected[-1],dict) and k in expected[-1]),None)
                if numeric_key:
                    for row in unused:
                        errors.extend(compare(row.get(numeric_key,MISSING),expected[-1][numeric_key],path+'[].'+numeric_key,rules))
            return errors
        return [failure for i,value in enumerate(expected) for failure in compare(actual[i] if i<len(actual) else MISSING,value,f'{path}[{i}]',rules,rule)]
    if expected is None:return [] if actual is None else [path+': expected absent value']
    # Direction words are engineering enums, not case-sensitive object names.
    # INPUT and input state the same fact; INPUT and OUTPUT never do.
    if path.rsplit('.', 1)[-1] == 'direction' and expected in ('INPUT', 'OUTPUT', 'INOUT'):
        return [] if isinstance(actual, str) and actual.upper() == expected else [path+': direction mismatch']
    if isinstance(actual,str) and actual.replace('\\','')==str(expected).replace('\\',''):return []
    return [f'{path}: {str(actual)[:100]!r} != {str(expected)[:100]!r}']


def score(answer,entry):
    gold=entry['gold'];rules=entry.get('match_rules',{})
    checks=[]
    for key in entry['graded_keys']:
        errors=compare(resolve(answer,key),resolve(gold,key),key,rules)
        checks.append({'field':key,'passed':not errors,'errors':errors})
    return {'passed':all(c['passed'] for c in checks),'checks':checks}
