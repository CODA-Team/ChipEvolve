"""No paid calls: budget accounting and full saved-output continuation."""
import json
import pytest
from qualification.v3.benchmark_tool import output_page
from qualification.v3.deepseek_provider import Ledger, BudgetExhausted, usage_cost, PEAK
from qualification.v3.answer_scoring import score


def test_actual_zero_tool_use_has_no_percentage_denominator():
    from qualification.v3.paired_results import summarize
    rows = [{'episode': 'round-chip-q-' + arm, 'design': 'chip', 'question_id': 'q', 'arm': arm,
             'usage_known': True, 'invocation_started': True, 'passed': True, 'is_complex': False,
             'status': 'answered', 'total_tokens': 100, 'seconds': 1, 'tool_calls': 0, 'tool_bytes': 0}
            for arm in ('interface', 'raw')]
    result = summarize(rows)
    assert result['total_tokens']['reduction_pct'] == 0
    assert result['tool_calls']['reduction_pct'] is None and result['tool_bytes']['reduction_pct'] is None
    assert result['tool_calls']['raw'] == result['tool_calls']['interface'] == 0


def test_connection_failures_stay_in_results_without_fabricating_usage_comparison():
    from qualification.v3.paired_results import summarize
    rows = [{'episode': 'round-chip-q-' + arm, 'design': 'chip', 'question_id': 'q', 'arm': arm,
             'usage_known': False, 'invocation_started': True, 'passed': False, 'is_complex': True,
             'status': 'provider_failed', 'total_tokens': 0, 'seconds': 2, 'tool_calls': 0, 'tool_bytes': 0}
            for arm in ('interface', 'raw')]
    result = summarize(rows)
    assert result['known_usage_pairs'] == 0 and result['excluded_unknown_usage_pairs'] == 1
    assert result['arms']['interface']['statuses'] == {'provider_failed': 1}
    assert result['arms']['raw']['passed'] == 0 and len(result['failures']) == 2
    for name in ('total_tokens', 'paired_seconds', 'tool_calls', 'tool_bytes'):
        assert result[name]['interface'] is result[name]['raw'] is result[name]['reduction_pct'] is None
    assert result['all_episode_seconds_including_failures']['raw'] == 2
    with pytest.raises(ValueError, match='both actual episode records'):
        summarize(rows[:1])


def test_engineering_unit_tolerances_survive_generic_container_numeric_defaults():
    entry = {'gold': {'answer': {'stages': [{'slack_ns': -0.4053}], 'max_capacitance_ff': 60.93}},
             'graded_keys': ['answer'], 'match_rules': {'answer': {'atol': 1e-6, 'rtol': 1e-6}}}
    exact = {'answer': {'stages': [{'slack_ns': -0.405275}], 'max_capacitance_ff': 60.932533264}}
    assert score(exact, entry)['passed']
    assert not score({'answer': {**exact['answer'], 'max_capacitance_ff': 0.060932533264}}, entry)['passed']
    assert not score({'answer': {**exact['answer'], 'max_capacitance_ff': 60.95}}, entry)['passed']
    assert not score({'answer': {**exact['answer'], 'stages': [{'slack_ns': -0.4033}]}}, entry)['passed']
    entry['match_rules']['answer.max_capacitance_ff'] = {'atol': 1e-6, 'rtol': 0}
    assert not score(exact, entry)['passed']


def test_declared_container_numeric_tolerance_reaches_nested_facts():
    entry = {'gold': {'answer': {'power': 0.0123, 'nested': {'value': 0.0456}}},
             'graded_keys': ['answer'], 'match_rules': {'answer': {'atol': 1e-6, 'rtol': 0}}}
    answer = {'answer': {'power': 0.0123005, 'nested': {'value': 0.0456005}}}
    assert score(answer, entry)['passed']
    entry['match_rules']['answer.nested.value'] = {'atol': 1e-9, 'rtol': 0}
    assert not score(answer, entry)['passed']
    answer['answer']['nested']['value'] = 0.0456
    answer['answer']['power'] = 0.012302
    assert not score(answer, entry)['passed']


def test_unknown_request_remains_reserved_and_complete_usage_releases_reservation(tmp_path):
    ledger = Ledger(tmp_path / 'usage.jsonl')
    ledger.append({'request_id': 'a', 'reserved_rmb': 299.8, 'status': 'reserved'}, reserve=True)
    ledger.append({'request_id': 'a', 'reserved_rmb': 299.8, 'status': 'unknown_or_failed'})
    with pytest.raises(BudgetExhausted):
        ledger.append({'request_id': 'b', 'reserved_rmb': 0.3}, reserve=True)
    ledger.append({'request_id': 'a', 'reserved_rmb': 299.8, 'cost_upper_rmb': 0.1, 'status': 'received'})
    ledger.append({'request_id': 'b', 'reserved_rmb': 0.3}, reserve=True)
    assert len((tmp_path / 'usage.jsonl').read_text().splitlines()) == 4
    assert usage_cost({'prompt_tokens': 1000000, 'completion_tokens': 1000000,
                       'prompt_cache_hit_tokens': 500000}, PEAK) == pytest.approx(9.02)


