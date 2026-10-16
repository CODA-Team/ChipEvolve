"""An existing Codex host can discover act contracts without a service or model."""

from __future__ import annotations

import json

import pytest

from query_agent.domain.investigation import InvestigationDecision
from query_agent.interfaces.cli import main


def test_decision_schema_requires_no_investigation_model_or_service(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Schema discovery must not create runtime services")

    monkeypatch.setattr("query_agent.interfaces.investigation_cli.service", forbidden)
    monkeypatch.setattr("query_agent.interfaces.cli._service", forbidden)
    assert main(["decision-schema"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == InvestigationDecision.model_json_schema()
    assert {"read", "answer"}.issubset(result["properties"]["action"]["enum"])


def test_decision_schema_is_discoverable_in_top_level_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    assert "decision-schema" in capsys.readouterr().out
