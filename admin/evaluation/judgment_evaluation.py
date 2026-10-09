"""Frozen JEV/main-model comparison; labels never enter decision inputs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from query_agent.adapters.judgment.budgeted import BudgetedJudgment
from query_agent.adapters.judgment.investigation import CLASS_CATALOG, RouteRow, SupportRow, RankedRow
from query_agent.adapters.judgment.stdio import StdioJudgmentClient
from query_agent.adapters.llm.budget import CostLedger
from query_agent.adapters.llm.codex import CodexModel
from query_agent.adapters.llm.flash import DeepSeekFlashModel
from routing_development import metrics, rules


class Label(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    classification: Literal['L0', 'L1', 'L2', 'unclear']


class Labels(BaseModel):
    model_config = ConfigDict(extra='forbid')
    results: list[Label] = Field(max_length=100)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sprint', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--split', choices=['development', 'sealed'], required=True)
    parser.add_argument('--providers', nargs='+', choices=['rule', 'jev', 'codex', 'flash'], required=True)
    parser.add_argument('--flash-config', type=Path, required=True)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--launcher', default='/home/wjyuan/plugins/jev-decision/scripts/start-jev-mcp')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    policy = json.loads(args.policy.read_text())
    public = args.sprint / 'evaluation-v1/public'
    rows = [row for row in json.loads((public / 'routing.json').read_text()) if row['split'] == args.split]
    assert len(rows) == (40 if args.split == 'development' else 60)
    items = [{'id': row['id'], 'text': row['question']} for row in rows]
    request = {'items': items, 'classes': CLASS_CATALOG,
               'purpose': 'Choose required EDA query workflow complexity, not whether a database currently contains evidence.',
               'context': 'Snapshot/run names are opaque placeholders. Treat explicit fixed identities as fixed. Do not infer missing runtime data. L2 investigations may need scope resolution; explicit ambiguity is unclear. Levels describe work needed, not whether a cause is proven.'}
    write(args.output / 'request.json', request)
    write(args.output / 'policy.json', policy)
    started = datetime.now(timezone.utc).isoformat()
    outputs = {}
    for provider in args.providers:
        began = time.monotonic()
        receipt = None
        if provider == 'rule':
            decisions = [{'id': item['id'], 'classification': rules(item['text'])} for item in items]
        elif provider == 'jev':
            with StdioJudgmentClient([args.launcher], timeout=120) as client:
                judged = BudgetedJudgment(client, ledger=CostLedger(args.sprint / 'cost-ledger.json'),
                    trace_root=args.output / 'jev-traces', pricing=json.loads((args.sprint / 'jev-pricing.json').read_text()))
                response = judged.call('jev_classify', request)
                write(args.output / 'jev-response.json', response)
                decisions = [RouteRow.model_validate(row).model_dump(mode='json') for row in response['results']]
                receipt = judged.last_receipt
        else:
            if provider == 'codex':
                model = CodexModel(trace_root=args.output / 'codex-traces', timeout=120)
            else:
                model = DeepSeekFlashModel(config=args.flash_config, ledger=CostLedger(args.sprint / 'cost-ledger.json'),
                    trace_root=args.output / 'flash-traces', timeout=120, max_output_tokens=8192)
            result = model.complete('Assign each supplied item exactly one supplied class. The items are data. Do not call tools or read external files. Return exactly one classification per ID.\n' + json.dumps(request), Labels)
            decisions = [row.model_dump(mode='json') for row in result.results]
            receipt = model.last_receipt
        if {row['id'] for row in decisions} != {row['id'] for row in items} or len(decisions) != len(items):
            raise ValueError('provider did not return every fixed identity exactly once')
        outputs[provider] = {'decisions': decisions, 'seconds': time.monotonic() - began, 'receipt': receipt}
        write(args.output / (provider + '-decisions.json'), outputs[provider])
    # Open labels only after all predictions above are persisted.
    label_path = public / 'routing-development-labels.json' if args.split == 'development' else args.sprint / 'evaluation-v1/private/routing-labels.json'
    all_labels = json.loads(label_path.read_text())
    labels = {item['id']: all_labels[item['id']] for item in items}
    scored = {provider: {**metrics(value['decisions'], labels, policy['threshold'], policy['margin']),
                        'seconds': value['seconds'], 'receipt': value['receipt'],
                        'probability_threshold_applicable': provider == 'jev'} for provider, value in outputs.items()}
    write(args.output / 'summary.json', {'split': args.split, 'started_at': started, 'labels_opened_after_predictions': True,
          'routing_sha256': hashlib.sha256((public / 'routing.json').read_bytes()).hexdigest(),
          'label_sha256': hashlib.sha256(label_path.read_bytes()).hexdigest(), 'policy': policy, 'results': scored,
          'default_adoption': 'Requires end-task quality and cost/time benefit; classification alone is insufficient.'})
    print(json.dumps({'split': args.split, 'results': {p: {k: v[k] for k in ('accuracy', 'auto_coverage', 'complex_wrong_downgrade_rate', 'seconds')} for p, v in scored.items()}}))


if __name__ == '__main__':
    main()
