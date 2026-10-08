"""Ablations remove actual capabilities while retaining sources and full lists."""
import pytest
from qualification.v3.exam_ablation import ablated_request
from tests.test_eda_compact_native_results import store


def query(path, profile, **extra):
    return ablated_request({'arm': 'interface', 'path': path, 'ablation': profile, **extra})


def test_disabled_joins_keep_individual_records_and_explicit_native_analysis():
    for path in ['/query', '/snapshots/s/timing-overview', '/snapshots/s/timing-paths/p/engineering',
                 '/snapshots/s/compare/t/inventory',
                 '/snapshots/s/instances/ram/pin-inventory?net_sort=load_count']:
        with pytest.raises(ValueError, match='joins/batches'):
            query(path, 'without_auto_join')
    for path in ['/snapshots/s/objects?kind=pin&limit=10', '/snapshots/s/timing-paths/p/points',
                 '/snapshots/s/native-queries']:
        assert query(path, 'without_auto_join')['path'] == path


def test_original_report_reads_preserve_sources_and_remove_declared_joins():
    source = '/snapshots/s/timing-reports?startpoint=u%2FA&limit=1&offset=2'
    assert query(source, 'without_auto_join')['path'] == source
    assert query(source, 'without_native_supplement')['path'] == source
    with pytest.raises(ValueError, match='joins/batches'):
        query(source + '&include_path_details=1', 'without_auto_join')
    expanded = query(source + '&fields=paths.slack_ns', 'without_compact_output')['path']
    assert expanded == source + '&detail=full'


def test_spatial_association_removal_keeps_individual_geometry_and_native_access():
    spatial = '/snapshots/s/objects?kind=instance&is_macro=1&sort=distance&reference_instance=logic'
    with pytest.raises(ValueError, match='joins/batches'):
        query(spatial, 'without_auto_join')
    with pytest.raises(ValueError, match='joins/batches'):
        query('/query', 'without_auto_join', payload={'requests': [spatial]})
    for path in ['/snapshots/s/objects?kind=instance&is_macro=1&sort=bbox_area',
                 '/snapshots/s/physical/logic', '/snapshots/s/native-queries']:
        assert query(path, 'without_auto_join')['path'] == path
    assert query(spatial, 'without_native_supplement')['path'] == spatial


def test_disabled_native_removes_implicit_supplements_and_keeps_existing_sources():
    for path in ['/snapshots/s/native-queries', '/snapshots/s/timing-overview?resolve=1',
                 '/snapshots/s/instances/ram/pin-inventory', '/native-queries/run',
                 '/snapshots/s/instances/ram/power']:
        with pytest.raises(ValueError, match='supplemental'):
            query(path, 'without_native_supplement')
    assert query('/snapshots/s/artifacts/files/excerpt?path=original.rpt',
                 'without_native_supplement')['path'].endswith('path=original.rpt')
    with pytest.raises(ValueError, match='supplemental'):
        query('/query', 'without_native_supplement', payload={
            'requests': ['/snapshots/s/timing-overview?resolve=1']})


def test_expanded_output_removes_projection_keeps_filters_and_pagination():
    result = query('/snapshots/s/objects?kind=instance&is_macro=1&fields=name&format=columns&limit=10&offset=20',
                   'without_compact_output')
    assert result['path'] == '/snapshots/s/objects?kind=instance&is_macro=1&limit=10&offset=20'
    result = query('/query', 'without_compact_output', payload={
        'requests': ['/snapshots?origin=flow&fields=snapshot_id', '/snapshots/s/summary?fields=run_summary'],
        'bindings': {'stage': {'request': 0, 'pointer': '/data/snapshots/0/stage'}}})
    assert result['payload']['requests'][0] == '/snapshots?origin=flow&detail=full'
    assert result['payload']['requests'][1] == '/snapshots/s/summary?detail=full'
    assert result['payload']['bindings']['stage']['request'] == 0
    result = query('/snapshots/s/constraints?fields=clocks&kind=all&offset=20', 'without_compact_output')
    assert result['path'] == '/snapshots/s/constraints?kind=all&offset=20&detail=full'


def test_baseline_request_is_unchanged_and_unknown_profiles_are_explicit():
    original = {'arm': 'interface', 'path': '/snapshots'}
    assert ablated_request(original) is original
    with pytest.raises(ValueError, match='declared'):
        query('/snapshots', 'unknown')


def test_account_tools_enforce_the_same_capability_removal_and_record_the_failure(tmp_path):
    import json
    import time
    from qualification.v3.chatgpt_exam_mcp import ExamTools
    tools = ExamTools({'arm': 'interface', 'design': 'chip', 'episode': 'ablation',
        'base': 'http://unused.invalid', 'deadline': time.time() + 10,
        'ablation': 'without_native_supplement'}, tmp_path)
    reply = tools.call('eda_tool', {'path': '/snapshots/s/native-queries',
                       'method': 'POST', 'payload': {'script': 'puts fact'}})
    assert 'supplemental analysis is disabled' in reply['content'][0]['text']
    trace = json.loads((tmp_path / 'trace.jsonl').read_text())
    assert 'tool_error' in trace['result'] and tools.state['tool_calls'] == 1


