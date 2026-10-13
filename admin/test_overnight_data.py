"""Physical failures and native power units must survive the data boundary."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from overnight_data import goal_metrics


def setup(tmp_path: Path, *, ok=True):
    (tmp_path / "runtime.json").write_text(
        json.dumps(
            {"kernel_url": "http://localhost:1", "data_url": "http://localhost:2"}
        )
    )
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "ok": ok,
                "metrics": {
                    "dynamic_power_pw": 1_000_000_000,
                    "leakage_power_pw": 10_000_000,
                    "tns_abs_ns": 2.5,
                },
            }
        )
    )
    return result


def test_failed_native_measurement_never_becomes_a_design_fact(tmp_path):
    result = setup(tmp_path, ok=False)
    with patch("overnight_data.submit") as submit:
        with pytest.raises(ValueError, match="failed native"):
            goal_metrics(tmp_path, "bad", "physical", result)
        submit.assert_not_called()


def test_successful_result_keeps_physical_ownership_and_si_power(tmp_path):
    result = setup(tmp_path)
    client = MagicMock()
    client.run.return_value = {"status": "succeeded"}

    def admit(state, key, spec):
        metadata = json.loads(Path(spec["staged_inputs"][0]["source"]).read_text())
        assert metadata["metrics"]["finish__power__total"] == pytest.approx(0.00101)
        assert metadata["metrics"]["finish__timing__setup__tns"] == -2.5
        assert spec["inputs"]["run_id"] == "physical-real"
        assert spec["labels"]["analysis_of_run_id"] == "physical-real"
        assert spec["staged_inputs"][1]["source"] == str(result)

    with patch("openroad_platform_client.KernelClient", return_value=client), patch(
        "overnight_data.submit", side_effect=admit
    ), patch(
        "overnight_data.collect",
        return_value={
            "run": {"status": "succeeded", "run_id": "analysis"},
            "artifacts": [{"kind": "data_snapshot", "artifact_id": "actual"}],
        },
    ), patch(
        "overnight_data.http", return_value={"status": "imported"}
    ):
        assert (
            goal_metrics(tmp_path, "good", "physical-real", result)["status"]
            == "imported"
        )
