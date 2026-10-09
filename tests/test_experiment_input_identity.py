"""Execution inputs must not be confused with timestamped derived exports."""
from copy import deepcopy

from openroad_app_data_foundation.analysis_context import experiment_conditions


def snapshot():
    return {"run_summary": {"timing_context": {"constraints": "inputs/original.sdc"}},
            "source_artifacts": [
                {"category": "raw_constraints", "logical_path": "inputs/original.sdc", "sha256": "a" * 64},
                {"category": "raw_constraints", "logical_path": "query-data/effective.sdc", "sha256": "b" * 64}]}


def test_export_byte_change_does_not_invent_changed_execution_constraints():
    left = snapshot()
    right = deepcopy(left)
    right["source_artifacts"][1]["sha256"] = "c" * 64
    result = experiment_conditions(left, right)["constraints"]
    assert result["status"] == "same"
    assert len(result["from"]) == len(result["to"]) == 1
    assert result["from"][0]["logical_path"] == "inputs/original.sdc"


def test_missing_loaded_sdc_remains_unknown_despite_available_export():
    left = snapshot()
    right = deepcopy(left)
    right["source_artifacts"].pop(0)
    assert experiment_conditions(left, right)["constraints"]["status"] == "unknown"


def test_changed_loaded_sdc_is_reported_even_when_exports_match():
    left = snapshot()
    right = deepcopy(left)
    right["source_artifacts"][0]["sha256"] = "c" * 64
    assert experiment_conditions(left, right)["constraints"]["status"] == "changed"
