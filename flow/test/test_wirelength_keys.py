"""Read the same stage wirelength across legacy and modern metric scopes."""

import json

import pytest
from extract_metrics import _extract_from_json


@pytest.mark.parametrize(
    "stage,filename,prefix",
    [("place", "3_5_place_dp.json", "detailedplace"), ("cts", "4_1_cts.json", "cts")],
)
def test_estimated_wirelength_scope(tmp_path, stage, filename, prefix):
    modern = f"{prefix}__dpl__route__wirelength__estimated"
    legacy = f"{prefix}__route__wirelength__estimated"
    path = tmp_path / filename
    path.write_text(json.dumps({modern: 40383.0}))
    assert _extract_from_json(tmp_path, stage)["wl"] == 40383.0
    path.write_text(json.dumps({modern: 40383.0, legacy: 40000.0}))
    assert _extract_from_json(tmp_path, stage)["wl"] == 40000.0
    path.write_text(json.dumps({f"{prefix}__dpl__design__hpwl__delta": 123.0}))
    assert _extract_from_json(tmp_path, stage)["wl"] is None


def test_final_uses_actual_routed_wirelength(tmp_path):
    (tmp_path / "6_report.json").write_text("{}")
    (tmp_path / "5_2_route.json").write_text(
        json.dumps({"detailedroute__route__wirelength": 54853.0})
    )
    assert _extract_from_json(tmp_path, "final")["wl"] == 54853.0
