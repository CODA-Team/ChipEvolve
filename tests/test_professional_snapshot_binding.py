"""A shared producer run does not make two physical checkpoints interchangeable."""

import hashlib
import json

import pytest

from chip_evolve.command_requests import RunCommand
from chip_evolve.config import read, write
from chip_evolve.contracts import SpecialistReply
from chip_evolve.professional import execute
from tests.test_query_objective_handoff import inputs


def prepare(tmp_path, monkeypatch, capability, snapshot):
    deployment, source, _ = inputs(tmp_path)
    frame = read(source)
    packet = {
        "schema_version": "chip-evolve.design-context.v1",
        "context_id": "pending",
        "confirmed_facts": [{"text": "Scoped checkpoint fact", "evidence_ids": ["e"]}],
        "evidence": [
            {
                "evidence_id": "e",
                "scope": {
                    "design_id": "gcd",
                    "run_id": frame["run_id"],
                    "snapshot_id": snapshot,
                },
                "locator": {"uri": "artifact://fact"},
                "source_hash": "a" * 64,
            }
        ],
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
    from tests.test_professional_handoff_contract import registered_source

    client, _ = registered_source(tmp_path, frame)
    write(source, frame)
    monkeypatch.setattr("chip_evolve.jobs.KernelClient", lambda *a, **kw: client)
    dispatched = []

    def run(*args):
        dispatched.append(args[3])
        return SpecialistReply(capability, args[3], "delivered")

    for target in (
        "chip_evolve.flow.run_flow",
        "chip_evolve.dpl.run_dpl",
        "chip_evolve.goal.run_goal",
        "chip_evolve.eco.run_eco",
    ):
        monkeypatch.setattr(target, run)
    args = RunCommand(
        config=deployment.path,
        key="snapshot-dispatch",
        source=source,
        design="gcd",
        objective=None,
        context=context,
        capability=capability,
        seconds=60,
        rounds=1,
        candidates=3 if capability in {"flow", "dpl"} else None,
        operation="evolve",
    ).normalized()
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
    assert dispatched == [frame.output]
    assert (
        read(experiment / "input-receipt.json")["source_run_id"] == frame.output.run_id
    )
    assert args.source.read_bytes() == source_bytes
