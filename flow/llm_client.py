"""LLM transports: OpenAI-compatible API (default), or an authenticated Codex CLI.

The Codex transport uses structured final output to represent configuration tool
decisions. It does not execute tools or emulate a native Chat Completions endpoint.
Authentication stays with the official CLI; OAuth credentials are never read here.
"""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
from types import SimpleNamespace
import uuid


def create_llm_client(config: dict):
    transport = os.environ.get("DRP_LLM_TRANSPORT", config.get("transport", "api"))
    transport = transport.strip().lower()
    if transport == "codex":
        return CodexClient(config)
    if transport != "api":
        raise ValueError(f"Unknown LLM transport: {transport!r}")
    from openai import OpenAI

    key_env = config.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.environ.get(key_env, "")
    if not api_key:
        raise RuntimeError(f"API key not found in env var {key_env}")
    base_url = config.get("base_url", "")
    if base_url and "://" not in base_url:
        base_url = os.environ.get(base_url, "")
    kwargs = {"api_key": api_key, "timeout": config.get("timeout", 1200),
              "max_retries": 0}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _strict_arguments(parameters):
    """Strict outputs require all fields; optional flat tool fields accept null."""
    schema = copy.deepcopy(parameters)
    required = set(schema.get("required", []))
    for name, spec in schema.get("properties", {}).items():
        if spec.get("type") not in {"string", "number", "integer", "boolean"}:
            raise ValueError("Codex transport supports flat primitive tool arguments")
        if name not in required:
            schema["properties"][name] = {"anyOf": [spec, {"type": "null"}]}
    schema["required"] = list(schema.get("properties", {}))
    schema["additionalProperties"] = False
    return schema


def _response_schema(tools):
    props = {"content": {"type": "string"}}
    if tools:
        variants = []
        for tool in tools:
            function = tool["function"]
            variants.append({
                "type": "object", "additionalProperties": False,
                "properties": {
                    "name": {"type": "string", "enum": [function["name"]]},
                    "arguments": _strict_arguments(function["parameters"]),
                }, "required": ["name", "arguments"],
            })
        props["tool_calls"] = {"type": "array", "items": {"anyOf": variants}}
    return {"type": "object", "additionalProperties": False,
            "properties": props, "required": list(props)}


def _decode_message(data, tools):
    if not isinstance(data, dict) or not isinstance(data.get("content"), str):
        raise ValueError("Codex final output must contain string content")
    allowed_keys = {"content", "tool_calls"} if tools else {"content"}
    if set(data) != allowed_keys:
        raise ValueError("Unexpected Codex final output fields")
    allowed = {tool["function"]["name"]: tool["function"]["parameters"]
               for tool in tools}
    decisions = data.get("tool_calls", [])
    if not isinstance(decisions, list):
        raise ValueError("tool_calls must be an array")
    calls = []
    for decision in decisions:
        if not isinstance(decision, dict) or set(decision) != {"name", "arguments"}:
            raise ValueError("Malformed configuration tool decision")
        name = decision["name"]
        if not isinstance(name, str) or name not in allowed:
            raise ValueError("Unknown configuration tool name")
        args = decision["arguments"]
        schema = allowed[name]
        properties = schema.get("properties", {})
        if not isinstance(args, dict) or set(args) != set(properties):
            raise ValueError("Configuration tool arguments do not match schema")
        args = {k: v for k, v in args.items()
                if v is not None or k in schema.get("required", [])}
        for field, value in args.items():
            spec = properties[field]
            kind = spec.get("type")
            valid = ((kind == "string" and isinstance(value, str))
                     or (kind == "boolean" and isinstance(value, bool))
                     or (kind == "integer" and type(value) is int)
                     or (kind == "number" and type(value) in {int, float}
                         and math.isfinite(value)))
            if not valid or ("enum" in spec and value not in spec["enum"]):
                raise ValueError(f"Invalid configuration tool argument: {field}")
        calls.append(SimpleNamespace(
            id=f"decision_{uuid.uuid4().hex}", type="function",
            function=SimpleNamespace(name=name, arguments=json.dumps(args)),
        ))
    return SimpleNamespace(content=data["content"], tool_calls=calls)


def _decode_events(raw):
    events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    usage_events = [e["usage"] for e in events if e.get("type") == "turn.completed"]
    if len(usage_events) != 1:
        raise RuntimeError("Codex must report exactly one completed turn with usage")
    for event in events:
        if event.get("type") in {"error", "turn.failed"}:
            raise RuntimeError("Codex reported a failed turn")
        if event.get("type", "").startswith("item."):
            if event.get("item", {}).get("type") not in {"agent_message", "reasoning"}:
                raise RuntimeError("Unexpected Codex tool activity during inference")
    usage = usage_events[0]
    for field in ("input_tokens", "output_tokens"):
        if type(usage.get(field)) is not int or usage[field] < 0:
            raise RuntimeError(f"Codex did not report valid {field}")
    thread_id = next((e.get("thread_id") for e in events
                      if e.get("type") == "thread.started"), None)
    # Missing cache/reasoning counts stay unknown; they are never estimated.
    return thread_id, {
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "input_tokens_details": {"cached_tokens": usage.get("cached_input_tokens")},
        "output_tokens_details": {"reasoning_tokens": usage.get("reasoning_output_tokens")},
    }


