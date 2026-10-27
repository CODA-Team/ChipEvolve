"""A shared producer run does not make two physical checkpoints interchangeable."""

import hashlib
import json
from argparse import Namespace

import pytest

from admin.test_query_objective_handoff import inputs
from chip_evolve.config import read, write
from chip_evolve.professional import execute


def prepare(tmp_path, monkeypatch, capability, snapshot):
    deployment, source, _ = inputs(tmp_path)
    frame = read(source)
    packet = {
        "schema_version": "chip-evolve.design-context.v1",
        "context_id": "pending",
        "confirmed_facts": [{"text": "Scoped checkpoint fact", "evidence_ids": ["e"]}],
        "evidence": [{"evidence_id": "e"}],
        "scope": {
            "design_id": "gcd",
            "run_id": frame["run_id"],
            "snapshot_id": snapshot,
        },
    }
    packet["context_id"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in packet.items() if key != "context_id"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    context = tmp_path / "context.json"
    write(context, packet)
    monkeypatch.setattr("chip_evolve.handoff.input_contract", lambda *a: {})
    dispatched = []

    def run(*args):
        dispatched.append(args[3])
        return args[3]

    for target in (
        "chip_evolve.professional.run_flow",
        "chip_evolve.professional.run_dpl",
        "chip_evolve.native.run_goal",
        "chip_evolve.native.run_eco",
    ):
        monkeypatch.setattr(target, run)
    args = Namespace(
        source=source,
        design="gcd",
        objective=None,
        context=context,
        capability=capability,
        seconds=60,
        rounds=1,
        candidates=3,
        operation="evolve",
    )
    experiment = deployment.experiment("gcd", "snapshot-dispatch")
    return deployment, args, experiment, dispatched


@pytest.mark.parametrize("capability", ["flow", "dpl", "goal", "eco"])
def test_same_run_other_physical_checkpoint_never_reaches_professional(
    tmp_path, monkeypatch, capability
):
    # Fixture: a producer has both post-power and post-timing states. The source
    # selects the latter, while the frozen Query packet describes the former.
    deployment, args, experiment, dispatched = prepare(
        tmp_path, monkeypatch, capability, "post-power"
    )
    frame = read(args.source)
    frame["snapshot_ids"] = {"opendb": "post-timing"}
    write(args.source, frame)
    source_bytes = args.source.read_bytes()
    with pytest.raises(ValueError, match="snapshot"):
        execute(deployment, args, experiment)
    assert not dispatched
    assert not (experiment / "handoff-input.json").exists()
    assert not (experiment / "input-receipt.json").exists()
    assert args.source.read_bytes() == source_bytes


@pytest.mark.parametrize("capability", ["flow", "dpl", "goal", "eco"])
@pytest.mark.parametrize("snapshot", ["db", "metrics", "timing"])
def test_declared_source_fact_views_remain_usable(
    tmp_path, monkeypatch, capability, snapshot
):
    deployment, args, experiment, dispatched = prepare(
        tmp_path, monkeypatch, capability, snapshot
    )
    source_bytes = args.source.read_bytes()
    frame = execute(deployment, args, experiment)
    assert dispatched == [frame]
    assert read(experiment / "input-receipt.json")["source_run_id"] == frame["run_id"]
    assert args.source.read_bytes() == source_bytes
