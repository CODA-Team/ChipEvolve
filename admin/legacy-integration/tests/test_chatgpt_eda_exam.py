"""Account exam budget boundaries and actual CLI usage accounting."""
import json
import time
import io
import urllib.error
from types import SimpleNamespace

import pytest

from qualification.v3 import benchmark_tool, chatgpt_exam_mcp, run_chatgpt


@pytest.mark.parametrize('kind', ['submitted', 'resolved', 'projected', 'pending', 'invalid_fields'])
def test_every_runner_can_continue_its_own_native_query_even_with_chunked_output(tmp_path, monkeypatch, kind):
    sid = 'ibex-run-finish-query-123456abcdef'
    method, status = 'GET', 200
    path = '/snapshots/ibex-run-finish/timing-overview?resolve=1'
    payload = {'data': {'query_execution': {'query_snapshot_id': sid},
                        'detail': 'x' * (benchmark_tool.MAX_BYTES + 100)}}
    if kind == 'submitted':
        method, status = 'POST', 202
        path = '/snapshots/ibex-run-finish/timing-queries'
        payload = {'snapshot_id': sid}
    elif kind == 'projected':
        path += '&fields=nets.name'
        payload['data']['snapshot'] = {'snapshot_id': sid}
    elif kind == 'pending':
        payload['data']['snapshot_id'] = 'ibex-run-finish'
        payload['data']['query_execution']['status'] = 'running'
    elif kind == 'invalid_fields':
        status = 400
        path += '&fields=not_a_real_field'
        payload = {'error': 'unknown metadata field; native query run already succeeded; correct the fields on '
                   + '/snapshots/' + sid + '/timing-overview?detail=full to reuse its complete result without another submission'}
    requests = []

    def open_request(request, timeout):
        requests.append(request)
        body = json.dumps(payload if len(requests) == 1 else {'data': {'ok': True}}).encode()
        if len(requests) == 1 and status == 400:
            raise urllib.error.HTTPError(request.full_url, 400, 'invalid fields', {}, io.BytesIO(body))
        response = io.BytesIO(body)
        response.status = status if len(requests) == 1 else 200
        return response

    monkeypatch.setattr(benchmark_tool, 'WORK', tmp_path / 'work')
    monkeypatch.setattr(benchmark_tool.urllib.request, 'build_opener',
                        lambda *args: SimpleNamespace(open=open_request))
    tools = chatgpt_exam_mcp.ExamTools({'arm': 'interface', 'design': 'ibex', 'episode': 'continuation',
                                      'base': 'http://eda.test', 'deadline': time.time() + 30}, tmp_path)
    first = json.loads(tools.call('eda_tool', {'path': path, 'method': method})['content'][0]['text'])
    assert first['http_status'] == status
    assert tools.state['created_snapshots'] == [sid]
    if kind in ('resolved', 'projected', 'pending'):
        assert first['truncated']
    continued = json.loads(tools.call('eda_tool', {'path': '/snapshots/' + sid + '/timing-overview'})['content'][0]['text'])
    assert continued['http_status'] == 200
    other = '/snapshots/ibex-run-finish-query-ffffffffffff/timing-overview'
    blocked = json.loads(tools.call('eda_tool', {'path': other})['content'][0]['text'])
    assert 'another episode' in blocked['tool_error']
    assert len(requests) == 2


def test_budget_blocks_execution_after_limit(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(benchmark_tool, 'execute', lambda request: calls.append(request) or {'output': 'ok'})
    tools = chatgpt_exam_mcp.ExamTools(
        {'arm': 'raw', 'design': 'ibex', 'episode': 'test', 'base': 'unused',
         'deadline': time.time() + 10}, tmp_path)
    tools.state['tool_calls'] = run_chatgpt.MAX_STEPS
    result = tools.call('eda_tool', {'code': 'echo must-not-run'})
    assert not calls
    assert 'budget exhausted' in result['content'][0]['text']
    assert json.loads((tmp_path / 'tool_state.json').read_text())['tool_calls'] == 33


def test_large_response_does_not_leak_past_reading_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark_tool, 'execute', lambda request: {'output': 'x' * 200})
    tools = chatgpt_exam_mcp.ExamTools(
        {'arm': 'interface', 'design': 'ibex', 'episode': 'test', 'base': 'unused',
         'deadline': time.time() + 10}, tmp_path)
    tools.state['tool_bytes'] = run_chatgpt.READ_BYTES - 100
    result = json.loads(tools.call('eda_tool', {'path': '/health'})['content'][0]['text'])
    assert 'output' not in result
    assert result['remaining_bytes'] == 100
    assert 'reading budget' in result['tool_error']


