"""Qualification must require real design outputs and matching provenance."""

from copy import deepcopy

import pytest
from accept_common_toolchain import validate_results
from qualify_common_toolchain import IMAGE_SHA, OPENROAD, ORFS


def example():
    artifacts = [
        {
            "artifact_id": name,
            "run_id": "flow",
            "sha256": name,
            "store_key": "results/" + name,
            "size_bytes": 12,
        }
        for name in ("6_final.odb", "6_final.sdc", "6_final.spef", "6_final.gds")
    ]
    sources = [
        {
            "artifact_id": a["artifact_id"],
            "run_id": "export",
            "sha256": a["sha256"],
            "logical_path": "inputs/" + a["artifact_id"],
        }
        for a in artifacts[:3]
    ]
    sources += [
        {
            "artifact_id": "timing",
            "run_id": "export",
            "sha256": "timing",
            "logical_path": "timing.json",
        }
    ]
    config = {
        "image_sha256": IMAGE_SHA,
        "openroad_commit": OPENROAD,
        "orfs_commit": ORFS,
        "source_manifest_sha256": "manifest",
        "source_archive_sha256": "archive",
    }
    runtime = {
        "status": "succeeded",
        "snapshot_id": "snapshot",
        "jobs": {
            name: {
                "run": {"run_id": name, "status": "succeeded"},
                "artifacts": [{"kind": "data_snapshot"}],
            }
            for name in (
                "build",
                "flow",
                "export",
                "check",
                "metrics_export",
                "units_export",
            )
        },
    }
    artifacts.append(
        {
            "artifact_id": "6_report.json",
            "run_id": "flow",
            "sha256": "report",
            "store_key": "logs/6_report.json",
            "size_bytes": 12,
        }
    )
    runtime["metric_snapshot_id"] = "metric-snapshot"
    runtime["jobs"]["metrics_export"]["artifacts"] = [
        {
            "artifact_id": "metric-copy",
            "run_id": "metrics_export",
            "sha256": "report",
            "store_key": "inputs/6_report.json",
        }
    ]
    runtime["jobs"]["flow"]["artifacts"] = artifacts
    runtime["jobs"]["export"]["artifacts"] = sources
    built = {**config, "binary_sha256": "binary", "tracked_source_unchanged": True}
    checked = {
        "design": "gcd",
        "platform": "nangate45",
        "instances": 1,
        "nets": 1,
        "wns_ns": 0.1,
        "placement_check_passed": True,
        "binary_sha256": "binary",
        "image_sha256": IMAGE_SHA,
        "input_odb_sha256": "6_final.odb",
    }
    scope = {
        "design_id": "gcd",
        "snapshot_id": "snapshot",
        "run_id": "flow",
        "stage": "finish",
    }
    sdk = {
        "summary": {
            "data": {
                "snapshot": {
                    **scope,
                    "producer_run_id": "export",
                    "record_counts": {
                        k: 1
                        for k in (
                            "entities",
                            "relations",
                            "physical_context",
                            "timing_paths",
                            "timing_points",
                        )
                    },
                    "source_artifacts": sources,
                }
            }
        },
        "scope": {"scope": scope},
        "metrics": {
            "scope": {
                "snapshot_id": "metric-snapshot",
                "run_id": "flow",
                "design_id": "gcd",
            },
            "data": {
                "metrics": [
                    {
                        "name": "WNS",
                        "status": "available",
                        "raw_key": "finish__timing__setup__ws",
                        "raw_value": -0.1,
                    }
                ]
            },
        },
        "paths": {"data": {"timing_paths": [{"path_id": "p"}]}},
        "fragment": {"status": "available", "data": {"fragments": [{}]}},
        "raw_evidence": {"artifact_id": "timing", "sha256": "timing", "size_bytes": 10},
        "metric_raw_evidence": {
            "artifact_id": "metric-copy",
            "sha256": "report",
            "source": {"finish__timing__setup__ws": -0.1},
        },
    }
    values = {
        "WNS": (-0.1, "ns"),
        "TNS": (-1.0, "ns"),
        "AREA": (1.0, "um^2"),
        "POWER_TOTAL": (0.1, "W"),
        "INSTANCE_COUNT": (1, "count"),
    }
    sdk["metrics"]["data"]["metrics"] = [
        {
            "name": name,
            "status": "available",
            "unit": unit,
            "raw_key": name,
            "raw_value": value,
            "value": value,
        }
        for name, (value, unit) in values.items()
    ]
    sdk["metric_raw_evidence"]["source"] = {
        name: value for name, (value, unit) in values.items()
    }
    return config, runtime, built, checked, sdk


def test_complete_evidence_passes():
    validate_results(*example())


@pytest.mark.parametrize(
    "field,value",
    [
        ("binary_sha256", "system-binary"),
        ("design", "aes"),
        ("platform", "asap7"),
        ("instances", 0),
        ("wns_ns", float("nan")),
        ("input_odb_sha256", "other"),
    ],
)
def test_invalid_compiled_design_check_is_rejected(field, value):
    inputs = example()
    inputs[3][field] = value
    with pytest.raises(ValueError):
        validate_results(*inputs)


@pytest.mark.parametrize("job", ["build", "flow", "export", "check"])
def test_failed_jobs_are_rejected(job):
    inputs = example()
    inputs[1]["jobs"][job]["run"]["status"] = "failed"
    with pytest.raises(ValueError, match="incomplete"):
        validate_results(*inputs)


def test_missing_final_gds_is_rejected():
    inputs = example()
    inputs[1]["jobs"]["flow"]["artifacts"] = [
        a
        for a in inputs[1]["jobs"]["flow"]["artifacts"]
        if a["store_key"] != "results/6_final.gds"
    ]
    with pytest.raises(ValueError, match="6_final.gds"):
        validate_results(*inputs)


@pytest.mark.parametrize(
    "change", ["snapshot", "source", "metrics", "fragment", "raw", "producer"]
)
def test_missing_or_wrong_data_evidence_is_rejected(change):
    inputs = deepcopy(example())
    snapshot = inputs[4]["summary"]["data"]["snapshot"]
    if change == "snapshot":
        snapshot["snapshot_id"] = "other"
    elif change == "source":
        snapshot["source_artifacts"][0]["sha256"] = "tampered"
    elif change == "metrics":
        inputs[4]["metrics"]["data"]["metrics"] = []
    elif change == "fragment":
        inputs[4]["fragment"]["status"] = "unavailable"
    elif change == "producer":
        snapshot["producer_run_id"] = "other"
    else:
        inputs[4]["raw_evidence"]["sha256"] = "tampered"
    with pytest.raises(ValueError):
        validate_results(*inputs)


@pytest.mark.parametrize("tamper", ["scope", "value", "source"])
def test_metrics_require_actual_report_and_physical_run(tamper):
    inputs = example()
    if tamper == "scope":
        inputs[4]["metrics"]["scope"]["run_id"] = "other"
    elif tamper == "value":
        inputs[4]["metrics"]["data"]["metrics"][0]["raw_value"] = -10
    else:
        inputs[4]["metric_raw_evidence"]["sha256"] = "other report"
    with pytest.raises(ValueError):
        validate_results(*inputs)


@pytest.mark.parametrize(
    "field,value", [("unit", None), ("unit", "s"), ("status", "partial")]
)
def test_timing_metrics_without_confirmed_units_are_rejected(field, value):
    inputs = example()
    inputs[4]["metrics"]["data"]["metrics"][0][field] = value
    with pytest.raises(ValueError, match="unit is unavailable"):
        validate_results(*inputs)
