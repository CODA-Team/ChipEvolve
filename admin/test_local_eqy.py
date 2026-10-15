"""Complete partition proof and declared design state are required for acceptance."""

from pathlib import Path

import pytest

from chip_evolve.eqy import configuration, proof_receipt


def checks():
    ports = {
        "out": {"direction": "output", "width": 8},
        "clk": {"direction": "input", "width": 1},
    }
    return [{"ports": ports, "zero_port_types": ["TAPCELL_ZERO"]}] * 2


def test_netlist_hierarchical_state_and_all_ports_survive_alias_filter():
    result = configuration(
        "design",
        [Path("gold.v"), Path("gate.v")],
        [Path("actual-ff.lib")],
        checks(),
        [{"keygen.state", "old_only"}, {"keygen.state", "gate_only"}],
    )
    filter_at = result.index(r"gold-nomatch /.*\..*/")
    for name in ("clk", "out", r"keygen\.state"):
        assert result.index(f"final-gold-match /{name}/") < filter_at
    assert "old_only" not in result and "gate_only" not in result
    assert (
        result.count('read_liberty -ignore_miss_func -ignore_miss_dir "actual-ff.lib"')
        == 2
    )
    assert result.count("delete t:TAPCELL_ZERO") == 2
    assert "use sat\ndepth 10" in result


def test_no_pass_marker_is_not_a_completed_proof(tmp_path):
    with pytest.raises(ValueError, match="complete design"):
        proof_receipt(tmp_path, checks())


def test_global_success_cannot_hide_an_unproven_partition(tmp_path):
    (tmp_path / "PASS").write_text("native success")
    (tmp_path / "partition.list").write_text("design design.out : out[7:0]\n")
    status = tmp_path / "strategies/design.out/simple/status"
    status.parent.mkdir(parents=True)
    status.write_text("UNKNOWN\n")
    with pytest.raises(ValueError, match="partition remains unproven"):
        proof_receipt(tmp_path, checks())
    status.write_text("PASS\n")
    assert proof_receipt(tmp_path, checks()) == {
        "engine": "eqy",
        "proven_points": 8,
        "proven_partitions": 1,
    }
    (tmp_path / "FAIL").write_text("failed control")
    with pytest.raises(ValueError, match="complete design"):
        proof_receipt(tmp_path, checks())


def test_empty_partition_listing_is_not_proof(tmp_path):
    (tmp_path / "PASS").touch()
    (tmp_path / "partition.list").write_text("")
    with pytest.raises(ValueError, match="no proof partitions"):
        proof_receipt(tmp_path, checks())
