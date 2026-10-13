"""Source optimization consumes a scoped data handoff, without native fallback."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from goalevolve.platform.execution import design_context


def test_data_handoff_is_scoped_and_failure_is_explicit(monkeypatch):
    assert design_context({}) is None
    client = MagicMock()
    factory = MagicMock(return_value=client)
    monkeypatch.setitem(
        sys.modules, "eda_ai_client", SimpleNamespace(EdaAiClient=factory)
    )
    profile = {
        "kernel_url": "http://localhost:2",
        "data_context": {
            "data_url": "http://localhost:1",
            "snapshot_id": "s",
            "metrics_snapshot_id": "m",
            "parent_run_id": "r",
        },
    }
    result = design_context(profile)
    assert result["parent_run_id"] == "r"
    client.resolve_scope.assert_called_once_with(snapshot_id="s")
    client.get_metrics.assert_called_once_with(snapshot_id="m")
    client.resolve_scope.side_effect = RuntimeError("missing snapshot")
    with pytest.raises(RuntimeError, match="missing snapshot"):
        design_context(profile)
