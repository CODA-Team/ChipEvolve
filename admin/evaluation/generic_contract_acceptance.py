"""Deterministically verify failed answer attempts can retry within the budget."""
import argparse
import json
from pathlib import Path

import generic_agent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)

    class PreparedResponses:
        def __init__(self, **kwargs):
            self.calls = 0

        def set_timeout(self, seconds):
            assert seconds > 0

        def complete(self, prompt, schema):
            self.calls += 1
            if self.calls == 1:
                return schema(action='answer', answer_json='{broken')
            assert 'last_action_error' in prompt and 'Expecting property name' in prompt
            return schema(action='answer', answer_json='{"value":7}')

    generic_agent.DeepSeekFlashModel = PreparedResponses
    config = {
        'arm': 'C', 'max_seconds': 30, 'snapshots': [], 'data_url': 'http://127.0.0.1:1',
        'question': 'Prepared-response retry transport acceptance; no model or EDA call.',
        'answer_schema': {'type': 'object', 'properties': {'value': {'type': 'integer'}},
                          'required': ['value'], 'additionalProperties': False},
        'flash_config': str(args.output / 'unused-settings.json'),
        'cost_ledger': str(args.output / 'unused-ledger.json'),
    }
    generic_agent.run(config, args.output / 'episode', 'flash')
    state = json.loads((args.output / 'episode/state.json').read_text())
    checks = {
        'answered_after_rejected_inner_json': state['status'] == 'answered' and state['answer'] == {'value': 7},
        'rejection_uses_original_step_budget': state['steps_used'] == 2,
        'first_rejection_retained': (args.output / 'episode/proposal-rejections.jsonl').is_file(),
        'no_tool_calls': state['calls_used'] == 0,
    }
    result = {'kind': 'deterministic harness contract, not model quality evaluation',
              'checks': checks, 'passed': all(checks.values())}
    (args.output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    assert result['passed']


if __name__ == '__main__':
    main()
