"""Native protocol conversion preserves tool observations, signatures and usage."""
import json
from qualification.v3.gemini_protocol import request, response


def test_native_tool_round_trip_preserves_signature_and_actual_hidden_observation():
    native = {'modelVersion': 'gemini-family', 'usageMetadata': {'promptTokenCount': 20,
        'candidatesTokenCount': 3, 'thoughtsTokenCount': 7, 'totalTokenCount': 30,
        'cachedContentTokenCount': 4}, 'candidates': [{'finishReason': 'STOP', 'content': {
        'role': 'model', 'parts': [{'thought': True, 'text': 'reason'}, {'thoughtSignature': 'sig',
        'functionCall': {'name': 'eda_tool', 'args': {'path': '/snapshots'}}}]}}]}
    normalized = response(native)
    message = normalized['choices'][0]['message']
    tool_call = message['tool_calls'][0]
    assert normalized['usage']['completion_tokens'] == 10
    assert normalized['usage']['prompt_tokens_details']['cached_tokens'] == 4
    messages = [{'role': 'system', 'content': 'shared engineering guide'},
                {'role': 'user', 'content': 'find design'}, message,
                {'role': 'tool', 'tool_call_id': tool_call['id'], 'content': 'actual design'}]
    tools = [{'type': 'function', 'function': {'name': 'eda_tool', 'description': 'query',
              'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}}}}]
    endpoint, payload = request('gemini-family', messages, tools, 1024, {})
    assert endpoint == '/v1beta/models/gemini-family:generateContent'
    assert payload['systemInstruction']['parts'][0]['text'] == 'shared engineering guide'
    assert payload['contents'][1]['parts'][1]['thoughtSignature'] == 'sig'
    assert payload['contents'][2]['parts'][0]['functionResponse'] == {
        'name': 'eda_tool', 'response': {'result': 'actual design'}}
    assert payload['generationConfig']['maxOutputTokens'] == 1024
    assert json.loads(tool_call['function']['arguments']) == {'path': '/snapshots'}
    assert normalized['provider_native_response'] == native


def test_parallel_same_name_calls_echo_native_ids_and_preserve_signed_parts():
    native = {'usageMetadata': {'totalTokenCount': 1}, 'candidates': [{'content': {'parts': [
        {'functionCall': {'id': 'call-a', 'name': 'lookup', 'args': {'key': 'a'}},
         'thoughtSignature': 'signed-a'},
        {'functionCall': {'id': 'call-b', 'name': 'lookup', 'args': {'key': 'b'}}}]}}]}
    message = response(native)['choices'][0]['message']
    assert [call['id'] for call in message['tool_calls']] == ['call-a', 'call-b']
    messages = [{'role': 'user', 'content': 'lookup both'}, message,
                {'role': 'tool', 'tool_call_id': 'call-a', 'content': 'A'},
                {'role': 'tool', 'tool_call_id': 'call-b', 'content': 'B'}]
    _, payload = request('family', messages, [], 20, {})
    assert payload['contents'][1]['parts'] == native['candidates'][0]['content']['parts']
    assert [part['functionResponse'] for part in payload['contents'][2]['parts']] == [
        {'id': 'call-a', 'name': 'lookup', 'response': {'result': 'A'}},
        {'id': 'call-b', 'name': 'lookup', 'response': {'result': 'B'}}]


def test_repeated_serialization_keeps_original_signed_content_unchanged():
    first = {'role': 'assistant', 'provider_parts': [{'text': 'one', 'thoughtSignature': 'sig-one'}]}
    second = {'role': 'assistant', 'provider_parts': [{'text': 'two', 'thoughtSignature': 'sig-two'}]}
    before = json.dumps([first, second])
    _, payload = request('family', [first, second], [], 20, {})
    assert json.dumps([first, second]) == before
    assert payload['contents'] == [
        {'role': 'model', 'parts': first['provider_parts']},
        {'role': 'model', 'parts': second['provider_parts']}]
    assert request('family', [first, second], [], 20, {})[1] == payload
