"""Native timing results remain usable after complete or partial read batches."""
import io
import json
import time
from types import SimpleNamespace

import pytest

from qualification.v3 import benchmark_tool, chatgpt_exam_mcp


@pytest.mark.parametrize('transport', ['shared', 'account'])
@pytest.mark.parametrize('kind', ['completed', 'pending', 'invalid_fields'])
def test_batch_queries_remain_owned_before_large_output_continuation(tmp_path, monkeypatch, transport, kind):
    sid = 'chip-original-global_route-query-112233aabbcc'
    result = {'status': 'available', 'data': {
        'query_execution': {'query_snapshot_id': sid, 'status': 'succeeded'},
        'long_complete_result': 'x' * (benchmark_tool.MAX_BYTES + 200)}}
    if kind == 'pending':
        result['data']['query_execution']['status'] = 'running'
    elif kind == 'invalid_fields':
        result = {'status': 'unavailable', 'data': {'error':
            'unknown metadata field; native query run already succeeded; correct the fields on '
            '/snapshots/' + sid + '/timing-overview?detail=full to reuse its complete result without another submission'}}
    batch = {'results': [{'status': 'available', 'data': {'snapshot_id': 'chip-original-global_route'}}, result]}
    observed = []

    def open_request(request, timeout):
        observed.append(request)
        response = io.BytesIO(json.dumps(batch if len(observed) == 1 else {'data': {'ok': True}}).encode())
        response.status = 200
        return response

    monkeypatch.setattr(benchmark_tool, 'WORK', tmp_path / 'work')
    monkeypatch.setattr(benchmark_tool.urllib.request, 'build_opener',
                        lambda *args: SimpleNamespace(open=open_request))
    context = {'arm': 'interface', 'design': 'chip', 'episode': 'batch-continuation',
               'base': 'http://eda.test', 'created_snapshots': []}
    tools = chatgpt_exam_mcp.ExamTools({**context, 'deadline': time.time() + 30}, tmp_path)
    owned = context['created_snapshots'] if transport == 'shared' else tools.state['created_snapshots']

    def invoke(arguments):
        if transport == 'shared':
            return benchmark_tool.execute({**context, **arguments})
        return json.loads(tools.call('eda_tool', arguments)['content'][0]['text'])

    first = invoke({'method': 'POST', 'path': '/query', 'payload': {'requests': [
        '/snapshots/chip-original-global_route/summary',
        '/snapshots/chip-original-global_route/timing-overview?resolve=1&fields=paths']}})
    assert owned == [sid]
    assert first['truncated'] == (kind != 'invalid_fields')
    assert invoke({'path': '/snapshots/' + sid + '/timing-overview'})['http_status'] == 200
    if transport == 'shared':
        with pytest.raises(ValueError, match='another episode'):
            invoke({'path': '/snapshots/chip-original-global_route-query-ffffffffffff/timing-overview'})
    else:
        assert 'another episode' in invoke({
            'path': '/snapshots/chip-original-global_route-query-ffffffffffff/timing-overview'})['tool_error']
    assert len(observed) == 2


def test_batch_keeps_every_resolved_query_once_and_ignores_other_result_ids():
    owned = []
    request = {'path': '/query', 'payload': {'requests': [
        '/snapshots/s/summary', '/snapshots/s/timing-overview?resolve=1',
        '/snapshots/s/timing-overview?resolve=1', '/snapshots/{same}/timing-overview?resolve=1']},
        'created_snapshots': owned}
    response = {'results': [
        {'status': 'available', 'data': {'snapshot_id': 'unrelated-query-do-not-own'}},
        {'status': 'available', 'data': {'query_execution': {'query_snapshot_id': 's-query-first'}}},
        {'status': 'available', 'data': {'query_execution': {'query_snapshot_id': 's-query-first'}}},
        {'status': 'available', 'data': {'query_execution': {'query_snapshot_id': 's-query-second'}}}]}
    benchmark_tool.remember_query_snapshot(request, json.dumps(response), 200)
    assert owned == ['s-query-first', 's-query-second']
    response['results'].pop()
    with pytest.raises(ValueError, match='request count'):
        benchmark_tool.remember_query_snapshot(request, json.dumps(response), 200)


def test_failed_name_or_native_context_does_not_drop_other_completed_query_results():
    request = {'path': '/query', 'payload': {'requests': [
        '/snapshots/missing/timing-overview?resolve=1',
        '/snapshots/s/timing-overview?resolve=1',
        '/snapshots/s/timing-overview?resolve=1&endpoint=wrong_name']}, 'created_snapshots': []}
    document = {'results': [
        {'status': 'not_found', 'data': {'error': 'snapshot missing'}},
        {'status': 'available', 'data': {'query_execution': {'query_snapshot_id': 's-query-complete'}}},
        {'status': 'unavailable', 'data': {'error': 'native endpoint not found'}}]}
    benchmark_tool.remember_query_snapshot(request, json.dumps(document), 200)
    assert request['created_snapshots'] == ['s-query-complete']
