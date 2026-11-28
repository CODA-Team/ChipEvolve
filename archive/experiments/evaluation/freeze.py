"""Freeze all public tasks, independent reference identities and the planned denominator.

Gold is kept outside source and model workspaces. This script never queries DF
or calls a model. New diagnosis gold will come from controlled native experiments.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone


def digest(path):
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def freeze(args):
    out = args.output
    if (out / 'freeze.json').exists():
        raise SystemExit('Already frozen; use a new version directory, never overwrite a freeze.')
    private = out / 'private'
    private.mkdir(parents=True, exist_ok=True)
    os.chmod(private, 0o700)
    public = out / 'public'
    hashes = {}
    questions = []
    for design in ('ariane', 'mempool_group', 'nvdla_c'):
        source = args.history / f'bank/questions/{design}.json'
        items = json.loads(source.read_text())['questions']
        for q in items:
            if q['id'].startswith('formal-'):
                questions.append({**q, 'design': design, 'case_id': design + ':' + q['id'],
                    'dataset_group': design, 'reference_origin': 'historical independent native gold'})
        gold = args.history / f'bank/gold/{design}.json'
        (private / (design + '.gold.json')).write_bytes(gold.read_bytes())
        hashes[str(source)] = digest(source)
        hashes[str(gold)] = digest(gold)
    if len(questions) != 72:
        raise ValueError('Expected exactly 72 inherited formal facts')
    write(public / 'facts.json', questions)
    for path in sorted((args.history / 'gold_native').rglob('*')):
        if path.is_file():
            hashes[str(path)] = digest(path)
    for name in ('bank_data.py', 'build_bank.py'):
        path = args.history / 'scripts' / name
        hashes[str(path)] = digest(path)
    diagnosis = json.loads((Path(__file__).parent / 'diagnosis-specs.json').read_text())
    routes = json.loads((Path(__file__).parent / 'routing-specs.json').read_text())
    if len(diagnosis) != 30 or sum(c['split'] == 'development' for c in diagnosis) != 12:
        raise ValueError('Expected 12 development / 18 sealed diagnosis cases')
    if len(routes) != 100 or sum(c['split'] == 'development' for c in routes) != 40:
        raise ValueError('Expected 40 development / 60 sealed route cases')
    write(private / 'routing-labels.json', {c['id']:c['label'] for c in routes})
    write(public / 'routing.json', [{k:v for k,v in c.items() if k != 'label'} for c in routes])
    write(public / 'routing-development-labels.json', {c['id']:c['label'] for c in routes if c['split'] == 'development'})
    write(private / 'diagnosis-specs.json', diagnosis)
    write(public / 'diagnosis.json', [{k:v for k,v in c.items() if k not in ('mechanism','success_conditions','experiment_group')} for c in diagnosis])
    matrix = []
    models = ('codex', 'deepseek-flash')
    def episode(case, model, arm, repeat=0, ablation=None):
        matrix.append({'episode_id': f"{case['case_id']}:{model}:{arm}:r{repeat}:" + (ablation or 'full'),
            'case_id':case['case_id'], 'kind':case.get('kind','fact'), 'model':model,
            'arm':arm, 'repeat':repeat, 'ablation':ablation, 'status':'not_run',
            'wall_seconds':120 if case.get('kind','fact') == 'fact' else 180})
    for case in questions:
        for model in models:
            for arm in ('B','C'): episode(case,model,arm)
    sealed = [c for c in diagnosis if c['split'] == 'sealed']
    repeated = [c for c in sealed if c['repeat']]
    if len(repeated) != 6: raise ValueError('Exactly six diagnosis repeats must be preselected')
    for case in sealed:
        for model in models:
            for arm in ('B','C','D','E'): episode(case,model,arm)
    for case in repeated:
        for model in models:
            for arm in ('B','C','D','E'): episode(case,model,arm,repeat=1)
    for case in questions:
        if case['id'] in ('formal-01','formal-04','formal-09','formal-13'):
            for model in models: episode(case,model,'A')
    for case in repeated:
        for model in models:
            for ablation in ('no-skills','no-supplement'): episode(case,model,'D',ablation=ablation)
    if len(matrix) != 528 or len({e['episode_id'] for e in matrix}) != 528:
        raise ValueError('Formal denominator must remain 528 unique episodes')
    write(public / 'matrix.json',matrix)
    rules = json.loads((Path(__file__).parent / 'scoring-rules.json').read_text())
    write(public / 'scoring-rules.json',rules)
    for path in out.rglob('*.json'):
        hashes[str(path.relative_to(out))] = digest(path)
    write(out / 'freeze.json', {'version':'eda-30h-evaluation-v1',
        'frozen_at':datetime.now(timezone.utc).isoformat(), 'files':hashes,
        'facts':72,'diagnosis':{'development':12,'sealed':18},
        'routing':{'development':40,'sealed':60},'formal_episodes':528,
        'diagnosis_gold':'pending controlled native experiments; no product-parser-only gold',
        'independence':'Group inference by design and underlying experiment mechanism; repeats and paraphrases are not new independent samples.',
        'sealed_policy':'Gold is never supplied to prompts/skills; no threshold tuning after sealed scoring.',
        'receipt_policy':'Every predeclared episode is retained, including failed and missing runs.'})
    print(json.dumps({'output':str(out),'formal_episodes':len(matrix),'hashes':len(hashes)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--history',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    freeze(parser.parse_args())
