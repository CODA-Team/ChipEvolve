"""The optional complete model removes cuts without changing proof obligations."""

from pathlib import Path

import pytest

from admin.test_eqy_pdr import prepared
from admin.test_local_eqy import checks
from chip_evolve import eqy


def test_whole_model_keeps_sources_ports_and_pdr_but_merges_partitions():
    args = (
        "design",
        [Path("gold.v"), Path("gate.v")],
        [Path("fixed.lib")],
        checks(),
        [{"block.state"}, {"block.state"}],
    )
    original = eqy.configuration(*args, strategy="abc-pdr")
    merged = eqy.configuration(*args, strategy="abc-pdr", merge_partitions=True)
    assert merged.replace("[partition *]\nmerge *\n\n", "") == original
    assert "final-gold-match /out/" in merged
    assert "engine abc pdr" in merged and "xprop on" in merged
    assert "assume" not in merged


@pytest.mark.parametrize("enabled", [False, True])
def test_private_policy_reaches_submission_and_is_disclosed_in_proof_receipt(
    tmp_path, monkeypatch, enabled
):
    jobs, reference, candidate, _, _, _, calls = prepared(tmp_path, monkeypatch)
    jobs.deployment.value["validation"]["equivalence_merge_partitions"] = enabled
    _, result = eqy.verify(jobs, reference, candidate, [Path("fixed.lib")], checks())
    text = (jobs.experiment / "proof.eqy").read_text()
    assert ("[partition *]\nmerge *\n" in text) == enabled
    assert result["partition_mode"] == ("whole_design" if enabled else "matched")
    assert result["proven_points"] == 8 and result["proven_partitions"] == 1
    assert calls[0]["parent"] == candidate["run_id"]
