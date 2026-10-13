import csv

from initial_constraints import constrain


def test_design_bounds_preserve_baseline_and_unrelated_values(tmp_path):
    path = tmp_path / "candidates.csv"
    path.write_text("CORE_UTILIZATION,clk_period\n65,310\n72,330\n15,280\n")
    config = {
        "configurations": [{"platform": "asap7", "design": "gcd",
                            "placement_range_override": {"CORE_UTILIZATION": [20, 35]}}],
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
