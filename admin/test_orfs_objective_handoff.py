"""The ORFS CLI preserves an explicitly supplied common acceptance goal."""

import pytest

from admin.test_local_business import deployment
from chip_evolve.cli import main
from chip_evolve.config import read, write
from chip_evolve.delivery import recover


@pytest.mark.parametrize("explicit", [False, True])
def test_orfs_cli_passes_original_objective_to_physical_boundary(
    tmp_path, monkeypatch, explicit
):
    d = deployment(tmp_path)
    objective = tmp_path / "original-objective.json"
    objective.write_text('{"objective_id":"original-limits"}\n')
    seen = []

    def baseline(deployment, design_id, experiment, seconds, *, objective=None):
        seen.append((design_id, seconds, objective))
        return {"run_id": "measured", "metrics": {}}

    monkeypatch.setattr("chip_evolve.physical.baseline", baseline)
    monkeypatch.chdir(tmp_path)
    argv = [
        "chip-evolve",
        "--config",
        str(d.path),
        "run",
        "--design",
        "gcd",
        "--capability",
        "orfs",
        "--key",
        "control",
        "--seconds",
        "123",
    ]
    if explicit:
        argv += ["--objective", "original-objective.json"]
    monkeypatch.setattr("sys.argv", argv)
    assert main() == 0
    assert seen == [("gcd", 123, objective if explicit else None)]
    saved = read(tmp_path / "experiments/gcd/control/request.json")
    assert saved["objective"] == (str(objective) if explicit else None)


@pytest.mark.parametrize("explicit", [False, True])
def test_orfs_recovery_preserves_the_requested_goal(tmp_path, monkeypatch, explicit):
    d = deployment(tmp_path)
    folder = d.experiment("gcd", "interrupted")
    objective = tmp_path / "strict-goal.json"
    write(objective, {"objective_id": "strict-original", "power_max": 0.001})
    write(
        folder / "request.json",
        {
            "design": "gcd",
            "capability": "orfs",
            "seconds": 600,
            "objective": str(objective) if explicit else None,
        },
    )
    seen = []

    def baseline(deployment, design, experiment, seconds, *, objective=None):
        seen.append(objective)
        return {"design_id": design, "run_id": "same-physical-run"}

    monkeypatch.setattr("chip_evolve.physical.baseline", baseline)
    elsewhere = tmp_path / "other-directory"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    recover(d, "gcd", "interrupted")
    assert seen == [objective if explicit else None]
    assert read(objective)["power_max"] == 0.001
