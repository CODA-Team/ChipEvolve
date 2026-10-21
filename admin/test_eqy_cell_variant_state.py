"""Resized-cell state proposals add obligations without changing the logic model."""

import copy

import pytest

from admin.test_eqy_pdr import prepared
from admin.test_eqy_sequential_state import model
from admin.test_local_eqy import checks
from chip_evolve import eqy
from chip_evolve.config import read, write


def resized_model():
    gate = model()
    gate["modules"]["design"]["cells"]["register"]["type"] = "larger_vt_variant"
    gate["modules"]["larger_vt_variant"] = copy.deepcopy(gate["modules"]["storage"])
    gate["modules"]["larger_vt_variant"]["attributes"] = {"area": "larger"}
    return gate


def test_cell_variant_matching_is_explicit_and_keeps_existing_state_points():
    gold, gate = model(), resized_model()
    assert eqy.common_flop_states(gold, gate, "design") == set()
    assert eqy.common_flop_states(gold, gate, "design", match_cell_variants=True) == {
        "register.IQ"
    }
    assert eqy.common_flop_states(
        gold, model(), "design", match_cell_variants=True
    ) == eqy.common_flop_states(gold, model(), "design")


@pytest.mark.parametrize("change", ["missing_instance", "missing_model", "no_state"])
def test_variants_do_not_invent_unobserved_or_stateless_correspondences(change):
    gold, gate = model(), resized_model()
    if change == "missing_instance":
        del gate["modules"]["design"]["cells"]["register"]
    elif change == "missing_model":
        del gate["modules"]["larger_vt_variant"]
    else:
        gate["modules"]["larger_vt_variant"] = copy.deepcopy(gate["modules"]["buffer"])
    assert (
        eqy.common_flop_states(gold, gate, "design", match_cell_variants=True) == set()
    )


@pytest.mark.parametrize("enabled", [False, True])
def test_private_policy_reaches_asserted_matches_and_disclosed_receipt(
    tmp_path, monkeypatch, enabled
):
    jobs, reference, candidate, _, _, _, _ = prepared(tmp_path, monkeypatch)
    jobs.deployment.value["validation"].update(
        equivalence_match_flops=True, equivalence_match_cell_variants=enabled
    )
    write(jobs.experiment / "gold.json", model())
    write(jobs.experiment / "gate.json", resized_model())
    _, receipt = eqy.verify(jobs, reference, candidate, [], checks())
    assert receipt["proposed_state_points"] == (1 if enabled else 0)
    assert receipt.get("cell_variant_state_matching", False) is enabled
    assert read(jobs.experiment / "proof-state-matches.json")["points"] == (
        ["register.IQ"] if enabled else []
    )
    text = (jobs.experiment / "proof.eqy").read_text()
    assert (r"final-gold-match /(?:register\.IQ)/" in text) is enabled
    assert "engine abc pdr" in text and "assume" not in text
    assert receipt["proven_points"] == 8
