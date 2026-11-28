"""Configured model transport shares the cap and records actual usage safely."""
import io
import json
import urllib.error
import pytest
from qualification.v3.compatible_provider import Provider
from qualification.v3.deepseek_provider import Ledger, BudgetExhausted, ProviderFailure


def configured(tmp_path):
    secrets=tmp_path/'secret.json'
    secrets.write_text(json.dumps({'models':[{'label':'example','key':'DO_NOT_LOG_THIS'}]}))
    config=tmp_path/'provider.json'
    config.write_text(json.dumps({'base_url':'https://example.invalid/v1','secret_file':str(secrets),
        'models':[{'label':'example','model':'vendor/model','upper_rates_rmb_per_million':{'input':2,'cached':.2,'output':4}}]}))
    return Provider(config,'example')


def test_configured_model_and_cache_usage_are_recorded(tmp_path,monkeypatch):
    provider=configured(tmp_path)
    class Response(io.BytesIO):
        status=200
    def invoke(request,timeout):
        assert request.full_url=='https://example.invalid/v1/chat/completions'
        payload=json.loads(request.data)
        assert payload['model']=='vendor/model' and not payload['stream']
        assert request.get_header('Authorization')=='Bearer DO_NOT_LOG_THIS'
        return Response(json.dumps({'model':'vendor/model','usage':{'prompt_tokens':10,'completion_tokens':2,
            'prompt_tokens_details':{'cached_tokens':3}},'choices':[{'message':{'role':'assistant','content':'{}'}}]}).encode())
    monkeypatch.setattr('urllib.request.urlopen',invoke)
    ledger=Ledger(tmp_path/'ledger.jsonl',cap_rmb=1)
    result,identifier=provider.call([],[],ledger,'episode',1,max_tokens=32)
    rows=[json.loads(line) for line in ledger.path.read_text().splitlines()]
    assert rows[-1]['request_id']==identifier and rows[-1]['response_model']=='vendor/model'
    assert rows[-1]['usage']==result['usage']
    assert rows[-1]['cost_upper_rmb']==pytest.approx((7*2+3*.2+2*4)/1e6)
    assert 'DO_NOT_LOG_THIS' not in ledger.path.read_text()


def test_unknown_failure_is_not_retried_and_error_redacts_key(tmp_path,monkeypatch):
    provider=configured(tmp_path);calls=[]
    def invoke(request,timeout):
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url,503,'unavailable',{},io.BytesIO(b'DO_NOT_LOG_THIS channel unavailable'))
    monkeypatch.setattr('urllib.request.urlopen',invoke)
    ledger=Ledger(tmp_path/'ledger.jsonl',cap_rmb=1)
    with pytest.raises(ProviderFailure):provider.call([],[],ledger,'failed',1,max_tokens=32)
    assert len(calls)==1 and 'DO_NOT_LOG_THIS' not in ledger.path.read_text()
    row=json.loads(ledger.path.read_text().splitlines()[-1])
    assert row['status']=='unknown_or_failed' and row['http_status']==503 and 'cost_upper_rmb' not in row


def test_configurable_cap_rejects_request_before_sending(tmp_path,monkeypatch):
    provider=configured(tmp_path)
    def forbidden(*args,**kwargs):pytest.fail('over-budget request must not be sent')
    monkeypatch.setattr('urllib.request.urlopen',forbidden)
    ledger=Ledger(tmp_path/'ledger.jsonl',cap_rmb=.001)
    with pytest.raises(BudgetExhausted):provider.call([],[],ledger,'capped',1,max_tokens=40000)


def test_native_protocol_uses_the_same_durable_billing_boundary(tmp_path, monkeypatch):
    provider = configured(tmp_path)
    provider.public_config['wire_api'] = 'gemini'
    class Response(io.BytesIO):
        status = 200
    def invoke(req, timeout):
        assert req.full_url.endswith('/v1beta/models/vendor%2Fmodel:generateContent')
        assert req.get_header('X-goog-api-key') == 'DO_NOT_LOG_THIS'
        payload = json.loads(req.data)
        assert payload['contents'][0]['parts'] == [{'text': 'question'}]
        return Response(json.dumps({'modelVersion': 'vendor/model', 'usageMetadata': {
            'promptTokenCount': 10, 'candidatesTokenCount': 2, 'totalTokenCount': 12},
            'candidates': [{'content': {'parts': [{'text': '{}'}]}, 'finishReason': 'STOP'}]}).encode())
    monkeypatch.setattr('urllib.request.urlopen', invoke)
    ledger = Ledger(tmp_path / 'native.jsonl', 1)
    result, identifier = provider.call([{'role': 'user', 'content': 'question'}], [], ledger, 'native', 1, max_tokens=32)
    rows = [json.loads(line) for line in ledger.path.read_text().splitlines()]
    assert rows[-1]['model'] == 'vendor/model' and rows[-1]['status'] == 'received'
    assert rows[-1]['request_id'] == identifier and result['usage']['total_tokens'] == 12
    assert 'DO_NOT_LOG_THIS' not in ledger.path.read_text()


def test_exam_resume_keeps_initial_health_without_confusing_it_with_settings(tmp_path, monkeypatch):
    from qualification.v3 import run_model
    bank = tmp_path / 'bank'
    for category in ('questions', 'gold'):
        (bank / category).mkdir(parents=True)
    (bank / 'questions/chip.json').write_text('{"questions":[]}')
    config = tmp_path / 'exam.json'
    config.write_text(json.dumps({'results_root': str(tmp_path / 'results')}))
    monkeypatch.setattr('sys.argv', ['exam', '--round', 'resume', '--selection', 'full', '--designs', 'chip',
        '--bank-dir', str(bank), '--exam-config', str(config), '--ledger', str(tmp_path / 'ledger')])
    class Opener:
        def open(self, *args, **kwargs):
            return io.BytesIO(b'{"healthy":true}')
    monkeypatch.setattr(run_model.benchmark_tool.urllib.request, 'build_opener', lambda *a: Opener())
    assert run_model.main() == 0
    folder = tmp_path / 'results/resume'
    assert json.loads((folder / 'service_health_at_start.json').read_text()) == {'healthy': True}
    assert 'actual_service_health_at_start' not in json.loads((folder / 'run_manifest.json').read_text())
    assert run_model.main() == 0
    config.write_text(json.dumps({'results_root': str(tmp_path / 'results'), 'variant': 'changed'}))
    with pytest.raises(ValueError, match='identical model'):
        run_model.main()