def test_cli_usage_keeps_cached_input_inside_total():
    usage, errors, extra = run_chatgpt.event_usage(json.dumps({
        'type': 'turn.completed', 'usage': {'input_tokens': 1000, 'cached_input_tokens': 700,
                                          'output_tokens': 100}}))
    assert usage == {'input_tokens': 1000, 'cached_input_tokens': 700, 'output_tokens': 100}
    assert usage['input_tokens'] + usage['output_tokens'] == 1100
    assert not errors and not extra


def test_failed_turn_has_unknown_usage_and_records_tool_bypass():
    events = [{'type': 'item.completed', 'item': {'type': 'command_execution'}},
              {'type': 'turn.failed', 'error': {'message': 'usage limit'}}]
    usage, errors, extra = run_chatgpt.event_usage('\n'.join(map(json.dumps, events)))
    assert usage is None
    assert errors == [events[1]]
    assert extra == ['command_execution']


def test_empty_resource_catalog_does_not_abort_valid_engineering_answers():
    probe = {'type': 'item.completed', 'item': {'type': 'mcp_tool_call', 'server': 'codex',
        'tool': 'list_mcp_resources', 'status': 'completed',
        'result': {'content': [{'type': 'text', 'text': '{"resources":[]}'}]}}}
    assert run_chatgpt.event_usage(json.dumps(probe))[2] == []
    probe['item']['result']['content'][0]['text'] = '{"resources":[{"uri":"file:///outside"}]}'
    assert run_chatgpt.event_usage(json.dumps(probe))[2] == ['codex']
    probe['item']['result']['content'][0]['text'] = 'malformed catalog'
    assert run_chatgpt.event_usage(json.dumps(probe))[2] == ['codex']


def test_invocation_uses_fresh_account_context_and_only_exam_mcp(tmp_path):
    cmd = run_chatgpt.command(tmp_path, tmp_path / 'context.json', 'public guide',
                              {'model': 'gpt-6.1-sol', 'forced_login_method': 'chatgpt'})
    assert '--ignore-user-config' in cmd and '--ephemeral' in cmd
    assert 'shell_tool' in cmd and 'plugins' in cmd and 'multi_agent' in cmd
    assert 'forced_login_method="chatgpt"' in cmd
    assert 'mcp_servers.eda.enabled_tools=["eda_tool", "read_output"]' in cmd
    assert 'resume' not in cmd


def test_transient_failure_does_not_abandon_the_rest_of_the_exam():
    assert not run_chatgpt.terminal_account_error([{'message': 'stream disconnected: error sending request'}])
    assert run_chatgpt.terminal_account_error([{'message': "You've hit your usage limit"}])
    assert run_chatgpt.terminal_account_error([{'message': '401 Unauthorized'}])


def test_recovered_account_stream_preserves_events_without_claiming_missing_usage():
    error = {'type': 'error', 'message': 'Reconnecting... 1/3: stream disconnected'}
    events = [error, {'type': 'turn.completed', 'usage': {'input_tokens': 1000, 'output_tokens': 100}}]
    usage, errors, extra = run_chatgpt.event_usage('\n'.join(map(json.dumps, events)))
    assert usage['input_tokens'] == 1000 and not extra
    recovery = run_chatgpt.transport_recovery(errors, '')
    assert recovery['observed'] and recovery['events'] == [error]
    assert not run_chatgpt.transport_recovery([], 'ordinary status')['observed']
    assert run_chatgpt.transport_recovery([], 'WARN request failed; retrying')['observed']


def test_exhausted_connection_stops_new_invocations_and_retains_unknown_failure(tmp_path, monkeypatch):
    error = {'type': 'turn.failed', 'error': {'message': 'Connection failed: error sending request'}}
    calls = []

    def failed_process(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1, communicate=lambda *a, **k: (
            json.dumps(error).encode(), b'Connection failed after reconnecting'))

    monkeypatch.setattr(run_chatgpt.subprocess, 'Popen', failed_process)
    monkeypatch.setattr(run_chatgpt, 'command', lambda *a: ['test-only'])
    question = {'id': 'q', 'category': 'metrics', 'question': 'fact', 'answer_schema': {},
                'match_rules': {}, 'scoring': {'units': {}, 'tolerance': {}, 'tie_rule': 'n/a'}}
    config = {'results_root': str(tmp_path)}
    try:
        failed = run_chatgpt.episode('chip', question, 'interface', 'outage', 'unused',
                                    tmp_path, {'model': 'test'}, config)
        assert failed['status'] == 'provider_failed' and not failed['usage_known']
        assert failed['invocation_started'] and run_chatgpt.STOP.is_set()
        assert json.loads((tmp_path / 'outage' / failed['episode'] / 'result.json').read_text()) == failed
        stopped = run_chatgpt.episode('chip', question, 'raw', 'outage', 'unused',
                                     tmp_path, {'model': 'test'}, config)
        assert stopped['status'] == 'interrupted' and not stopped['invocation_started']
        assert len(calls) == 1
    finally:
        run_chatgpt.STOP.clear()
