"""Codex subscription transport; the investigation application executes actions."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from query_agent.domain.errors import LLMContractError
from query_agent.ports.llm import OutputModel


def strict_schema(value: Any) -> Any:
    """Make model-object fields explicit for the CLI's structured output mode."""
    if isinstance(value, list):
        return [strict_schema(item) for item in cast(list[Any], value)]
    if not isinstance(value, dict):
        return value
    result = {
        key: strict_schema(item)
        for key, item in cast(dict[str, Any], value).items()
        if key != "default"
    }
    if result.get("type") == "object" and "properties" in result:
        result["additionalProperties"] = False
        result["required"] = list(result["properties"])
    return result


class CodexModel:
    def set_timeout(self, seconds: float) -> None:
        self.timeout = max(0.1, seconds)

    def __init__(
        self, *, trace_root: Path, timeout: float = 120, executable: str = "codex"
    ) -> None:
        resolved = shutil.which(executable)
        if resolved is None:
            raise LLMContractError("Codex executable is not installed")
        self.executable, self.trace_root, self.timeout = resolved, trace_root, timeout
        self.last_receipt: dict[str, Any] | None = None

    def complete(self, prompt: str, response_model: type[OutputModel]) -> OutputModel:
        folder = self.trace_root / uuid.uuid4().hex
        folder.mkdir(parents=True)
        schema = folder / "schema.json"
        schema.write_text(json.dumps(strict_schema(response_model.model_json_schema())))
        instructions = (
            "Use only the supplied context. Do not use terminal, file, network "
            "or MCP tools. Propose actions in the requested schema; the application "
            "will validate and execute them.\n\n" + prompt
        )
        (folder / "prompt.txt").write_text(instructions)
        command = [
            self.executable,
            "exec",
            "--ignore-user-config",
            "--ephemeral",
            "--skip-git-repo-check",
            "-C",
            str(folder.resolve()),
            "-s",
            "read-only",
            "-m",
            "gpt-6.1-sol",
            "-c",
            'model_reasoning_effort="medium"',
            "-c",
            'approval_policy="never"',
            "--json",
            "--output-schema",
            str(schema.resolve()),
            "--output-last-message",
            str((folder / "answer.json").resolve()),
            "-",
        ]
        (folder / "invocation.json").write_text(json.dumps(command, indent=2))
        started = time.monotonic()
        timed_out = False
        with (
            (folder / "events.jsonl").open("w") as events,
            (folder / "stderr.txt").open("w") as errors,
        ):
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=events,
                stderr=errors,
                text=True,
                start_new_session=True,
            )
            try:
                process.communicate(instructions, timeout=self.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        usage: dict[str, Any] = {}
        tool_actions: list[dict[str, Any]] = []
        for line in (folder / "events.jsonl").read_text().splitlines():
            event = cast(dict[str, Any], json.loads(line))
            if event.get("type") == "turn.completed":
                usage = event.get("usage", {})
            item = event.get("item", {})
            if event.get("type") == "item.completed" and item.get("type") in (
                "command_execution",
                "mcp_tool_call",
                "web_search",
            ):
                tool_actions.append(item)
        self.last_receipt = {
            "model": "gpt-6.1-sol",
            "reasoning_effort": "medium",
            "usage": usage,
            "seconds": time.monotonic() - started,
            "exit_code": process.returncode,
            "timed_out": timed_out,
            "tool_actions": tool_actions,
            "trace": str(folder.resolve()),
            "cash_cost_usd": None,
            "billing": "Codex subscription",
        }
        (folder / "receipt.json").write_text(json.dumps(self.last_receipt, indent=2))
        if timed_out or process.returncode or tool_actions:
            raise LLMContractError(
                "Codex failed, timed out or bypassed the action port; see trace"
            )
        try:
            return response_model.model_validate_json(
                (folder / "answer.json").read_text()
            )
        except (OSError, ValidationError) as exc:
            raise LLMContractError(
                "Codex returned no schema-valid answer; see trace"
            ) from exc