def test_saved_json_output_continuation_recovers_full_unicode(tmp_path):
    content = json.dumps({'text': '中文大设计' * 10000, 'numbers': list(range(1000))}, ensure_ascii=False)
    path = tmp_path / 'output-1.txt'; path.write_text(content)
    chunks = []; offset = 0
    while True:
        page = output_page(path, offset)
        chunks.append(page['output'])
        if not page['continuation']:break
        offset = page['continuation']['offset']
    assert ''.join(chunks) == content
    assert json.loads(''.join(chunks))['numbers'][-1] == 999


def test_scoring_keeps_facts_required_when_explanation_is_background():
    entry = {'gold': {'rounded': {'value': 0, 'note': 'reference prose'}},
             'graded_keys': ['rounded'], 'match_rules': {'rounded.note': {'match_rule': 'background'}}}
    assert score({'rounded': {'value': 0, 'note': 'different accurate explanation'}}, entry)['passed']
    assert not score({'rounded': {'value': 0.2}}, entry)['passed']


def test_answer_parser_recovers_one_json_without_choosing_among_conflicting_answers():
    from qualification.v3.run_model import parse_answer
    assert parse_answer('The reported slack is below zero.\n```json\n{"slack":-0.01}\n```')['slack'] == -0.01
    with pytest.raises(ValueError):
        parse_answer('One answer: {"slack":1}. Another answer: {"slack":2}')


def test_direction_enum_case_does_not_change_fact_but_names_and_reversed_direction_do():
    entry = {'gold': {'pin': {'name': 'CLK', 'direction': 'INPUT'}},
             'graded_keys': ['pin'], 'match_rules': {}}
    assert score({'pin': {'name': 'CLK', 'direction': 'input'}}, entry)['passed']
    assert not score({'pin': {'name': 'clk', 'direction': 'input'}}, entry)['passed']
    assert not score({'pin': {'name': 'CLK', 'direction': 'OUTPUT'}}, entry)['passed']


def test_explicit_stage_enum_ignores_case_without_relaxing_object_names():
    entry = {'gold': {'pair': [{'stage': 'cts', 'net': 'netA'}]}, 'graded_keys': ['pair'],
             'match_rules': {'pair[].stage': {'match_rule': 'enum_casefold'}}}
    assert score({'pair': [{'stage': 'CTS', 'net': 'netA'}]}, entry)['passed']
    assert not score({'pair': [{'stage': 'CTS', 'net': 'neta'}]}, entry)['passed']
    assert not score({'pair': [{'stage': 'route', 'net': 'netA'}]}, entry)['passed']


def test_source_aliases_do_not_relax_hash_or_run_identity():
    entry = {'gold': {'source': {'file': 'results/nangate45/chip/run/6_final.odb', 'sha256': 'a' * 64}},
             'graded_keys': ['source'], 'match_rules': {'source.file': {'match_rule': 'source_file'}}}
    assert score({'source': {'file': '/data/results/nangate45/chip/run/6_final.odb', 'sha256': 'a' * 64}}, entry)['passed']
    assert score({'source': {'file': '6_final.odb', 'sha256': 'a' * 64}}, entry)['passed']
    assert not score({'source': {'file': '6_final.odb', 'sha256': 'b' * 64}}, entry)['passed']
    assert not score({'source': {'file': 'results/nangate45/chip/other-run/6_final.odb', 'sha256': 'a' * 64}}, entry)['passed']


def test_unit_syntax_and_clock_role_words_preserve_physical_meaning():
    entry = {'gold': {'unit':'1,ff','role':'launch+capture','capacitance':3},
             'graded_keys':['unit','role','capacitance'],
             'match_rules':{'unit':{'match_rule':'unit_literal'},'role':{'match_rule':'clock_role'}}}
    assert score({'unit':'1ff','role':'launch and capture','capacitance':3},entry)['passed']
    assert not score({'unit':'1pf','role':'launch and capture','capacitance':3},entry)['passed']
    assert not score({'unit':'1ff','role':'capture','capacitance':3},entry)['passed']
    assert not score({'unit':'1ff','role':'launch+capture','capacitance':4},entry)['passed']


