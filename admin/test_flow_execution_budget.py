"""A calibrated native batch deadline must reach Flow without changing its search."""

from argparse import Namespace
from unittest.mock import patch

import pytest

from chip_evolve.config import Deployment, read, write
from chip_evolve.professional import run_flow


def fixture(tmp_path, execution=None):
    path = tmp_path / "local.json"
    binding = {"python": "/native/bin/python"}
    if execution is not None:
        binding["execution"] = execution
    write(
        path,
        {
            "schema_version": "chip-evolve.local.v1",
            "state_root": str(tmp_path / "runtime"),
            "kernel_url": "http://localhost:1",
            "data_url": "http://localhost:2",
            "professional": {"flow": binding},
            "designs": {
                "jpeg": {
                    "platform": "asap7",
                    "nickname": "jpeg",
                    "clock_period_ns": 0.545,
                }
            },
        },
    )
    d = Deployment(path)
    experiment = d.experiment("jpeg", "budget")
    source = experiment / "source"
    (source / "flow/designs/asap7/jpeg").mkdir(parents=True)
    (source / "config").mkdir()
    sdc = tmp_path / "source.sdc"
    sdc.write_text(
        "set_cmd_units -time ps\ncreate_clock -name clk -period 545 [get_ports clk]\n"
    )
    profile = tmp_path / "profile.json"
    write(
        profile,
        {"toolchain": {"binaries": {k: {"sha256": k} for k in ("openroad", "yosys")}}},
    )
    args = Namespace(
        design="jpeg", flow_recipe="legacy", seconds=36000, rounds=2, candidates=50
    )
    return d, args, experiment, source, sdc, profile


@pytest.mark.parametrize(
    "execution,expected",
    [
        (None, (8, 24, 7200)),
        (
            {"threads": 16, "memory_gib": 32, "stage_timeout_seconds": 14400},
            (16, 32, 14400),
        ),
    ],
)
def test_budget_reaches_native_command_and_ef_reservation(
    tmp_path, execution, expected
):
    d, args, experiment, source, sdc, profile = fixture(tmp_path, execution)
    with (
        patch("chip_evolve.professional.flow_source", return_value=source),
        patch("chip_evolve.professional.tool_profile", return_value=profile),
        patch("chip_evolve.professional.invoke") as invoke,
        patch(
            "chip_evolve.professional.collect_flow", return_value={"delivered": True}
        ),
    ):
        assert run_flow(
            d,
            args,
            experiment,
            {"files": {"sdc": str(sdc)}},
            tmp_path / "objective.json",
            tmp_path / "context.json",
        ) == {"delivered": True}
    command, _, _, _, seconds = invoke.call_args.args
    settings = read(experiment / "platform.json")
    threads, memory, stage = expected
    assert command[command.index("--cpus") + 1] == str(threads)
    assert command[command.index("--timeout") + 1] == str(stage) + "s"
    assert command[command.index("-i") + 1] == "2"
    assert command[command.index("-r") + 1] == "50"
    assert command[command.index("-o") + 1] == "TNS_EVAL"
    assert settings["threads"] == threads
    assert settings["resources"]["memory_bytes"] == memory << 30
    assert settings["stage_timeout_seconds"] == stage
    assert settings["timeout_seconds"] == seconds == 36000
    assert settings["deadline_epoch"] > 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("threads", 0),
        ("memory_gib", -1),
        ("stage_timeout_seconds", "4h"),
        ("threads", True),
        ("stage_timeout_seconds", 1.5),
    ],
)
def test_invalid_budget_fails_before_preparing_native_files(tmp_path, field, value):
    d, args, experiment, *_ = fixture(tmp_path, {field: value})
    with (
        patch("chip_evolve.professional.flow_source") as prepare,
        pytest.raises(ValueError, match=field),
    ):
        run_flow(
            d,
            args,
            experiment,
            {},
            tmp_path / "objective.json",
            tmp_path / "context.json",
        )
    prepare.assert_not_called()
