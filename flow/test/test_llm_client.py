"""Transport contract tests; no network requests or account credentials needed."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common
import llm_client as lc
from llm_usage import _usage_values


TOOL = {"type": "function", "function": {
    "name": "configure_model", "parameters": {
        "type": "object", "properties": {
            "kernel_type": {"type": "string", "enum": ["matern", "rbf"]},
            "explore_frac": {"type": "number"},
        }, "required": ["kernel_type"]}}}


def decision(**args):
    return {"content": "", "tool_calls": [{
        "name": "configure_model", "arguments": args}]}


def events(usage=None):
    return "\n".join(json.dumps(e) for e in [
        {"type": "thread.started", "thread_id": "test-thread"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}},
        {"type": "turn.completed", "usage": usage or {
            "input_tokens": 100, "cached_input_tokens": 40,
            "output_tokens": 12, "reasoning_output_tokens": 3}},
    ])


def test_optional_tool_arguments_preserve_defaults():
    strict = lc._response_schema([TOOL])["properties"]["tool_calls"]["items"]["anyOf"][0]
    assert strict["properties"]["arguments"]["required"] == ["kernel_type", "explore_frac"]
    msg = lc._decode_message(decision(kernel_type="rbf", explore_frac=None), [TOOL])
    assert json.loads(msg.tool_calls[0].function.arguments) == {"kernel_type": "rbf"}


@pytest.mark.parametrize("args", [
    {"kernel_type": "unsupported", "explore_frac": 0.4},
    {"kernel_type": "rbf", "explore_frac": True},
    {"kernel_type": None, "explore_frac": 0.4},
    {"kernel_type": "rbf", "explore_frac": float("nan")},
    {"kernel_type": "rbf"},
    {"kernel_type": "rbf", "explore_frac": 0.4, "extra": 1},
])
def test_invalid_tool_arguments_rejected(args):
    with pytest.raises(ValueError):
        lc._decode_message(decision(**args), [TOOL])


def test_unknown_tool_and_unrequested_tools_rejected():
    data = decision(kernel_type="rbf", explore_frac=0.2)
    data["tool_calls"][0]["name"] = "run_shell"
    with pytest.raises(ValueError):
        lc._decode_message(data, [TOOL])
    with pytest.raises(ValueError):
        lc._decode_message(data, [])


def test_done_without_tool_is_valid():
    assert not lc._decode_message({"content": "DONE", "tool_calls": []}, [TOOL]).tool_calls


def test_usage_matches_real_cli_counts():
    thread_id, usage = lc._decode_events(events())
    assert thread_id == "test-thread"
    parsed = _usage_values({"usage": usage})
    assert parsed["usage_complete"]
    assert (parsed["prompt_tokens"], parsed["completion_tokens"], parsed["total_tokens"],
            parsed["cached_tokens"], parsed["reasoning_tokens"]) == (100, 12, 112, 40, 3)
    _, usage = lc._decode_events(events({"input_tokens": 10, "output_tokens": 2}))
    assert usage["input_tokens_details"]["cached_tokens"] is None


@pytest.mark.parametrize("raw", [
    "", events({"input_tokens": 100}),
    events() + '\n{"type":"turn.failed"}',
    events() + '\n{"type":"item.completed","item":{"type":"command_execution"}}',
    events() + '\n{"type":"turn.completed","usage":{}}',
])
def test_incomplete_or_tool_using_turn_rejected(raw):
    with pytest.raises(RuntimeError):
        lc._decode_events(raw)


def make_client(monkeypatch):
    monkeypatch.setattr(lc.shutil, "which", lambda _: "/fake/codex")
    return lc.CodexClient({"timeout": 2})


def test_cli_request_and_result_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("DRP_CODEX_AUDIT_DIR", str(tmp_path))
    class Process:
        returncode = 0
        def __init__(self, command, **kwargs):
            assert "--ignore-user-config" in command and "--ephemeral" in command
            assert command[command.index("--sandbox") + 1] == "read-only"
            assert Path(kwargs["cwd"]) != Path.cwd()
            self.output = Path(command[command.index("--output-last-message") + 1])
        def communicate(self, prompt, timeout):
            assert TOOL["function"]["name"] in prompt and timeout == 2
            self.output.write_text(json.dumps(decision(kernel_type="rbf", explore_frac=0.2)))
            return events(), ""
    monkeypatch.setattr(lc.subprocess, "Popen", Process)
    result = make_client(monkeypatch).create(model="test-model", messages=[], tools=[TOOL])
    assert result.model is None and result.id == "test-thread"
    assert result.choices[0].message.tool_calls[0].function.name == "configure_model"
    saved = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert saved["requested_model"] == "test-model"
    assert saved["effective_settings"]["max_tokens"] is None


def test_timeout_kills_process_group(monkeypatch):
    calls = []
    class Process:
        pid = 999
        def __init__(self, *_args, **_kwargs):
            pass
        def communicate(self, *_args, **kwargs):
            if "timeout" in kwargs:
                raise subprocess.TimeoutExpired("codex", 2)
            return "", ""
    monkeypatch.setattr(lc.subprocess, "Popen", Process)
    monkeypatch.setattr(lc.os, "killpg", lambda pid, sig: calls.append((pid, sig)))
    with pytest.raises(subprocess.TimeoutExpired):
        make_client(monkeypatch).create(model="test", messages=[])
    assert calls == [(999, lc.signal.SIGKILL)]


def test_failed_cli_does_not_leak_stderr(monkeypatch):
    class Process:
        returncode = 1
        def __init__(self, *_args, **_kwargs):
            pass
        def communicate(self, *_args, **_kwargs):
            return "", "private-auth-value"
    monkeypatch.setattr(lc.subprocess, "Popen", Process)
    with pytest.raises(RuntimeError) as exc:
        make_client(monkeypatch).create(model="test", messages=[])
    assert "private-auth-value" not in str(exc.value)


def test_failed_cli_preserves_model_error_without_credentials():
    raw = json.dumps(
        {
            "type": "turn.failed",
            "error": {
                "message": "Model unavailable; api_key=private-value Bearer private-bearer sk-secret"
            },
        }
    )
    detail = lc._failure_detail(raw, "")
    assert "Model unavailable" in detail
    assert not any(
        secret in detail for secret in ("private-value", "private-bearer", "sk-secret")
    )


def test_failed_cli_preserves_explicit_transport_error():
    assert (
        lc._failure_detail("", "noise\nError: connection reset")
        == "Error: connection reset"
    )


def test_api_remains_default_and_requires_key(monkeypatch):
    monkeypatch.delenv("DRP_LLM_TRANSPORT", raising=False)
    monkeypatch.delenv("DRP_TEST_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DRP_TEST_KEY"):
        lc.create_llm_client({"api_key_env": "DRP_TEST_KEY"})


def test_api_options_are_preserved(monkeypatch):
    import openai
    monkeypatch.delenv("DRP_LLM_TRANSPORT", raising=False)
    monkeypatch.setenv("DRP_TEST_KEY", "test-key")
    monkeypatch.setenv("DRP_TEST_URL", "https://example.invalid/v1")
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: kwargs)
    options = lc.create_llm_client({"api_key_env": "DRP_TEST_KEY",
                                    "base_url": "DRP_TEST_URL", "timeout": 5})
    assert options == {"api_key": "test-key", "base_url": "https://example.invalid/v1",
                       "timeout": 5, "max_retries": 0}


def test_environment_transport_overrides_config(monkeypatch):
    monkeypatch.setenv("DRP_LLM_TRANSPORT", "codex")
    marker = object()
    monkeypatch.setattr(lc, "CodexClient", lambda config: marker)
    assert lc.create_llm_client({"transport": "api"}) is marker


def test_no_llm_never_constructs_transport(monkeypatch):
    monkeypatch.setenv("DRP_NO_LLM", "1")
    def unexpected(_config):
        raise AssertionError("transport must not be constructed")
    monkeypatch.setattr(common, "create_llm_client", unexpected)
    assert common.call_llm("test", {"llm": {}}) is None