def test_absent_object_name_accepts_native_empty_string_without_accepting_fabricated_owner():
    entry = {'gold':{'instance':None,'net':'clock_net','arrival':0},
             'graded_keys':['instance','net','arrival'],
             'match_rules':{'instance':{'match_rule':'absent_name'},'net':{'match_rule':'absent_name'}}}
    assert score({'instance':'','net':'clock_net','arrival':0},entry)['passed']
    assert not score({'instance':'clock_port','net':'clock_net','arrival':0},entry)['passed']
    assert not score({'instance':0,'net':'clock_net','arrival':0},entry)['passed']
    assert not score({'instance':'','net':'','arrival':0},entry)['passed']


def test_report_cell_is_checked_privately_without_accepting_a_different_cell_with_similar_name():
    entry = {'gold':{'raw_report_match':'u/A (BUF_X1) 0.01'},'graded_keys':['raw_report_match'],
             'match_rules':{'raw_report_match':{'match_rule':'report_cell'}}}
    assert score({'raw_report_match':'original timing line u/A (BUF_X1)'},entry)['passed']
    assert not score({'raw_report_match':'u/A (CLKBUF_X1)'},entry)['passed']


def test_stopped_exam_saves_interruption_without_another_paid_request(tmp_path, monkeypatch):
    from qualification.v3 import run_model
    monkeypatch.setattr(run_model, 'RESULTS', tmp_path)
    def forbidden_call(*args, **kwargs):
        pytest.fail('an interrupted exam sent another billable request')
    monkeypatch.setattr(run_model, 'call', forbidden_call)
    question = {'id': 'metrics-01', 'category': 'metrics', 'question': 'original fact',
                'answer_schema': {}, 'match_rules': {},
                'scoring': {'units': {}, 'tolerance': {}, 'tie_rule': 'n/a'}}
    run_model.STOP.set()
    try:
        result = run_model.episode('ibex', question, 'interface', 'stopped', None, 'unused')
        assert result['status'] == 'interrupted'
        assert result['requests'] == []
        assert result['passed'] is False
        assert list(tmp_path.glob('stopped/*/result.json'))
    finally:
        run_model.STOP.clear()


def test_invalid_url_is_a_correctable_tool_error_before_http_dispatch(tmp_path, monkeypatch):
    from qualification.v3 import benchmark_tool, run_model
    monkeypatch.setattr(benchmark_tool, 'WORK', tmp_path / 'work')
    monkeypatch.setattr(run_model, 'RESULTS', tmp_path / 'results')
    calls = iter([{'role': 'assistant', 'content': '', 'tool_calls': [{
        'id': 'bad-url', 'function': {'name': 'eda_tool', 'arguments': json.dumps({
            'path': '/snapshots/s/artifacts/files/search?pattern=worst slack'})}}]},
        {'role': 'assistant', 'content': '{"value":1}'}])
    def call(messages, *args, **kwargs):
        if len(messages) > 2:
            assert 'URL-encode' in messages[-1]['content']
        return {'usage': {'prompt_tokens': 10, 'completion_tokens': 1},
                'choices': [{'message': next(calls)}]}, 'request'
    monkeypatch.setattr(run_model, 'call', call)
    bank = tmp_path / 'bank/gold'; bank.mkdir(parents=True)
    (bank / 'ibex.json').write_text(json.dumps({'gold': {'q': {
        'gold': {'value': 1}, 'graded_keys': ['value']}}}))
    question = {'id': 'q', 'category': 'metrics', 'question': 'fact', 'answer_schema': {},
                'match_rules': {}, 'scoring': {'units': {}, 'tolerance': {}, 'tie_rule': 'n/a'}}
    result = run_model.episode('ibex', question, 'interface', 'url-check', None, 'unused', bank.parent)
    assert result['passed'] and result['tool_calls'] == 1


def test_refused_provider_connection_stops_new_requests_and_keeps_failure(tmp_path, monkeypatch):
    import urllib.error
    from qualification.v3 import run_model
    from qualification.v3.deepseek_provider import ProviderFailure
    monkeypatch.setattr(run_model, 'RESULTS', tmp_path)
    def refused(*args, **kwargs):
        raise ProviderFailure('connection refused') from urllib.error.URLError(ConnectionRefusedError(111, 'refused'))
    monkeypatch.setattr(run_model, 'call', refused)
    question = {'id': 'q', 'category': 'metrics', 'question': 'fact', 'answer_schema': {},
                'match_rules': {}, 'scoring': {'units': {}, 'tolerance': {}, 'tie_rule': 'n/a'}}
    try:
        row = run_model.episode('ibex', question, 'interface', 'refused', None, 'unused')
        assert row['status'] == 'provider_failed_no_retry' and not row['passed']
        assert run_model.STOP.is_set()
        next_row = run_model.episode('ibex', question, 'raw', 'refused', None, 'unused')
        assert next_row['status'] == 'interrupted' and next_row['requests'] == []
    finally:
        run_model.STOP.clear()


