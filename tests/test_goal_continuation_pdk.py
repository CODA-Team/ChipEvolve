"""Goal continuation must hand its frozen technology to final qualification."""

from types import SimpleNamespace

import pytest

from chip_evolve import continuation, delivery
from chip_evolve.config import read, write
from chip_evolve.jobs import digest


@pytest.mark.parametrize("platform", ["asap7", "nangate45"])
@pytest.mark.parametrize("explicit_pdk", [False, True])
def test_continuation_delivers_the_original_technology(
    tmp_path, monkeypatch, platform, explicit_pdk
):
    previous = tmp_path / "previous"
    original_parent = {
        "source_hash": "selected",
        "source_commit": "measured-source",
        "evaluation_mode": "power_only",
        "metrics": {"dynamic_power_pw": 5, "leakage_power_pw": 5, "tns_abs_ns": 0.4},
    }
    original_checkpoint = previous / "campaign/parents/selected/design_checkpoint.odb"
    original_checkpoint.parent.mkdir(parents=True)
    original_checkpoint.write_bytes(b"qualified source layout")
    write(previous / "campaign/parent.json", original_parent)
    write(
        previous / "result.json",
        {
            "design_id": "gcd",
            "run_id": "source-run",
            "objective": str(tmp_path / "objective.json"),
            "qualification": {"input_odb_sha256": digest(original_checkpoint)},
        },
    )
    pdk = previous / "inputs" / platform
    if explicit_pdk:
        pdk = previous / "inputs/frozen-technology"
    pdk.mkdir(parents=True)
    (pdk / "setRC.tcl").write_text("frozen " + platform + " RC\n")
    write(
        previous / "profile.json",
        {
            "source_seed": str(tmp_path / "seed"),
            **({"pdk_root": str(pdk)} if explicit_pdk else {}),
        },
    )
    write(
        previous / "evolve-config.json",
        {
            "target_metrics": {
                "dynamic_power_pw": 10,
                "leakage_power_pw": 10,
                "tns_abs_ns": 0,
            },
            "students": ["original-student"],
        },
    )
    (previous / "controller/third_party/official_checker").mkdir(parents=True)
    experiment = tmp_path / "continued"
    experiment.mkdir()
    deployment = SimpleNamespace(
        experiment=lambda *_args: experiment,
        design=lambda _design: {"platform": platform},
        value={
            "professional": {"goal": {"source": str(tmp_path / "module")}},
            "kernel_url": "http://localhost:1",
            "client_python": "/client/python",
            "goal_python": "/goal/python",
        },
    )
    monkeypatch.setattr(
        continuation, "freeze", lambda _source, target, **_kwargs: target.mkdir()
    )
    monkeypatch.setattr(continuation, "inventory", lambda _path: {})
    monkeypatch.setattr(continuation, "environment", lambda *_args: {})
    monkeypatch.setattr(
        "eda_toolkits.context.load_context",
        lambda _path: {"scope": {"design_id": "gcd", "run_id": "source-run"}},
    )

    def native_round(*_args):
        assert read(experiment / "evolve-config.json")["target_metrics"] == {
            "dynamic_power_pw": 10,
            "leakage_power_pw": 10,
            "tns_abs_ns": 0,
        }
        write(experiment / "campaign/parent.json", original_parent)
        selected = experiment / "campaign/parents/selected/design_checkpoint.odb"
        selected.parent.mkdir(parents=True)
        selected.write_bytes(original_checkpoint.read_bytes())

    monkeypatch.setattr(continuation, "invoke", native_round)
    monkeypatch.setattr(continuation, "checkpoint_producer", lambda *_args: "producer")
    monkeypatch.setattr(continuation, "checkpoint_method", lambda *_args: {})
    captured = {}
    monkeypatch.setattr(
        delivery, "checkpoint", lambda _experiment, **fields: captured.update(fields)
    )
    monkeypatch.setattr(delivery, "finish", lambda *_args: {"run_id": "delivered"})
    result = continuation.run(
        deployment, previous, tmp_path / "context.json", "continued", 60
    )
    assert result == {"run_id": "delivered"}
    assert captured["pdk"] == pdk
    assert (captured["pdk"] / "setRC.tcl").read_text() == "frozen " + platform + " RC\n"
    assert captured["producer"] == "producer"
