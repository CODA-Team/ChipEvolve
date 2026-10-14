import hashlib
import json

import pytest
from eda_toolkits.context import (
    append_context,
    bind_task_context,
    context_messages,
    load_context,
)


def context(tmp_path):
    value = {
        "schema_version": "chip-evolve.design-context.v1",
        "scope": {"design_id": "second", "snapshot_id": "snapshot"},
        "confirmed_facts": [
            {"text": "A sampled path regressed", "evidence_ids": ["e1"]}
        ],
        "hypotheses": [
            {"explanation": "fanout may explain the delay", "status": "unverified"}
        ],
        "evidence": [{"evidence_id": "e1", "source_hash": "a" * 64}],
        "limitations": ["sampled timing only"],
    }
    value["context_id"] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / "context.json"
    path.write_text(json.dumps(value))
    return path, value


def test_actual_prompt_retains_evidence_hypothesis_and_original_request(
    tmp_path, monkeypatch
):
    path, value = context(tmp_path)
    monkeypatch.setenv("EDA_PLATFORM_CONTEXT", str(path))
    prompt = append_context("native professional contract")
    assert prompt.startswith("native professional contract")
    assert "unverified" in prompt and "e1" in prompt and "sampled timing only" in prompt
    payload = {"messages": [{"role": "user", "content": "native"}]}
    actual = context_messages(payload)
    assert len(payload["messages"]) == 1
    assert value["context_id"] in actual["messages"][-1]["content"]
    spec = {"design_id": "second", "labels": {}, "inputs": {}, "staged_inputs": []}
    bind_task_context(spec)
    assert spec["labels"]["design_context_id"] == value["context_id"]
    spec["design_id"] = "other"
    with pytest.raises(ValueError, match="another design"):
        bind_task_context(spec)
    value["confirmed_facts"][0]["text"] = "unsupported cause"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="context changed"):
        load_context(path)
