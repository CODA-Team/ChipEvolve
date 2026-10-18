"""A stopped native frontend must not leave its declared EF work running."""

import pytest

from admin.native_episode_cleanup import prepare, retire
from admin.run_native_codex_episode import run
from admin.test_native_codex_episode import episode
from chip_evolve.config import Deployment, read, write
from chip_evolve.jobs import Jobs, digest


def configure(spec, tmp_path, keys=("trial-owned", "trial-owned/logic")):
    config = tmp_path / "deployment.json"
    write(
        config,
        {
            "schema_version": "chip-evolve.local.v1",
            "state_root": str(tmp_path / "state"),
            "kernel_url": "http://unit-test-unused",
            "designs": {"gcd": {"platform": "asap7", "nickname": "gcd-native"}},
        },
    )
    value = read(spec)
    value["input_hashes"][str(config)] = digest(config)
    value["platform_timeout_cleanup"] = {
        "config": str(config),
        "experiments": [{"design_id": "gcd", "key": key} for key in keys],
        "settle_seconds": 0.02,
    }
    write(spec, value)
    return config


class Client:
    def __init__(self, rows, *, settle=True, unavailable=False):
        self.rows = {row["run_id"]: row for row in rows}
        self.cancelled = []
        self.settle = settle
        self.unavailable = unavailable

    def runs(self, *, design_id, status, limit, offset):
        if self.unavailable:
            raise OSError("public EF unavailable")
        return [
            row.copy()
            for row in self.rows.values()
            if row["design_id"] == design_id and row["status"] == status
        ][offset : offset + limit]

    def cancel(self, run_id):
        self.cancelled.append(run_id)
        self.rows[run_id]["status"] = "cancel_requested"
        return {"run": self.rows[run_id].copy()}

    def run(self, run_id):
        if self.settle:
            self.rows[run_id]["status"] = "cancelled"
        return self.rows[run_id].copy()


def test_real_frontend_timeout_retires_declared_business_children_and_native_flow_only(
    tmp_path, monkeypatch
):
    owned = tmp_path / "state/experiments/gcd/trial-owned"
    journal = owned / "platform-state/campaign.json"
    body = (
        f"Path({str(owned / 'logic')!r}).mkdir(parents=True)\n"
        f"Path({str(journal.parent)!r}).mkdir()\n"
        f"Path({str(journal)!r}).write_text(json.dumps({{'platform':'asap7','design':'gcd-native','campaign_id':'native-owned'}}))\n"
        "time.sleep(30)\n"
    )
    spec, output = episode(tmp_path, body, seconds=0.5)
    config = configure(spec, tmp_path)
    deployment = Deployment(config)
    rows = []
    for rid, design, campaign, project in [
        ("root", "gcd", Jobs(deployment, "gcd", owned).campaign, "business"),
        ("logic", "gcd", Jobs(deployment, "gcd", owned / "logic").campaign, "business"),
        ("native", "gcd-native", "native-owned", "a2-flow"),
        ("other-project", "gcd-native", "native-owned", "other-project"),
        ("other-trial", "gcd", "different-trial", "business"),
    ]:
        rows.append(
            dict(
                run_id=rid,
                design_id=design,
                experiment_id=campaign,
                project_id=project,
                status="running" if rid == "logic" else "queued",
            )
        )
    client = Client(rows)
    monkeypatch.setattr("chip_evolve.jobs.KernelClient", lambda *a, **k: client)
    result = run(spec, output)
    assert result["status"] == "timed_out" and result["usage"] is None
    assert result["cleanup"]["status"] == "completed"
    ef = result["platform_timeout_cleanup"]
    assert ef["status"] == "completed"
    assert set(client.cancelled) == {"root", "logic", "native"}
    assert set(ef["terminal_runs"]) == {"root", "logic", "native"}
    assert client.rows["other-trial"]["status"] == "queued"
    assert client.rows["other-project"]["status"] == "queued"
    assert read(output / "receipt.json")["platform_timeout_cleanup"] == ef


def test_normal_native_completion_does_not_cancel_even_with_explicit_plan(
    tmp_path, monkeypatch
):
    spec, output = episode(tmp_path)
    configure(spec, tmp_path)
    monkeypatch.setattr(
        "chip_evolve.jobs.KernelClient",
        lambda *a, **k: pytest.fail("no EF calls on ordinary completion"),
    )
    result = run(spec, output)
    assert result["status"] == "native_completed"
    assert "platform_timeout_cleanup" not in result


@pytest.mark.parametrize("case", ["unpinned", "existing", "escape", "empty"])
def test_invalid_ownership_rejected_before_native_dispatch(tmp_path, case):
    spec, output = episode(tmp_path)
    config = configure(spec, tmp_path)
    value = read(spec)
    if case == "unpinned":
        del value["input_hashes"][str(config)]
    elif case == "existing":
        (tmp_path / "state/experiments/gcd/trial-owned").mkdir(parents=True)
    elif case == "escape":
        value["platform_timeout_cleanup"]["experiments"][0]["key"] = "../unrelated"
    else:
        value["platform_timeout_cleanup"]["experiments"] = []
    write(spec, value)
    with pytest.raises(ValueError):
        run(spec, output)
    assert not output.exists()


@pytest.mark.parametrize("unavailable", [False, True])
def test_cancel_request_or_public_failure_is_not_terminal_success(
    tmp_path, monkeypatch, unavailable
):
    spec, _ = episode(tmp_path)
    config = configure(spec, tmp_path, keys=("trial-owned",))
    plan = prepare(read(spec))
    assert plan is not None
    path = tmp_path / "state/experiments/gcd/trial-owned"
    path.mkdir(parents=True)
    campaign = Jobs(Deployment(config), "gcd", path).campaign
    client = Client(
        [
            dict(
                run_id="owned",
                design_id="gcd",
                experiment_id=campaign,
                project_id="business",
                status="queued",
            )
        ],
        settle=False,
        unavailable=unavailable,
    )
    monkeypatch.setattr("chip_evolve.jobs.KernelClient", lambda *a, **k: client)
    result = retire(plan)
    assert result["status"] == "incomplete"
    if unavailable:
        assert result["errors"] and not client.cancelled
    else:
        assert result["not_confirmed_terminal"] == ["owned"]
        assert not result["terminal_runs"]
