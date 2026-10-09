"""Confirmed responses settle the quote; unknown billing never frees capacity."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from query_agent.adapters.judgment.budgeted import BudgetedJudgment
from query_agent.adapters.judgment.stdio import (
    JudgmentTransportError,
    StdioJudgmentClient,
)
from query_agent.adapters.llm.budget import BudgetExceeded, CostLedger


class Server(StdioJudgmentClient):
    def __init__(self, *, fail: bool = False) -> None:
        super().__init__(["unused"])
        self.fail = fail
        self.calls = 0

    def call(self, tool: str, arguments: Mapping[str, object]) -> dict[str, Any]:
        self.calls += 1
        if self.fail:
            raise JudgmentTransportError("provider timed out after request")
        result = {
            "model": "typesafe/jev-1.13-20260917",
            "provider": "openrouter",
            "usage": {"input_tokens": 100, "output_tokens": 20},
            "results": [{"id": "p", "classification": "L2"}],
        }
        return {"content": [{"type": "text", "text": json.dumps(result)}]}


def wrapper(tmp_path: Path, server: Server, *, quoted: bool) -> BudgetedJudgment:
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({"limits": {"jev": 0.1}, "settled": {"jev": 0}, "reservations": []})
    )
    return BudgetedJudgment(
        server,
        ledger=CostLedger(ledger),
        trace_root=tmp_path / "traces",
        pricing={
            "id": "typesafe/jev-1.13",
            "pricing": {"prompt": "0.000000042", "completion": "0"},
        }
        if quoted
        else None,
    )


def test_quoted_usage_is_recorded_and_settled(tmp_path: Path) -> None:
    client = wrapper(tmp_path, Server(), quoted=True)
    result = client.call("jev_classify", {"items": []})
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert result["results"][0]["classification"] == "L2"
    assert ledger["settled"]["jev"] == pytest.approx(0.0000042)
    assert ledger["reservations"][0]["status"] == "settled"
    assert client.last_receipt and client.last_receipt["usage"]["input_tokens"] == 100


@pytest.mark.parametrize("failed", [False, True])
def test_unknown_settlement_blocks_another_paid_request(
    tmp_path: Path,
    failed: bool,
) -> None:
    server = Server(fail=failed)
    client = wrapper(tmp_path, server, quoted=False)
    if failed:
        with pytest.raises(JudgmentTransportError):
            client.call("jev_classify", {"items": []})
    else:
        client.call("jev_classify", {"items": []})
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert ledger["reservations"][0]["status"] == "unknown-settlement"
    with pytest.raises(BudgetExceeded):
        client.call("jev_classify", {"items": []})
    assert server.calls == 1


def test_receipt_failure_retains_reservation_without_double_settlement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = wrapper(tmp_path, Server(), quoted=True)
    original = Path.write_text

    def write(path: Path, data: str, *args: Any, **kwargs: Any) -> int:
        if path.name == "receipt.json":
            raise OSError("receipt disk full")
        return original(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write)
    with pytest.raises(OSError, match="receipt disk full"):
        client.call("jev_classify", {"items": []})
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert ledger["settled"]["jev"] == 0
    assert ledger["reservations"][0]["status"] == "unknown-settlement"
