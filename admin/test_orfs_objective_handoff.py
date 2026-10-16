"""The ORFS CLI preserves an explicitly supplied common acceptance goal."""

import pytest

from admin.test_local_business import deployment
from chip_evolve.cli import main
from chip_evolve.config import read


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
    assert saved["objective"] == ("original-objective.json" if explicit else None)
