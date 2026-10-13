"""Optional official Codex CLI transport; native ECO prompts and loop stay intact."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4


def usage_events(content: str) -> tuple[dict, str | None]:
    usage, session = {}, None
    for line in content.splitlines():
        event = json.loads(line)
        if event.get("type") == "thread.started":
            session = event.get("thread_id")
        if event.get("type") == "turn.completed":
            usage = event["usage"]
    return usage, session


def call_codex(system_prompt: str, user_prompt: str) -> tuple[str, dict]:
    folder = (
        Path(__file__).resolve().parents[1] / "prompts/dynamic/codex_logs" / uuid4().hex
    )
    folder.mkdir(parents=True)
    output = folder / "reply.txt"
    prompt = (
        "Use no tools. Follow the ECO strategy and response format below. "
        "Return the original requested analysis and Tcl sections.\n\n"
        "<eco_strategy>\n" + system_prompt + "\n</eco_strategy>\n"
        "<current_design_context>\n" + user_prompt + "\n</current_design_context>\n"
    )
    (folder / "prompt.txt").write_text(prompt)
    model = os.environ.get("TIMINGECO_CODEX_MODEL", "gpt-6.1-sol")
    command = [
        os.environ.get("TIMINGECO_CODEX_BIN", "codex"),
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--model",
        model,
        "--config",
        'model_reasoning_effort="high"',
        "--output-last-message",
        str(output),
        "-",
    ]
    settings = {
        "model_provider": "chatgpt-http",
        "model_providers.chatgpt-http.name": "ChatGPT HTTP",
        "model_providers.chatgpt-http.base_url": "https://chatgpt.com/backend-api/codex",
        "model_providers.chatgpt-http.wire_api": "responses",
        "model_providers.chatgpt-http.requires_openai_auth": True,
        "model_providers.chatgpt-http.request_max_retries": 0,
        "model_providers.chatgpt-http.stream_max_retries": 0,
        "web_search": "disabled",
    }
    for key, value in settings.items():
        command[2:2] = ["-c", f"{key}={json.dumps(value)}"]
    started = time.monotonic()
    with (folder / "events.jsonl").open("w") as events, (folder / "stderr.log").open(
        "w"
    ) as errors:
        process = subprocess.run(
            command,
            input=prompt,
            text=True,
            stdout=events,
            stderr=errors,
            timeout=float(os.environ.get("TIMINGECO_CODEX_TIMEOUT", "600")),
            check=False,
        )
    if process.returncode:
        raise RuntimeError("Codex ECO transport failed; see " + str(folder))
    usage, session = usage_events((folder / "events.jsonl").read_text())
    reply = output.read_text()
    normalized = {
        "input_tokens": (
            (usage["input_tokens"] - usage.get("cached_input_tokens", 0))
            if "input_tokens" in usage
            else None
        ),
        "output_tokens": usage.get("output_tokens"),
        "cache_read_input_tokens": usage.get("cached_input_tokens"),
        "cache_creation_input_tokens": None,
    }
    meta = {
        "provider": "codex_existing_login",
        "model": model,
        "session_id": session,
        "elapsed_s": time.monotonic() - started,
        "returncode": process.returncode,
        "prompt_chars": len(prompt),
        "system_chars": len(system_prompt),
        "user_chars": len(user_prompt),
        "usage_reported": normalized,
        "codex_usage": usage,
        "total_cost_usd": None,
        "monetary_cost_measured": False,
        "reply_chars": len(reply),
        "codex_events": str(folder / "events.jsonl"),
        "claude_envelope": {"usage": normalized, "result": reply},
    }
    (folder / "receipt.json").write_text(json.dumps(meta, indent=2) + "\n")
    return reply, meta
