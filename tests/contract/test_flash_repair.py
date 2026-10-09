"""Bad structured output may get one bounded repair; paid failures remain visible."""

import io
import json
import urllib.request
from pathlib import Path
from typing import Literal, cast

import pytest
from pydantic import BaseModel, ConfigDict, model_validator

from query_agent.adapters.llm.budget import CostLedger
from query_agent.adapters.llm.flash import DeepSeekFlashModel
from query_agent.domain.errors import LLMContractError


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["answer"]
    fact: str

    @model_validator(mode="after")
    def observed_fact(self) -> "Answer":
        if not self.fact:
            raise ValueError("fact must contain an observation")
        return self


def model(tmp_path: Path) -> DeepSeekFlashModel:
    secret = tmp_path / "secret.json"
    secret.write_text(
        json.dumps({"models": [{"label": "test", "key": "synthetic-test-key"}]})
    )
    secret.chmod(0o600)
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "secret_file": str(secret),
                "base_url": "https://api.deepseek.com",
                "models": [{"label": "test", "model": "deepseek-flash"}],
            }
        )
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({"limits": {"deepseek-flash": 1}, "settled": {}, "reservations": []})
    )
    return DeepSeekFlashModel(
        config=config,
        ledger=CostLedger(ledger),
        trace_root=tmp_path / "traces",
        timeout=30,
    )


def response(content: str, finish: str = "stop") -> io.BytesIO:
    return io.BytesIO(
        json.dumps(
            {
                "model": "deepseek-flash",
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                "choices": [{"finish_reason": finish, "message": {"content": content}}],
            }
        ).encode()
    )


@pytest.mark.parametrize("second", ["valid", "invalid", "network"])
@pytest.mark.parametrize("failure", ["extra_field", "domain_validator"])
def test_schema_repair_preserves_both_responses_and_actual_cost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, second: str, failure: str
) -> None:
    client = model(tmp_path)
    calls: list[tuple[bytes, float]] = []
    bad = (
        '{"action":"answer","fact":"observed -0.2 ns","extra":true}'
        if failure == "extra_field"
        else '{"action":"answer","fact":""}'
    )

    def send(request: urllib.request.Request, *, timeout: float) -> io.BytesIO:
        calls.append((cast(bytes, request.data), timeout))
        if len(calls) == 1:
            return response(bad)
        if second == "network":
            raise OSError("connection unavailable")
        return response(
            '{"action":"answer","fact":"observed -0.2 ns"}'
            if second == "valid"
            else bad
        )

    monkeypatch.setattr(urllib.request, "urlopen", send)
    if second == "valid":
        assert (
            client.complete("Evidence: observed -0.2 ns", Answer).fact
            == "observed -0.2 ns"
        )
    else:
        with pytest.raises(LLMContractError):
            client.complete("Evidence: observed -0.2 ns", Answer)
    assert len(calls) == 2
    assert calls[1][1] <= calls[0][1]
    assert bad in json.loads(calls[1][0])["messages"][1]["content"]
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert len(ledger["reservations"]) == 2
    assert ledger["reservations"][0]["status"] == "settled"
    assert ledger["reservations"][1]["status"] == (
        "unknown-settlement" if second == "network" else "settled"
    )
    assert len(list((tmp_path / "traces").glob("*/response.json"))) == (
        1 if second == "network" else 2
    )
    assert client.last_receipt is not None
    assert len(client.last_receipt["attempts"]) == 2
    assert client.last_receipt["actual_usd"] == (
        None if second == "network" else ledger["settled"]["deepseek-flash"]
    )
    assert client.timeout == 30


def test_truncated_response_is_not_retried_as_a_schema_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = model(tmp_path)
    calls: list[urllib.request.Request] = []

    def send(request: urllib.request.Request, *, timeout: float) -> io.BytesIO:
        calls.append(request)
        return response('{"action":', "length")

    monkeypatch.setattr(urllib.request, "urlopen", send)
    with pytest.raises(LLMContractError):
        client.complete("Evidence", Answer)
    assert len(calls) == 1
    assert client.last_receipt and client.last_receipt["finish_reason"] == "length"
