"""Derived-clock handling changes the formal clock model, not the obligations."""

from pathlib import Path

import pytest

from admin.test_eqy_pdr import prepared
from admin.test_local_eqy import checks
from chip_evolve import eqy


def test_derived_clock_option_keeps_models_matches_and_pdr_obligations():
    args = (
        "design",
        [Path("gold.v"), Path("gate.v")],
        [Path("fixed.lib")],
        checks(),
        [{"block.state"}, {"block.state"}],
    )
    original = eqy.configuration(*args, strategy="abc-pdr")
    derived = eqy.configuration(*args, strategy="abc-pdr", multiclock=True)
    assert (
        derived.replace("option multiclock on\n", "").replace("clk2fflogic\n", "")
        == original
    )
    assert derived.count("clk2fflogic\n") == 2
    assert derived.index("clk2fflogic") < derived.index("[match *]")
    assert "assume" not in derived


@pytest.mark.parametrize("enabled", [False, True])
def test_clock_policy_reaches_solver_and_is_recorded(tmp_path, monkeypatch, enabled):
    jobs, reference, candidate, _, _, _, calls = prepared(tmp_path, monkeypatch)
    jobs.deployment.value["validation"]["equivalence_multiclock"] = enabled
    _, result = eqy.verify(jobs, reference, candidate, [], checks())
    script = (jobs.experiment / "proof.eqy").read_text()
    assert ("option multiclock on" in script) is enabled
    assert result["clock_model"] == ("clk2fflogic" if enabled else "single_clock")
    assert result["proven_points"] == 8 and result["proven_partitions"] == 1
    assert calls[0]["parent"] == candidate["run_id"]
