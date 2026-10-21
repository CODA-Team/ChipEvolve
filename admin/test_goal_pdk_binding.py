"""The public business adapter passes the actual PDK to the native controller."""

from argparse import Namespace
from types import SimpleNamespace

import pytest

from chip_evolve import native
from chip_evolve.config import Deployment, read, write


@pytest.mark.parametrize("platform", ["asap7", "nangate45"])
def test_goal_profile_and_inputs_use_the_bound_pdk(tmp_path, monkeypatch, platform):
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
    write(
        campaign,
        {
            "target_metrics": {
                "dynamic_power_pw": 0,
                "leakage_power_pw": 0,
                "tns_abs_ns": 0,
            }
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
    monkeypatch.setattr(
        native,
        "Jobs",
        lambda *_args: SimpleNamespace(
            campaign="bound-pdk", command=lambda *_args, **_kwargs: None
        ),
    )

    def before_native(*_args):
        actual = read(experiment / "profile.json")
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
        seconds=60, code_source=None, operation="evolve", design="gcd", rounds=1
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
