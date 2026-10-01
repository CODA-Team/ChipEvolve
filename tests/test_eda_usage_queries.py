import json
import pytest
from openroad_app_data_foundation.api_help import api_help, GUIDES
from openroad_app_data_foundation.native_queries import submit_native_query
from openroad_app_data_foundation.source_metadata import source_metadata
from openroad_app_data_foundation.repository import DataStore
from tests.test_eda_engineering import sample


def test_public_usage_preserves_complete_topics_and_real_snapshot_scope(tmp_path):
    store = DataStore(tmp_path / 's.sqlite')
    try:
        store.register(sample())
        catalog = api_help(store, 's', {})
        assert len(catalog['topics']) == 6
        for topic in catalog['topics']:
            guide = api_help(store, 's', {'topic': topic['topic']})['guide']
            assert guide and '{design}' not in guide and '{variant}' not in guide
        assert 'wait_seconds=120' in GUIDES['native']
        with pytest.raises(ValueError):
            api_help(store, 's', {'topic': 'not-a-topic'})
        with pytest.raises(KeyError):
            api_help(store, 'absent', {})
    finally:
        store.close()


@pytest.mark.parametrize('value', [-1, 121, 1.5, True, '10'])
def test_invalid_native_wait_is_rejected_before_submission(tmp_path, value):
    class NoSubmit:
        def submit(self, task):
            pytest.fail('invalid wait must never start an execution')
    with pytest.raises(ValueError, match='wait_seconds'):
        submit_native_query(None, NoSubmit(), 's', {'script': 'puts ok', 'wait_seconds': value})


@pytest.mark.parametrize('status', ['succeeded', 'failed', 'running'])
def test_submit_and_wait_returns_real_outcome_and_original_report(tmp_path, status):
    pack = sample()
    pack['run_summary']['timing_context'] = {'executor': '/tool/openroad'}
    pack['snapshot']['source_artifacts'] = [
        {'artifact_id': 'odb', 'logical_path': 'inputs/design.odb', 'category': 'raw_design_database', 'run_id': 'run', 'stage': 'finish', 'sha256': 'a'*64, 'size_bytes': 20}]
    calls = []
    class Client:
        def submit(self, task):
            calls.append(task)
            return {'run': {'run_id': 'job', 'status': 'running'}}
        def run(self, run_id):
            assert run_id == 'job'
            return {'project_id': 'eda-ai-native-query', 'status': status,
                    'stages': [{'attempts': [{'failure': {'message': 'actual bad Tcl'}}]}] if status == 'failed' else []}
        def artifacts(self, run_id):
            return [{'artifact_id': 'report', 'kind': 'analysis_report', 'metadata': {'report': 'native'}}]
        def artifact_excerpt(self, run_id, artifact_id, **query):
            assert query == {'offset': 0, 'max_bytes': 256}
            return {'text': 'real native output', 'truncated': False}
    store = DataStore(tmp_path / 'native.sqlite')
    try:
        store.register(pack)
        result = submit_native_query(store, Client(), 's',
            {'script': 'puts actual', 'wait_seconds': 1, 'max_bytes': 256})
        assert len(calls) == 1 and result['status'] == status
        assert result['run']['run_id'] == 'job'
        if status == 'failed':
            assert result['failure_details'] == [{'message': 'actual bad Tcl'}]
        if status != 'running':
            assert result['excerpt']['text'] == 'real native output'
        else:
            assert 'excerpt' not in result
    finally:
        store.close()


def test_excerpt_text_and_exact_bytes_remain_separately_retrievable():
    import base64
    from openroad_app_data_foundation.excerpts import excerpt_view
    original = b'original UTF8 \xe4\xb8\xad\n\xffbinary'
    raw = {'artifact_id': 'source', 'sha256': 'a'*64, 'offset': 0, 'bytes_read': len(original),
           'size_bytes': len(original), 'text': original.decode(errors='replace'),
           'data_base64': base64.b64encode(original).decode(), 'truncated': False}
    text = excerpt_view(raw, {})
    exact = excerpt_view(raw, {'format': 'base64'})
    assert text['text'] == raw['text'] and 'data_base64' not in text
    assert 'text' not in exact and base64.b64decode(exact['data_base64']) == original
    assert text['next_offset'] is None
    page = {**raw, 'offset': 10, 'bytes_read': 3, 'truncated': True}
    assert excerpt_view(page, {})['next_offset'] == 13
    assert excerpt_view(raw, {'format': 'full'}) is raw
    assert text['bytes_read'] == exact['bytes_read'] == len(original)
    with pytest.raises(ValueError):
        excerpt_view(raw, {'format': 'made-up-format'})


def test_original_metric_corners_do_not_reuse_declared_snapshot_label(tmp_path):
    root = tmp_path / 'flow'
    logs = root / 'logs/p/chip/r'
    logs.mkdir(parents=True)
    (logs / '6_report.json').write_text(json.dumps({'finish__timing__setup__tns__corner:slow_hot': -1,
                                                 'finish__timing__setup__tns__corner:fast': 0}))
    pack = sample()
    pack['run_summary']['timing_context'] = {'corner': 'declared-label'}
    store = DataStore(tmp_path / 'scenario.sqlite')
    try:
        store.register(pack)
        data = source_metadata(store, 's', root)
        assert data['timing_context']['corner'] == 'declared-label'
        assert data['original_metric_scenarios'][0]['corner_names'] == ['fast', 'slow_hot']
        assert data['original_metric_scenarios'][0]['source']['relative_path'] == 'logs/p/chip/r/6_report.json'
    finally:
        store.close()
