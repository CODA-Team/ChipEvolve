"""Small MCP stdio client for a configured, independently installed server.

The transport forwards no credentials in arguments or protocol messages.
It starts the configured launcher, which owns provider authentication.
"""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast


class JudgmentTransportError(RuntimeError):
    """Server startup, protocol, timeout, or remote tool failure."""


class StdioJudgmentClient:
    """One persistent server process; synchronous, bounded tool calls."""

    def __init__(self, command: list[str], *, timeout: float = 60) -> None:
        self.command = command
        self.timeout = timeout
        self._process: subprocess.Popen[bytes] | None = None
        self._buffer = b""
        self._sequence = 0

    def __enter__(self) -> StdioJudgmentClient:
        self._process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        try:
            self._request(
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "eda-query-agent", "version": "0.3.0"},
                },
            )
            self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except Exception:
            self.__exit__()
            raise
        return self

    def __exit__(self, *_: object) -> None:
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            for stream in (self._process.stdin, self._process.stdout):
                if stream is not None:
                    stream.close()
            self._process = None

    def call(self, tool: str, arguments: Mapping[str, object]) -> dict[str, Any]:
        result = self._request("tools/call", {"name": tool, "arguments": arguments})
        if result.get("isError"):
            raise JudgmentTransportError(json.dumps(result, ensure_ascii=False))
        return result

    def tools(self) -> dict[str, Any]:
        return self._request("tools/list", {})

    def _send(self, payload: Mapping[str, object]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise JudgmentTransportError("judgment server is not connected")
        try:
            process.stdin.write((json.dumps(payload) + "\n").encode())
        except BrokenPipeError as exc:
            raise JudgmentTransportError("judgment server closed its input") from exc
        process.stdin.flush()

    def _request(self, method: str, params: Mapping[str, object]) -> dict[str, Any]:
        self._sequence += 1
        request_id = self._sequence
        self._send(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        )
        process = self._process
        assert process is not None and process.stdout is not None
        deadline = time.monotonic() + self.timeout
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                while b"\n" not in self._buffer:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise JudgmentTransportError(f"judgment {method} timed out")
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        raise JudgmentTransportError(
                            "judgment server closed its output"
                        )
                    self._buffer += chunk
                    if len(self._buffer) > 16 * 1024 * 1024:
                        raise JudgmentTransportError(
                            "judgment response exceeds transport limit"
                        )
                line, self._buffer = self._buffer.split(b"\n", 1)
                try:
                    payload = json.loads(line)
                except (ValueError, UnicodeError) as exc:
                    raise JudgmentTransportError(
                        "judgment response is invalid JSON"
                    ) from exc
                if not isinstance(payload, dict):
                    raise JudgmentTransportError(
                        "judgment response is not a JSON-RPC object"
                    )
                if time.monotonic() >= deadline:
                    raise JudgmentTransportError(f"judgment {method} timed out")
                payload = cast(dict[str, Any], payload)
                if payload.get("id") != request_id:
                    continue
                if "error" in payload:
                    raise JudgmentTransportError(json.dumps(payload["error"]))
                result = payload.get("result")
                if not isinstance(result, dict):
                    raise JudgmentTransportError("judgment response is not an object")
                return cast(dict[str, Any], result)


def main() -> None:
    """Protocol probe; full response goes only to the supplied evidence file."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--launcher", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    request = json.loads(args.input.read_text())
    start = time.monotonic()
    outcome: dict[str, Any] = {}
    try:
        with StdioJudgmentClient([args.launcher]) as client:
            outcome = client.call(request["tool"], request["arguments"])
        status = "succeeded"
    except (JudgmentTransportError, OSError) as exc:
        outcome = {"error": str(exc)}
        status = "failed"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {"status": status, "seconds": time.monotonic() - start, "result": outcome},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({"status": status, "output": os.fspath(args.output)}))
    if status != "succeeded":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
