"""Flow terminal admission and locking belong to the delivery owner."""

import os
from contextlib import contextmanager
from pathlib import Path

import pytest
from openroad_platform_client import KernelClient

from chip_evolve import flow, flow_delivery, flow_evidence
from chip_evolve.candidates import deliver_candidates
from chip_evolve.config import business_lock, read, write
from chip_evolve.contracts import BusinessInputError
from chip_evolve.result_io import load_physical_result
from tests.test_business_contracts import result_file
from tests.test_local_business import deployment


def prepare(tmp_path, monkeypatch):
    d = deployment(tmp_path)
    d.value["designs"]["gcd"] = {"platform": "pdk", "nickname": "gcd"}
    experiment = d.experiment("gcd", "flow-test")
    source = result_file(tmp_path / "measured")
    goal = load_physical_result(source).objective
    summary = experiment / "source/flow/backup_dir/pdk/gcd/llm_usage_summary.json"
    write(
        summary,
        {
            "status": "completed",
            "exit_code": 0,
            "campaign_id": "campaign",
            "completed_iterations": 1,
        },
    )
    write(
        experiment / "platform-state/campaign.json",
        {"campaign_id": "campaign", "owner": {"pid": 1073741824, "start_ticks": "1"}},
    )
    calls = []

    def deliver(
        deployment, design_id, root, objective, *, output=None, native_campaign=None
    ):
        target = output or root
        target.mkdir(exist_ok=True)
        calls.append((target, native_campaign))
        return deliver_candidates(target, [source], native_campaign=native_campaign)

    monkeypatch.setattr(flow_delivery, "_deliver_candidates", deliver)
    monkeypatch.setattr(
        KernelClient,
        "submit",
        lambda *a, **kw: pytest.fail("terminal gate submitted EDA"),
    )
    return d, experiment, goal, summary, calls


@pytest.mark.parametrize("status", ["completed", "early_stop"])
def test_completed_collection_keeps_the_legacy_wire_and_nested_business_lock(
    tmp_path, monkeypatch, status
):
    d, exp, goal, summary, calls = prepare(tmp_path, monkeypatch)
    wire = read(summary)
    wire["status"] = status
    write(summary, wire)
    with business_lock(exp):
        result = flow_delivery.collect_completed(d, "gcd", exp, goal)
    assert result.execution_state == "succeeded" and len(result.candidates) == 1
    assert calls == [(exp, None)]
    assert flow.recover_config is flow_delivery.recover_config
    assert flow.collect_flow(d, "gcd", exp, goal.path) == read(exp / "result.json")


@pytest.mark.parametrize(
    "status,code",
    [("running", None), ("failed", 1), ("completed", 1), ("completed", True)],
)
def test_success_api_rejects_non_success_terminal_before_delivery(
    tmp_path, monkeypatch, status, code
):
    d, exp, goal, summary, calls = prepare(tmp_path, monkeypatch)
    write(summary, {"status": status, "exit_code": code})
    with pytest.raises(BusinessInputError):
        flow_delivery.collect_completed(d, "gcd", exp, goal)
    assert calls == [] and not (exp / "result.json").exists()


def test_failed_search_keeps_evidence_only_and_lock_order(tmp_path, monkeypatch):
    d, exp, goal, summary, calls = prepare(tmp_path, monkeypatch)
    wire = read(summary)
    wire.update(status="failed", exit_code=2)
    write(summary, wire)
    order = []

    @contextmanager
    def locked(path):
        order.append(path)
        with business_lock(path):
            yield

    monkeypatch.setattr(flow_delivery, "business_lock", locked)
    result = flow_delivery.collect_failed_evidence(d, "gcd", exp, goal)
    assert order == [exp, exp / "flow-delivery-lock"]
    assert result.execution_state == "failed" and result.wire["evidence_only"] is True
    assert (
        result.wire["native_search_completed"] is False
        and result.wire["adopted"] is False
    )
    assert calls[0][0] == exp / "completed-evidence"
    assert flow_evidence.collect(d, "gcd", exp, goal.path) == read(
        exp / "completed-evidence/result.json"
    )


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "missing_cleanup",
        "wrong_pid",
        "wrong_reason",
        "active_owner",
        "wrong_campaign",
    ],
)
def test_timeout_requires_original_matching_completed_cleanup(
    tmp_path, monkeypatch, fault
):
    d, exp, goal, summary, calls = prepare(tmp_path, monkeypatch)
    wire = read(summary)
    wire.update(status="running", exit_code=None)
    write(summary, wire)
    write(exp / "status.json", {"status": "failed", "error_type": "TimeoutExpired"})
    cleanup = {
        "status": "completed",
        "reason": "TimeoutExpired",
        "owner_pid": 1073741824,
    }
    if fault == "wrong_pid":
        cleanup["owner_pid"] = 1
    if fault == "wrong_reason":
        cleanup["reason"] = "KeyboardInterrupt"
    if fault != "missing_cleanup":
        write(exp / "native-frontend-cleanup.json", cleanup)
    if fault == "active_owner":
        ticks = (
            Path(f"/proc/{os.getpid()}/stat").read_text().rsplit(")", 1)[1].split()[19]
        )
        write(
            exp / "platform-state/campaign.json",
            {
                "campaign_id": "campaign",
                "owner": {"pid": os.getpid(), "start_ticks": ticks},
            },
        )
    if fault == "wrong_campaign":
        state = read(exp / "platform-state/campaign.json")
        state["campaign_id"] = "foreign"
        write(exp / "platform-state/campaign.json", state)
    if fault:
        with pytest.raises(ValueError):
            flow_delivery.collect_failed_evidence(d, "gcd", exp, goal)
        assert calls == []
    else:
        result = flow_delivery.collect_failed_evidence(d, "gcd", exp, goal)
        assert (
            result.execution_state == "timed_out"
            and result.wire["evidence_only"] is True
        )


@pytest.mark.parametrize("entry", ["completed", "failed"])
def test_concurrent_collection_fails_before_delivery_and_releases_outer_lock(
    tmp_path, monkeypatch, entry
):
    d, exp, goal, summary, calls = prepare(tmp_path, monkeypatch)
    if entry == "failed":
        wire = read(summary)
        wire.update(status="failed", exit_code=1)
        write(summary, wire)
    lock = exp / "flow-delivery-lock"
    lock.mkdir()
    with business_lock(lock):
        with pytest.raises(RuntimeError, match="active business driver"):
            getattr(
                flow_delivery,
                "collect_"
                + ("completed" if entry == "completed" else "failed_evidence"),
            )(d, "gcd", exp, goal)
    with business_lock(exp):
        pass
    assert calls == []