def test_refused_connection_releases_reservation_but_unknown_remote_failure_keeps_it(tmp_path, monkeypatch):
    import urllib.error
    from qualification.v3 import deepseek_provider as provider
    key = tmp_path / 'test.key'; key.write_text('test-only')
    monkeypatch.setattr(provider, 'KEY_FILE', key)
    ledger = provider.Ledger(tmp_path / 'usage.jsonl')
    def refused(*args, **kwargs):
        raise urllib.error.URLError(ConnectionRefusedError(111, 'refused'))
    monkeypatch.setattr(provider.urllib.request, 'urlopen', refused)
    with pytest.raises(provider.ProviderFailure):
        provider.call([], [], ledger, 'refused', 1)
    last = json.loads(ledger.path.read_text().splitlines()[-1])
    assert last['cost_upper_rmb'] == 0 and last['status'] == 'not_sent_connection_refused'
    def unknown(*args, **kwargs):
        raise TimeoutError('no receipt')
    monkeypatch.setattr(provider.urllib.request, 'urlopen', unknown)
    with pytest.raises(provider.ProviderFailure):
        provider.call([], [], ledger, 'unknown', 1)
    last = json.loads(ledger.path.read_text().splitlines()[-1])
    assert last['status'] == 'unknown_or_failed' and 'cost_upper_rmb' not in last


@pytest.mark.parametrize('arm,bad_name,bad_arguments', [
    ('interface', 'eda_tool', '{"path":"bad\\q"}'),
    ('raw', 'eda_tool', '{"code":"bad\\q"}'),
    ('interface', 'eda_tool', '[]'),
    ('raw', 'eda_tool', '{"code":1}'),
    ('interface', 'eda_tool', '{"path":"/help","extra":true}'),
    ('raw', 'eda_tool', '{}'),
    ('interface', 'eda_tool', '{"path":"/help","method":"DELETE"}'),
    ('raw', 'read_output', '{"output_id":"o","offset":true}'),
    ('interface', 'unknown', '{}'),
])
def test_invalid_tool_parameters_are_visible_then_model_corrects_with_all_costs_retained(
        tmp_path, monkeypatch, arm, bad_name, bad_arguments):
    from qualification.v3 import run_model
    monkeypatch.setattr(run_model, 'RESULTS', tmp_path / 'results')
    good_arguments = {'path': '/help'} if arm == 'interface' else {'code': 'cat report.txt'}
    messages_to_return = iter([
        {'role': 'assistant', 'tool_calls': [{'id': 'invalid', 'function': {
            'name': bad_name, 'arguments': bad_arguments}}]},
        {'role': 'assistant', 'tool_calls': [{'id': 'corrected', 'function': {
            'name': 'eda_tool', 'arguments': json.dumps(good_arguments)}}]},
        {'role': 'assistant', 'content': '{"value":1}'},
    ])
    observed = []
    def invoke(messages, *args, **kwargs):
        observed.append([dict(message) for message in messages])
        return {'model': 'any-provider', 'usage': {'prompt_tokens': 10, 'completion_tokens': 2},
                'choices': [{'message': next(messages_to_return)}]}, str(len(observed))
    executed = []
    def execute(request):
        executed.append(request)
        return {'value': 1}
    monkeypatch.setattr(run_model, 'call', invoke)
    monkeypatch.setattr(run_model.benchmark_tool, 'execute', execute)
    gold = tmp_path / 'bank/gold'; gold.mkdir(parents=True)
    (gold / 'chip.json').write_text(json.dumps({'gold': {'q': {
        'gold': {'value': 1}, 'graded_keys': ['value']}}}))
    question = {'id': 'q', 'category': 'metrics', 'question': 'fact', 'answer_schema': {},
                'match_rules': {}, 'scoring': {'units': {}, 'tolerance': {}, 'tie_rule': 'n/a'}}
    row = run_model.episode('chip', question, arm, 'validation', None, 'unused', gold.parent)
    assert row['passed'] and row['status'] == 'answered'
    assert row['tool_calls'] == 2 and row['total_tokens'] == 36 and len(row['requests']) == 3
    assert len(executed) == 1
    assert 'tool_error' in observed[1][-1]['content']
    assert observed[1][-1]['tool_call_id'] == 'invalid'
    events = [json.loads(line) for line in next((tmp_path / 'results').glob('*/*/trace.jsonl')).read_text().splitlines()]
    tools = [event for event in events if event['kind'] == 'tool']
    assert tools[0]['raw_arguments'] == bad_arguments and tools[0]['arguments'] is None
    assert tools[1]['arguments'] == good_arguments
    assert row['tool_bytes'] == sum(len(json.dumps(event['result'], ensure_ascii=False).encode()) for event in tools)
