"""The public business adapter passes the actual PDK to the native controller."""

from argparse import Namespace
from types import SimpleNamespace

import pytest

from chip_evolve import native
from chip_evolve.config import Deployment, read, write


@pytest.mark.parametrize("platform", ["asap7", "nangate45"])
@pytest.mark.parametrize("explicit_donor", [False, True])
@pytest.mark.parametrize("operation", ["evolve", "replay"])
def test_goal_profile_and_inputs_use_the_bound_pdk(
    tmp_path, monkeypatch, platform, explicit_donor, operation
):
    pdk = tmp_path / "technology"
    (pdk / "lib").mkdir(parents=True)
    (pdk / "setRC.tcl").write_text("set_wire_rc -signal -layer metal3\n")
    if platform == "nangate45":
        (pdk / "equivalent_cells.csv").write_text("INV_X1\n")
    official = tmp_path / "official"
    official.mkdir()
    library = tmp_path / "standard.lib"
    library.write_text("library (standard) {}\n")
    profile = tmp_path / "profile-template.json"
    write(profile, {"source_seed": str(tmp_path / "seed"), "resources": {}})
    campaign = tmp_path / "campaign-template.json"
    donor = tmp_path / "build-donor"
    write(
        campaign,
        {
            **({"build_seed_root": str(donor)} if explicit_donor else {}),
            "target_metrics": {
                "dynamic_power_pw": 0,
                "leakage_power_pw": 0,
                "tns_abs_ns": 0,
            },
        },
    )
    config = tmp_path / "local.json"
    write(
        config,
        {
            "schema_version": "chip-evolve.local.v1",
            "state_root": str(tmp_path / "state"),
            "kernel_url": "http://localhost:1",
            "data_url": "http://localhost:2",
            "tools": {"openroad": "/openroad"},
            "client_python": "/client/python",
            "goal_python": "/goal/python",
            "designs": {
                "gcd": {
                    "top": "gcd",
                    "platform": platform,
                    "libraries": [{"path": str(library)}],
                }
            },
            "professional": {
                "goal": {
                    "source": str(tmp_path / "source"),
                    "official_checker": str(official),
                    "pdk_template": str(pdk),
                    "profile_template": str(profile),
                    "campaign_template": str(campaign),
                }
            },
        },
    )
    experiment = tmp_path / "experiment"
    experiment.mkdir()
    frame = {
        "run_id": "parent",
        "snapshot_ids": {"opendb": "objects", "orfs": "metrics"},
        "files": {},
    }
    for ext in ("def", "v", "sdc", "odb"):
        path = tmp_path / ("gcd." + ext)
        path.write_text(ext)
        frame["files"][ext] = str(path)
    monkeypatch.setattr(
        native, "freeze", lambda _original, target, **_kwargs: target.mkdir()
    )
    monkeypatch.setattr(native, "inventory", lambda _path: {})
    monkeypatch.setattr(native, "environment", lambda *_args: {})
    monkeypatch.setattr(native, "container", lambda _deployment, command: command)
    selected = tmp_path / "selected-source"
    monkeypatch.setattr(
        "chip_evolve.goal_replay.descriptor",
        lambda *_args: {"source_root": str(selected), "recipe_parameters": {}},
    )
    monkeypatch.setattr(
        native,
        "Jobs",
        lambda *_args: SimpleNamespace(
            campaign="bound-pdk", command=lambda *_args, **_kwargs: None
        ),
    )

    def before_native(*_args):
        actual = read(experiment / "profile.json")
        config = read(experiment / "baseline-config.json")
        seed = str(tmp_path / "seed")
        expected_donor = str(donor) if explicit_donor else seed
        assert seed in actual["read_roots"]
        assert expected_donor in actual["read_roots"]
        assert config["source_root"] == (
            str(selected) if operation == "replay" else seed
        )
        if explicit_donor or operation == "replay":
            assert config["build_seed_root"] == expected_donor
        else:
            assert "build_seed_root" not in config
        if operation == "replay":
            assert str(selected) in actual["read_roots"]
        expected = experiment / "inputs" / platform
        assert actual["pdk_root"] == str(expected)
        assert (expected / "lib/standard.lib").read_text() == library.read_text()
        if platform == "nangate45":
            assert actual["equivalent_cells"] == str(expected / "equivalent_cells.csv")
        else:
            assert "equivalent_cells" not in actual
        raise RuntimeError("checked-before-native-launch")

    monkeypatch.setattr(native, "invoke", before_native)
    args = Namespace(
        seconds=60,
        code_source=tmp_path / "candidate.json" if operation == "replay" else None,
        operation=operation,
        design="gcd",
        rounds=1,
    )
    with pytest.raises(RuntimeError, match="checked-before-native-launch"):
        native.run_goal(
            Deployment(config),
            args,
            experiment,
            frame,
            tmp_path / "objective.json",
            tmp_path / "context.json",
        )


@pytest.mark.parametrize("explicit_donor", [False, True])
def test_goal_continuation_preserves_the_original_build_donor_mount(
    tmp_path, monkeypatch, explicit_donor
):
    from chip_evolve import continuation
    from chip_evolve.jobs import digest

    previous = tmp_path / "previous"
    checkpoint = previous / "campaign/parents/selected/design_checkpoint.odb"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"qualified selected layout")
    write(
        previous / "result.json",
        {
            "design_id": "gcd",
            "qualification": {"input_odb_sha256": digest(checkpoint)},
        },
    )
    write(previous / "campaign/parent.json", {"source_hash": "selected"})
    donor = str(tmp_path / "donor")
    write(
        previous / "evolve-config.json",
        {"build_seed_root": donor} if explicit_donor else {},
    )
    seed = str(tmp_path / "seed")
    write(previous / "profile.json", {"source_seed": seed})
    (previous / "controller/third_party/official_checker").mkdir(parents=True)
    experiment = tmp_path / "continuation"
    experiment.mkdir()
    deployment = SimpleNamespace(
        experiment=lambda *_args: experiment,
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

    def before_native(path, value):
        assert path == experiment / "profile.json"
        assert seed in value["read_roots"]
        assert (donor if explicit_donor else seed) in value["read_roots"]
        raise RuntimeError("continuation-mount-checked-before-launch")

    monkeypatch.setattr(continuation, "write", before_native)
    with pytest.raises(RuntimeError, match="continuation-mount-checked-before-launch"):
        continuation.run(deployment, previous, tmp_path / "context.json", "next", 60)
