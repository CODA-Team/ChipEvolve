"""Inherited Make values drive the real native config generator."""

import csv
import json
import os
import shutil
import subprocess
from pathlib import Path


def test_source_values_override_legacy_defaults_without_changing_ten_dimensional_csv(
    tmp_path,
):
    flow = Path(__file__).resolve().parents[1]
    for name in ("run_sequential.sh", "initial_constraints.py"):
        shutil.copyfile(flow / name, tmp_path / name)
    (tmp_path / "drp_config.json").write_text('{"configurations": []}')
    design = tmp_path / "designs/pdk/test"
    design.mkdir(parents=True)
    (design / "config.mk").write_text("include deeply/inherited/source-config.mk\n")
    (design / "constraint.sdc").write_text(
        "set clk_period 810\ncreate_clock -period $clk_period [get_ports clk]\n"
    )
    values = {
        "SYNTH_FLATTEN": "1",
        "CORE_UTILIZATION": "70",
        "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT": "0",
        "CELL_PAD_IN_SITES_DETAIL_PLACEMENT": "0",
        "ENABLE_DPO": "1",
        "PLACE_DENSITY_LB_ADDON": "0.2",
        "TNS_END_PERCENT": "100",
        "FLOORPLAN_PIN_LAYER_ADJUST": "0.25",
        "FLOORPLAN_ABOVE_LAYER_ADJUST": "0.30",
        "CTS_CLUSTER_SIZE": "25",
        "CTS_CLUSTER_DIAMETER": "100",
        "PIN_LAYER_ADJUST": "0.35",
        "ABOVE_LAYER_ADJUST": "0.40",
    }
    params = tmp_path / "parameters.json"
    params.write_text(json.dumps(values))
    subprocess.run(
        ["bash", str(tmp_path / "run_sequential.sh"), "pdk", "test", "3", "1"],
        check=True,
        capture_output=True,
        env=dict(os.environ, DRP_SOURCE_PARAMETERS=str(params), DRP_SEED="42"),
    )
    rows = list(csv.DictReader((design / "pdk_test.csv").open()))
    assert len(rows) == 3 and len(rows[0]) == 10
    for name in rows[0]:
        assert float(rows[0][name]) == float(values.get(name, "810"))
    generated = (design / "config_1.mk").read_text()
    for name in (
        "CTS_CLUSTER_SIZE",
        "CTS_CLUSTER_DIAMETER",
        "PIN_LAYER_ADJUST",
        "ABOVE_LAYER_ADJUST",
    ):
        assert f"export {name} = {values[name]}" in generated
    assert "export SYNTH_HIERARCHICAL = 0" in generated
    assert "export FLOORPLAN_PIN_LAYER_ADJUST = 0.25" in generated
