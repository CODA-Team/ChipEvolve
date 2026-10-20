import hashlib

import pytest
from platform_drc import best_drc_report_tcl, route_evidence


def test_platform_records_native_count_before_a_standalone_checker(monkeypatch):
    monkeypatch.setenv("TIMINGECO_EF_LEAF", "1")
    script = best_drc_report_tcl("/outputs/drc.rpt")
    assert "drt::detailed_route_num_drvs" in script
    assert "check_drc" not in script
    assert "/outputs/drc.rpt.count" in script


def test_original_native_report_command_is_preserved(monkeypatch):
    monkeypatch.delenv("TIMINGECO_EF_LEAF", raising=False)
    assert "{ check_drc }" in best_drc_report_tcl("native.rpt")


@pytest.mark.parametrize(
    "saved,input_count,expected",
    [(3, 0, 3), (0, 7, 0), (None, 7, 7), (None, None, None)],
)
def test_drc_evidence_is_paired_with_the_selected_checkpoint(
    tmp_path, saved, input_count, expected
):
    odb = tmp_path / "final_eco.odb"
    odb.write_bytes(b"selected best routed state")
    if saved is not None:
        (tmp_path / "final_drc_report.txt.count").write_text(str(saved))
    record = route_evidence(tmp_path, input_count)
    assert record["route_drc"] == expected
    assert record["checkpoint_sha256"] == hashlib.sha256(odb.read_bytes()).hexdigest()


def test_broken_native_counter_does_not_fall_back_to_input_zero(tmp_path):
    (tmp_path / "final_drc_report.txt.count").write_text("")
    with pytest.raises(ValueError):
        route_evidence(tmp_path, 0)
