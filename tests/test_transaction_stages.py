"""Business stages expose their I/O, admission order and immutable input boundary."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from openroad_platform_client import KernelClient

from chip_evolve import commands, professional, goal, eco
from chip_evolve.command_requests import RunCommand
from chip_evolve.config import read, write
from chip_evolve.contracts import BusinessInputError
from tests.test_professional_snapshot_binding import prepare
from tests.test_code_candidate_delivery import inputs, collect


@pytest.mark.parametrize("capability", ["flow", "dpl", "goal", "eco"])
def test_professional_inspection_is_read_only_before_creating_a_new_experiment(
    tmp_path, monkeypatch, capability
):
    d, args, _, _ = prepare(tmp_path, monkeypatch, capability, "db")
    args = replace(args, key="inspect-only")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}

    def forbidden(*a, **kw):
        pytest.fail("preflight performed execution/preparation")

    monkeypatch.setattr(KernelClient, "submit", forbidden)
    monkeypatch.setattr("chip_evolve.design_facts.ensure", forbidden)
    monkeypatch.setattr("chip_evolve.diagnosis.diagnose", forbidden)
    monkeypatch.setattr("chip_evolve.native_process.invoke", forbidden)
    checked = professional.inspect_inputs(d, args)
    assert checked.source.design_id == checked.request.design == "gcd"
    assert checked.context is not None
    assert not (d.state / "experiments/gcd/inspect-only").exists()
    assert all(p.read_bytes() == raw for p, raw in before.items())


@pytest.mark.parametrize("changed", ["source", "context", "objective"])
def test_input_changed_after_preflight_rejects_before_materialization(
    tmp_path, monkeypatch, changed
):
    d, args, exp, _ = prepare(tmp_path, monkeypatch, "dpl", "db")
    checked = professional.inspect_inputs(d, args)
    target = {
        "source": checked.source.origin.path,
        "context": checked.context.path,
        "objective": checked.objective.path,
    }[changed]
    target.write_bytes(target.read_bytes() + b" ")
    calls = []
    monkeypatch.setattr(
        "chip_evolve.design_facts.ensure",
        lambda *a, **kw: calls.append(a) or pytest.fail("materialized changed input"),
    )
    monkeypatch.setattr(
        KernelClient, "submit", lambda *a, **kw: pytest.fail("submitted changed input")
    )
    with pytest.raises(BusinessInputError, match="changed_input"):
        professional.prepare_inputs(d, checked, exp)
    assert calls == [] and not (exp / "handoff-input.json").exists()


def test_commands_follow_inspection_open_prepare_dispatch_order(
    tmp_path, monkeypatch, capsys
):
    d, args, _, _ = prepare(tmp_path, monkeypatch, "dpl", "db")
    order = []
    for name in ["inspect_inputs", "prepare_inputs", "dispatch_prepared"]:
        original = getattr(professional, name)

        def traced(*values, _name=name, _original=original):
            order.append(_name)
            return _original(*values)

        monkeypatch.setattr(professional, name, traced)
    original_open = d.experiment

    def open_run(*values):
        order.append("open")
        assert order == ["inspect_inputs", "open"]
        return original_open(*values)

    monkeypatch.setattr(d, "experiment", open_run)
    command = RunCommand(
        d.path,
        "gcd",
        "stages",
        "dpl",
        source=args.source,
        context=args.context,
        seconds=60,
    )
    assert commands.run_experiment(d, command) == 0
    assert order == ["inspect_inputs", "open", "prepare_inputs", "dispatch_prepared"]
    assert json.loads(capsys.readouterr().out)["run_id"] == read(args.source)["run_id"]
    assert read(d.state / "experiments/gcd/stages/request.json")["seconds"] == 60


def test_adapter_selection_reads_current_owner_without_coupling_other_specialists(
    monkeypatch,
):
    other = eco.run_eco

    def changed(*args):
        raise AssertionError("identity only")

    monkeypatch.setattr(goal, "run_goal", changed)
    assert professional.select_adapter("goal") is changed
    assert professional.select_adapter("eco") is other


def test_late_candidate_identity_fault_prevents_first_additional_measurement(
    tmp_path, monkeypatch
):
    data = inputs(tmp_path, monkeypatch)
    saved = read(data[1] / "delivery-checkpoint.json")
    saved["producer"] = "retained-parent"
    write(data[1] / "delivery-checkpoint.json", saved)
    data[4]["native-1"]["design_id"] = "foreign"
    with pytest.raises(BusinessInputError):
        collect(data)
    assert data[-1] == []


@pytest.mark.parametrize("fault", ["identity", "power_none", "drc_none"])
def test_pending_inventory_checks_all_completed_identities_before_new_eda(
    tmp_path, monkeypatch, fault
):
    data = inputs(tmp_path, monkeypatch)
    saved = read(data[1] / "delivery-checkpoint.json")
    saved["producer"] = "retained-parent"
    write(data[1] / "delivery-checkpoint.json", saved)
    metadata = collect(data)
    index_path = Path(metadata["inventory"]["path"])
    index = read(index_path)
    index["status"] = "pending"
    index["candidates"][0]["status"] = "prepared"
    index["candidates"][0].pop("result")
    completed = index["candidates"][1]["result"]
    result_path = Path(completed["path"])
    result = read(result_path)
    if fault == "identity":
        result["design_id"] = "foreign"
    elif fault == "power_none":
        result["metrics"]["finish__power__total"] = None
    else:
        result["route_drc"] = None
    write(result_path, result)
    from chip_evolve.jobs import digest

    completed["sha256"] = digest(result_path)
    write(index_path, index)
    original_calls = len(data[-1])
    with pytest.raises(BusinessInputError):
        collect(data)
    assert len(data[-1]) == original_calls


def test_cli_notice_retains_failed_native_state_when_evidence_is_delivered(
    tmp_path, monkeypatch, capsys
):
    from chip_evolve.candidates import deliver_candidates
    from chip_evolve.result_io import specialist_reply

    d, args, _, _ = prepare(tmp_path, monkeypatch, "flow", "db")

    def evidence_only(deployment, request, experiment, source, objective, context):
        deliver_candidates(
            experiment, [source.origin.path], native_campaign={"status": "failed"}
        )
        return specialist_reply("flow", experiment / "result.json")

    monkeypatch.setattr("chip_evolve.flow.run_flow", evidence_only)
    assert (
        commands.run_experiment(
            d,
            RunCommand(
                d.path,
                "gcd",
                "evidence",
                "flow",
                source=args.source,
                context=args.context,
            ),
        )
        == 0
    )
    notice = json.loads(capsys.readouterr().out)
    assert (
        notice["execution_state"] == "failed"
        and notice["delivery_state"] == "completed"
    )
    assert read(d.state / "experiments/gcd/evidence/result.json")["adopted"] is False
