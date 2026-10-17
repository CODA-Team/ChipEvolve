import csv
import json
from pathlib import Path

from common import get_design_config, get_param_constraints
from initial_constraints import constrain


def test_design_bounds_preserve_baseline_and_unrelated_values(tmp_path):
    path = tmp_path / "candidates.csv"
    path.write_text("CORE_UTILIZATION,clk_period\n65,310\n72,330\n15,280\n")
    config = {
        "configurations": [
            {
                "platform": "asap7",
                "design": "gcd",
                "placement_range_override": {"CORE_UTILIZATION": [20, 35]},
            }
        ],
        "parameter_constraints": {"placement": {"CORE_UTILIZATION": {"type": "int"}}},
    }
    constrain(path, config, "asap7", "gcd")
    rows = list(csv.DictReader(path.open()))
    assert [r["CORE_UTILIZATION"] for r in rows] == ["65", "35", "20"]
    assert [r["clk_period"] for r in rows] == ["310", "330", "280"]


def test_design_without_override_keeps_original_bytes(tmp_path):
    path = tmp_path / "candidates.csv"
    original = "CORE_UTILIZATION,clk_period\n65,310\n72,330\n"
    path.write_text(original)
    constrain(path, {"configurations": []}, "asap7", "other")
    assert path.read_text() == original


def test_default_gcd_inherits_shared_placement_and_cts_domains():
    config = json.loads(
        Path(__file__).resolve().parents[1].joinpath("drp_config.json").read_text()
    )
    design = get_design_config(config, "asap7", "gcd")
    assert design is not None
    for stage in ("placement", "cts"):
        assert f"{stage}_range_override" not in design
        assert (
            get_param_constraints(config, stage, design)
            == config["parameter_constraints"][stage]
        )
    assert get_param_constraints(config, "placement", design)["CORE_UTILIZATION"][
        "range"
    ] == [20, 99]


def test_default_gcd_preserves_valid_dense_candidates(tmp_path):
    config = json.loads(
        Path(__file__).resolve().parents[1].joinpath("drp_config.json").read_text()
    )
    path = tmp_path / "candidates.csv"
    original = (
        "CORE_UTILIZATION,CELL_PAD_IN_SITES_GLOBAL_PLACEMENT,"
        "CELL_PAD_IN_SITES_DETAIL_PLACEMENT,PLACE_DENSITY_LB_ADDON,clk_period\n"
        "65,0,0,0.20,310\n65,3,3,0.75,310\n80,3,3,0.75,310\n"
    )
    path.write_text(original)
    constrain(path, config, "asap7", "gcd")
    assert path.read_text() == original