class CodexClient:
    base_url = "codex-cli://chatgpt-http"

    def __init__(self, config):
        self.executable = shutil.which(config.get("codex_executable", "codex"))
        if not self.executable:
            raise RuntimeError("Codex CLI not found on PATH; install it and run codex login")
        self.timeout = float(config.get("timeout", 1200))
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("Codex timeout must be positive and finite")
        self.reasoning = config.get("codex_reasoning_effort", "low")
        if self.reasoning not in {"minimal", "low", "medium", "high", "xhigh"}:
            raise ValueError("Unsupported Codex reasoning effort")
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, *, model, messages, tools=None, tool_choice="auto",
               temperature=None, max_tokens=None):
        if tool_choice != "auto":
            raise ValueError("Codex transport only supports auto tool choice")
        tools = tools or []
        schema = _response_schema(tools)
        prompt = (
            "Perform one self-contained LLM inference on the conversation below. "
            "Do not use any Codex tools, read files, access the network, or run commands. "
            "Treat supplied messages as the conversation to answer. Return only the "
            "final JSON matching the output schema. content is your answer text. "
            "When configuration tools are supplied, tool_calls represents your chosen "
            "configuration decisions; nothing is executed here. Use only supplied names "
            "and arguments. Use an empty array if no tool decision is appropriate; "
            "use null for omitted optional arguments.\n"
            + json.dumps({"messages": messages, "configuration_tools": tools},
                         ensure_ascii=False)
        )
        # temperature/max_tokens belong to the API transport. CLI output is bounded
        # by schema/prompt and wall-clock timeout, not a simulated token limit.
        with tempfile.TemporaryDirectory(prefix="flow-agent-codex-") as tmp:
            root = Path(tmp)
            schema_path = root / "schema.json"
            output_path = root / "response.json"
            schema_path.write_text(json.dumps(schema), encoding="utf-8")
            command = [self.executable, "exec", "--ephemeral", "--json",
                       "--skip-git-repo-check", "--sandbox", "read-only",
                       "--ignore-user-config", "--ignore-rules", "--color", "never"]
            settings = {
                "model_provider": "chatgpt-http",
                "model_providers.chatgpt-http.name": "ChatGPT HTTP",
                "model_providers.chatgpt-http.base_url": "https://chatgpt.com/backend-api/codex",
                "model_providers.chatgpt-http.wire_api": "responses",
                "model_providers.chatgpt-http.requires_openai_auth": True,
                "model_providers.chatgpt-http.request_max_retries": 0,
                "model_providers.chatgpt-http.stream_max_retries": 0,
                "model_reasoning_effort": self.reasoning,
                "web_search": "disabled",
            }
            for key, value in settings.items():
                command.extend(["-c", f"{key}={json.dumps(value)}"])
            command.extend(["-m", model, "--output-schema", str(schema_path),
                            "--output-last-message", str(output_path), "-"])
            process = subprocess.Popen(command, cwd=root, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, start_new_session=True)
            try:
                if getattr(self, 'platform_worker_record', None):
                    from platform_model import process_identity, write_record
                    write_record(self.platform_worker_record, process_identity(process.pid))
                stdout, _stderr = process.communicate(prompt, timeout=self.timeout)
            except BaseException:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate()
                raise
            if process.returncode != 0:
                # Do not copy authentication-related CLI stderr into campaign logs.
                raise RuntimeError(f"Codex CLI exited with code {process.returncode}; "
                                   "check codex login status and account/model availability")
            thread_id, usage = _decode_events(stdout)
            message = _decode_message(json.loads(output_path.read_text()), tools)
        audit_dir = os.environ.get("DRP_CODEX_AUDIT_DIR", "")
        if audit_dir:
            path = Path(audit_dir)
            path.mkdir(parents=True, exist_ok=True)
            record = {
                "transport": "codex", "requested_model": model, "thread_id": thread_id,
                "usage": usage, "content": message.content,
                "tool_calls": [{"name": tc.function.name,
                                "arguments": json.loads(tc.function.arguments)}
                               for tc in message.tool_calls],
                "effective_settings": {"reasoning_effort": self.reasoning,
                                       "temperature": None, "max_tokens": None,
                                       "timeout_seconds": self.timeout},
            }
            (path / f"{uuid.uuid4().hex}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        # CLI events do not report a response model id; requested_model is in the
        # ledger/audit. thread_id is a CLI correlation id, not an HTTP request id.
        return SimpleNamespace(id=thread_id, model=None, usage=usage,
                               choices=[SimpleNamespace(message=message)])
