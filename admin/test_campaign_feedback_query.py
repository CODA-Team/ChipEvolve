"""A metric is usable only when its value, conditions, and producer agree."""

from copy import deepcopy

import pytest
from query_campaign_feedback import verify_metrics


@pytest.mark.parametrize(
    "change", ["value", "unit", "evaluation_conditions", "evidence"]
)
def test_sdk_feedback_rejects_same_number_with_changed_measurement_context(change):
    metadata = {"artifact_id": "measured-metadata", "sha256": "source-hash"}
    measured = {
        "observations": {
            name: {"unit": "W" if name == "power" else "ns", "value": 0.5}
            for name in ("tns", "wns", "power")
        },
        "metric_context": {"evaluation_conditions": {"cp0_ns": 0.792}},
    }
    rows = {
        name: {
            "status": "available",
            "unit": "W" if name == "POWER_TOTAL" else "ns",
            "value": 0.5,
            "authoritative_source": "a2_cp0_evaluator",
            "evaluation_conditions": {"cp0_ns": 0.792},
            "evidence": [{**metadata, "resolution": "exact_artifact"}],
        }
        for name in ("TNS", "WNS", "POWER_TOTAL")
    }
    verify_metrics(rows, measured, metadata)
    altered = deepcopy(rows)
    changes = {
        "value": 1.5,
        "unit": "ps",
        "evaluation_conditions": {"cp0_ns": 1.0},
        "evidence": [
            {
                "artifact_id": "other-metadata",
                "sha256": "source-hash",
                "resolution": "exact_artifact",
            }
        ],
    }
    altered["TNS"][change] = changes[change]
    with pytest.raises(ValueError):
        verify_metrics(altered, measured, metadata)