@pytest.mark.parametrize('pin', ['iterm%3A917617', 'bterm%3A12', 'ram%2Faddr%5B0%5D'])
def test_native_removal_blocks_pin_engineering_before_any_native_execution(tmp_path, monkeypatch, pin):
    import json
    import time
    from qualification.v3 import benchmark_tool
    from qualification.v3.chatgpt_exam_mcp import ExamTools

    class UnreachableNetwork:
        def open(self, *args, **kwargs):
            raise AssertionError('A removed native getter reached the application')

    monkeypatch.setattr(benchmark_tool.urllib.request, 'build_opener', lambda *a: UnreachableNetwork())
    path = '/snapshots/s/pins/' + pin + '/engineering'
    request = {'arm': 'interface', 'design': 'chip', 'episode': 'ablation-pin',
               'base': 'http://unused.invalid', 'ablation': 'without_native_supplement', 'path': path}
    with pytest.raises(ValueError, match='supplemental'):
        benchmark_tool.execute(request)
    tools = ExamTools({**request, 'deadline': time.time() + 10}, tmp_path)
    reply = tools.call('eda_tool', {'path': path})
    assert 'supplemental analysis is disabled' in reply['content'][0]['text']
    assert json.loads((tmp_path / 'trace.jsonl').read_text())['result']['tool_error']
    with pytest.raises(ValueError, match='supplemental'):
        query('/query', 'without_native_supplement', payload={'requests': [path]})
    source = '/snapshots/s/objects?kind=pin&parent_instance=ram'
    assert query(source, 'without_native_supplement')['path'] == source
    assert query(path, 'without_compact_output')['path'] == path


def test_pair_join_removal_is_shared_by_transports_and_preserves_other_capability_scopes(tmp_path, monkeypatch):
    import json
    import time
    from qualification.v3 import benchmark_tool
    from qualification.v3.chatgpt_exam_mcp import ExamTools

    class UnreachableNetwork:
        def open(self, *args, **kwargs):
            raise AssertionError('Removed pair join reached the application')

    monkeypatch.setattr(benchmark_tool.urllib.request, 'build_opener', lambda *a: UnreachableNetwork())
    path = '/snapshots/s/instances/u/pair?with_instance=v&signal_type=SIGNAL&fields=shared_nets&limit=1'
    request = {'arm': 'interface', 'design': 'chip', 'episode': 'pair-ablation',
               'path': path, 'ablation': 'without_auto_join'}
    with pytest.raises(ValueError, match='joins/batches'):
        benchmark_tool.execute(request)
    tools = ExamTools({**request, 'base': 'http://unused.invalid', 'deadline': time.time() + 10}, tmp_path)
    tools.call('eda_tool', {'path': path})
    assert 'joins/batches' in json.loads((tmp_path / 'trace.jsonl').read_text())['result']['tool_error']
    assert query(path, 'without_native_supplement')['path'] == path
    assert query(path, 'without_compact_output')['path'] == (
        '/snapshots/s/instances/u/pair?with_instance=v&signal_type=SIGNAL&limit=1')


def test_native_power_removal_blocks_direct_and_batched_queries_in_both_transports(tmp_path, monkeypatch):
    import json
    import time
    from qualification.v3 import benchmark_tool
    from qualification.v3.chatgpt_exam_mcp import ExamTools
    class UnreachableNetwork:
        def open(self, *args, **kwargs):
            raise AssertionError('Disabled native power reached the application')
    monkeypatch.setattr(benchmark_tool.urllib.request, 'build_opener', lambda *a: UnreachableNetwork())
    path = '/snapshots/s/instances/ram%2Fbank%5B0%5D/power'
    request = {'arm': 'interface', 'design': 'chip', 'episode': 'power-ablation',
               'path': path, 'ablation': 'without_native_supplement'}
    with pytest.raises(ValueError, match='supplemental'):
        benchmark_tool.execute(request)
    tools = ExamTools({**request, 'base': 'http://unused.invalid', 'deadline': time.time()+10}, tmp_path)
    tools.call('eda_tool', {'path': path})
    assert 'supplemental' in json.loads((tmp_path/'trace.jsonl').read_text())['result']['tool_error']
    with pytest.raises(ValueError, match='supplemental'):
        query('/query', 'without_native_supplement', payload={'requests': [path]})
    assert query(path, 'without_auto_join')['path'] == path
    assert query(path, 'without_compact_output')['path'] == path


def test_full_native_delivery_preserves_actual_script_filters_and_page_budget():
    payload = {'script': 'puts actual', 'with_timing': True, 'wait_seconds': 120, 'max_bytes': 8192}
    full = query('/snapshots/s/native-queries', 'without_compact_output', method='POST', payload=payload)
    assert full['payload'] == {**payload, 'detail': 'full', 'format': 'full'}
    assert payload == {'script': 'puts actual', 'with_timing': True, 'wait_seconds': 120, 'max_bytes': 8192}
    continued = query('/native-queries/run?wait_seconds=120&offset=8192&max_bytes=4096', 'without_compact_output')
    assert continued['path'] == '/native-queries/run?wait_seconds=120&offset=8192&max_bytes=4096&detail=full&format=full'


def test_full_delivery_ablation_submits_same_query_and_returns_real_input_metadata(store):
    from tests.test_eda_compact_native_results import NativeClient, handler
    client = NativeClient('succeeded')
    h = handler(store, client)
    request = query('/snapshots/s/native-queries', 'without_compact_output', method='POST',
                    payload={'script': 'puts actual', 'wait_seconds': 120, 'max_bytes': 8192})
    h.path = request['path']
    h._read_body = lambda: dict(request['payload'])
    replies = []
    h._send = lambda code, payload: replies.append((code, payload))
    h.do_POST()
    code, actual = replies[0]
    assert code == 200 and actual['status'] == 'succeeded'
    assert len(client.submissions) == 1 and client.submissions[0]['inputs']['script'] == 'puts actual'
    assert actual['original_input_artifacts'] == client.inputs
    assert actual['excerpt']['text'] == client.report
    assert client.reads == [(0, 8192)]
