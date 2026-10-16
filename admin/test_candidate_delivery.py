"""A tied native metric must not silently choose the business input."""

import pytest

from admin.test_adoption_consistency import frame_at
from chip_evolve.candidates import deliver_candidates, expand_results, result_frame
from chip_evolve.config import read, write


def test_tied_tns_delivers_all_candidates_without_a_winner(tmp_path):
    first = frame_at(tmp_path, "first", 1.9)
    second = frame_at(tmp_path, "second", 0.8)
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    result = deliver_candidates(campaign, [first, second])
    assert result["selected_source"] is None
    assert result["adopted"] is False
    assert [row["run_id"] for row in result["candidate_results"]] == ["first", "second"]
    assert "run_id" not in result and "metrics" not in result
    assert expand_results([campaign / "result.json"]) == [first, second]
    with pytest.raises(ValueError, match="Choose an explicit result"):
        result_frame(campaign / "result.json")


def test_infeasible_intermediate_is_available_but_not_adopted(tmp_path):
    candidate = frame_at(tmp_path, "exploration", 3.0)
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    result = deliver_candidates(campaign, [candidate])
    row = result["candidate_results"][0]
    assert not row["final_feasible"]
    assert row["constraint_violations"] == ["power_total_w_max"]
    assert result_frame(candidate)["run_id"] == "exploration"
    value = read(candidate)
    value["run_id"] = "changed"
    write(candidate, value)
    with pytest.raises(ValueError, match="Delivered candidate changed"):
        expand_results([campaign / "result.json"])
