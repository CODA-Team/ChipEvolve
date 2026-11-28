"""The shared exam transport carries real GET filters to the HTTP endpoint."""
import io
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from qualification.v3 import benchmark_tool


def test_filters_reach_the_endpoint_as_query_parameters_without_a_get_body(tmp_path, monkeypatch):
    class Response(io.BytesIO):
        status = 200
    class Opener:
        def open(self, request, timeout):
            assert request.method == 'GET' and request.data is None
            assert parse_qs(urlsplit(request.full_url).query) == {
                'limit': ['1'], 'kind': ['instance'], 'is_macro': ['true'], 'name': ['层级/u[0]']}
            return Response(b'{"data":{"object_count":136}}')
    monkeypatch.setattr(benchmark_tool.urllib.request, 'build_opener', lambda *a: Opener())
    monkeypatch.setattr(benchmark_tool, 'WORK', tmp_path)
    request = {'arm': 'interface', 'design': 'chip', 'episode': 'get-filters',
               'path': '/snapshots/s/objects/statistics?limit=1',
               'payload': {'kind': 'instance', 'is_macro': True, 'name': '层级/u[0]'}}
    result = benchmark_tool.execute(request)
    assert json.loads(result['output'])['data']['object_count'] == 136
    assert request['path'].endswith('?limit=1') and 'payload' in request


def test_conflicting_or_nested_filters_are_named_errors_before_any_http_call():
    with pytest.raises(ValueError, match='conflicting GET filter.*kind'):
        benchmark_tool.encode_get_filters({'path': '/snapshots/s/objects?kind=pin', 'payload': {'kind': 'instance'}})
    with pytest.raises(ValueError, match='encode lists explicitly'):
        benchmark_tool.encode_get_filters({'path': '/snapshots/s/objects', 'payload': {'ids': ['a', 'b']}})
    encoded = benchmark_tool.encode_get_filters({'path': '/snapshots/s/objects?kind=pin', 'payload': {'kind': 'pin'}})
    assert encoded['path'].count('kind=') == 1


def test_post_payload_and_ablation_controls_keep_their_original_semantics():
    request = {'method': 'POST', 'path': '/query', 'payload': {'requests': ['/snapshots']}}
    assert benchmark_tool.encode_get_filters(request) == request
    from qualification.v3.exam_ablation import ablated_request
    request = {'arm': 'interface', 'path': '/snapshots/s/objects',
               'ablation': 'without_auto_join', 'payload': {'include_engineering': 1}}
    with pytest.raises(ValueError):
        ablated_request(benchmark_tool.encode_get_filters(request))
