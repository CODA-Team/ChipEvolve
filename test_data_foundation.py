"""Deterministic data-foundation business tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from openroad_platform_contracts import ContractError

from openroad_app_data_foundation.bundle import import_ready_bundles, load_run_bundle
from openroad_app_data_foundation.context import net_context, object_context
from openroad_app_data_foundation.envelope import envelope
from openroad_app_data_foundation.ingest import load_snapshot_directory
from openroad_app_data_foundation.metric_queries import compare_metric
from openroad_app_data_foundation.metrics import project_run
from openroad_app_data_foundation.queries import (
    compare_timing_path,
    list_metrics_for_run,
    list_observations,
    list_timing_paths,
)
from openroad_app_data_foundation.repository import DataStore


def pack() -> dict:
    return {
        "snapshot": {
            "snapshot_id": "snap-1", "design_id": "chip", "revision_id": "rev-1",
            "run_id": "run-1", "stage": "route", "created_at": "2026-01-01T00:00:00Z",
        },
        "entities": [{"object_id": "top/u1", "snapshot_id": "snap-1",
                       "kind": "instance", "name": "u1"},
                      {"object_id": "net:n1", "snapshot_id": "snap-1",
                       "kind": "net", "name": "n1"}],
        "timing_paths": [{"path_id": "path-1", "snapshot_id": "snap-1",
                           "analysis": "view", "check": "setup", "group": "clk",
                           "startpoint": "top/u1/A", "endpoint": "top/u2/Z",
                           "corner": "slow", "unit": "s",
                           "evidence": [{"artifact_id": "report-1", "source_type": "line",
                                          "line_start": 12, "line_end": 19}]}],
        "timing_points": [{"point_id": "point-1", "path_id": "path-1", "ordinal": 0,
                            "pin_name": "top/u1/A", "object_id": "top/u1"}],
        "physical_context": [{"object_id": "top/u1", "snapshot_id": "snap-1",
                              "instance_name": "u1", "x": 10.0, "y": 20.0},
                             {"object_id": "net:n1", "snapshot_id": "snap-1",
                              "routing": [{"routing_type": "segment"}]}],
    }


def test_snapshot_and_path_are_separate_fact_queries(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "data.db")
    try:
        created = store.register(pack())
        assert created["record_counts"]["timing_paths"] == 1
        assert store.records("snap-1", "timing_points")[0]["object_id"] == "top/u1"
        assert store.physical("snap-1", "top/u1")["x"] == 10.0
        assert store.find_instance("snap-1", "u1")[0]["object_id"] == "top/u1"
        assert store.find_net("snap-1", "n1")[0]["object_id"] == "net:n1"
        assert store.net("snap-1", "net:n1")["physical_context"]["routing"]
        assert store.run_summary("snap-1")["record_counts"]["timing_paths"] == 1
        assert store.run_summary_for_run("run-1")["snapshots"][0]["snapshot"][
            "snapshot_id"] == "snap-1"
    finally:
        store.close()


def test_structured_metrics_are_queryable_by_snapshot_and_run(tmp_path: Path) -> None:
    value = pack()
    value["run_summary"] = {"tool": "flow", "metrics": {"wns": -0.2}}
    value["observations"] = [{
        "observation_id": "metric:wns", "object_id": "run:run-1",
        "kind": "metric", "value": -0.2, "status": "parsed",
        "evidence": [{"artifact_id": "metrics-1", "field": "metrics.wns"}],
    }, {
        "observation_id": "metric:tns", "object_id": "run:run-1",
        "kind": "metric", "value": -1.3, "status": "parsed",
        "context": {"scene": "setup"},
    }]
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(value)
        summary = store.run_summary("snap-1")
        assert summary["run_summary"]["metrics"]["wns"] == -0.2
        observed = list_observations(store, "snap-1", {"name": "wns"})
        assert observed["observations"][0]["value"] == -0.2
        # CONTRACT 4.6: only declared canonical names appear in metrics;
        # anything else stays reachable under its original key.
        metrics = list_metrics_for_run(store, "run-1", {"scene": "setup"})
        assert metrics["metrics"] == []
        raw = list_metrics_for_run(store, "run-1", {"include_raw": "1"})
        by_key = {item["raw_key"]: item for item in raw["raw_metrics"]}
        assert by_key["wns"]["value"] == -0.2
        assert by_key["tns"]["stage"] == "route"
        assert by_key["tns"]["canonical"] is False
        runtime = [row for row in list_metrics_for_run(store, "run-1", {})["metrics"]
                   if row["name"] == "RUNTIME"][0]
        assert runtime["status"] == "unavailable"
        assert runtime["authoritative_source"] == "execution_foundation"
    finally:
        store.close()


def test_metric_comparison_keeps_values_units_and_evidence(tmp_path: Path) -> None:
    placed = pack()
    placed["snapshot"] = {**placed["snapshot"], "snapshot_id": "snap-place",
                           "stage": "place"}
    placed["observations"] = [{
        "observation_id": "metric:wns", "kind": "metric", "name": "wns",
        "value": -0.12, "unit": "ns", "context": {"scene": "setup"},
        "evidence": [{"artifact_id": "place-metrics", "field": "wns"}],
    }]
    routed = {
        **placed,
        "snapshot": {**placed["snapshot"], "snapshot_id": "snap-route",
                      "stage": "route"},
        "observations": [{
            "observation_id": "metric:wns", "kind": "metric", "name": "wns",
            "value": -0.58, "unit": "ns", "context": {"scene": "setup"},
            "evidence": [{"artifact_id": "route-metrics", "field": "wns"}],
        }],
    }
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(placed)
        store.register(routed)
        result = compare_metric(store, "snap-place", "snap-route", "wns", "setup")
        assert result["status"] == "COMPARABLE"
        assert result["value"] == {"from": -0.12, "to": -0.58, "delta": pytest.approx(-0.46)}
        assert result["unit"] == "ns"
        assert result["evidence"]["from"][0]["artifact_id"] == "place-metrics"
    finally:
        store.close()


def test_metric_comparison_rejects_unit_or_scope_mismatch(tmp_path: Path) -> None:
    left = pack()
    left["observations"] = [{"observation_id": "metric:area", "kind": "metric",
                              "name": "area", "value": 10, "unit": "um2"}]
    right = {**left, "snapshot": {**left["snapshot"], "snapshot_id": "snap-right",
                                   "revision_id": "rev-2"},
             "observations": [{"observation_id": "metric:area", "kind": "metric",
                                "name": "area", "value": 11, "unit": "mm2"}]}
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(left)
        store.register(right)
        result = compare_metric(store, "snap-1", "snap-right", "area")
        assert result["status"] == "INCOMPARABLE"
        assert {item["field"] for item in result["matching"]["reasons"]} == {
            "revision_id", "unit"}
        assert "value" not in result
    finally:
        store.close()


def test_snapshot_records_keep_native_local_and_canonical_identity(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(pack())
        entity = store.object("snap-1", "top/u1")["entity"]
        identity = entity["identity"]
        assert identity["snapshot_local_id"] == "top/u1"
        assert identity["canonical"] == {
            "design_id": "chip", "revision_id": "rev-1",
            "kind": "instance", "hierarchical_name": "u1",
        }
        point = store.records("snap-1", "timing_points")[0]
        assert point["identity_references"]["object_id"] == identity
        physical = store.physical("snap-1", "top/u1")
        assert physical["identity"] == identity
    finally:
        store.close()


def test_snapshot_retains_ambiguous_canonical_identity(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "data.db")
    try:
        value = pack()
        value["entities"].append({"object_id": "another/u1", "kind": "instance",
                                   "name": "u1"})
        store.register(value)
        identities = [row["identity"] for row in store.records("snap-1", "entities")
                      if row["identity"]["canonical"]["hierarchical_name"] == "u1"]
        assert all(item["matching_status"] == "ambiguous" for item in identities)
        assert identities[0]["ambiguous_candidates"] == ["another/u1", "top/u1"]
    finally:
        store.close()


def test_evidence_keeps_source_location(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(pack())
        evidence = store.evidence("snap-1", "report-1")
        assert evidence[0]["record_id"] == "path-1"
        assert evidence[0]["evidence"]["line_start"] == 12
        assert store.record_evidence("snap-1", "timing_paths", "path-1")[0][
            "evidence"]["line_end"] == 19
    finally:
        store.close()


def test_evidence_role_resolves_to_registered_artifact_identity(tmp_path: Path) -> None:
    value = pack()
    value["snapshot"]["source_artifacts"] = [{
        "artifact_id": "timing-1", "run_id": "run-1", "sha256": "a" * 64,
        "logical_path": "stored/reports/timing.json",
        "category": "raw_timing_report", "stage": "route", "size_bytes": 20,
    }]
    value["timing_paths"][0]["evidence"] = [{
        "artifact_kind": "raw_timing_report", "logical_path": "reports/timing.json",
        "stage": "route", "source_type": "json", "line_start": 2,
    }]
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(value)
        evidence = store.record_evidence("snap-1", "timing_paths", "path-1")[0]["evidence"]
        assert evidence["artifact_id"] == "timing-1"
        assert evidence["resolution"] == "unique_role"
        assert evidence["sha256"] == "a" * 64
    finally:
        store.close()


def test_evidence_role_stays_unresolved_when_two_sources_match(tmp_path: Path) -> None:
    value = pack()
    value["snapshot"]["source_artifacts"] = [{
        "artifact_id": "timing-1", "run_id": "run-1", "sha256": "a" * 64,
        "logical_path": "reports/a.json", "category": "raw_timing_report",
        "stage": "route", "size_bytes": 20,
    }, {
        "artifact_id": "timing-2", "run_id": "run-1", "sha256": "b" * 64,
        "logical_path": "reports/b.json", "category": "raw_timing_report",
        "stage": "route", "size_bytes": 20,
    }]
    value["timing_paths"][0]["evidence"] = [{
        "artifact_kind": "raw_timing_report", "logical_path": "unknown.json",
    }]
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(value)
        evidence = store.record_evidence("snap-1", "timing_paths", "path-1")[0]["evidence"]
        assert evidence["resolution"] == "ambiguous"
        assert "artifact_id" not in evidence
    finally:
        store.close()


def test_placeholder_evidence_resolves_to_real_bundle_artifact(tmp_path: Path) -> None:
    value = pack()
    value["snapshot"]["source_artifacts"] = [{
        "artifact_id": "bundle-1", "run_id": "run-1", "sha256": "a" * 64,
        "logical_path": "query-data.zip", "category": "data_snapshot",
        "stage": "route", "size_bytes": 20,
    }]
    value["timing_paths"][0]["evidence"] = [{
        "artifact_id": "timing-report", "artifact_kind": "raw_timing_report",
        "logical_path": "query-data/timing_report.json", "source_type": "json",
        "json_pointer": "/checks/0",
    }]
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(value)
        evidence = store.record_evidence("snap-1", "timing_paths", "path-1")[0]["evidence"]
        assert evidence["artifact_id"] == "bundle-1"
        assert evidence["resolution"] == "bundle_member"
        assert evidence["nested_path"] == "query-data/timing_report.json"
        assert evidence["artifact_id"] != "timing-report"
    finally:
        store.close()


def test_missing_analysis_context_is_unavailable_and_not_comparable(tmp_path: Path) -> None:
    value = pack()
    del value["timing_paths"][0]["corner"]
    other = {**value, "snapshot": {**value["snapshot"], "snapshot_id": "snap-2"}}
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(value)
        store.register(other)
        context = compare_timing_path(store, "snap-1", "snap-2", "path-1")
        assert context["status"] == "INCOMPARABLE"
        assert any(item["field"] == "corner" for item in context["matching"]["reasons"])
        assert "timing" not in context
    finally:
        store.close()


def test_object_and_net_contexts_keep_explicit_neighbors_and_sources(tmp_path: Path) -> None:
    value = pack()
    value["relations"] = [{
        "relation_id": "u1-net", "snapshot_id": "snap-1",
        "subject_id": "top/u1", "predicate": "connected_to",
        "object_id": "net:n1",
        "evidence": [{"artifact_id": "netlist-1", "source_type": "line",
                       "line_start": 4, "line_end": 4}],
    }, {
        "relation_id": "pin-inst", "snapshot_id": "snap-1",
        "subject_id": "top/u1/A", "predicate": "belongs_to", "object_id": "top/u1",
    }, {
        "relation_id": "pin-net", "snapshot_id": "snap-1",
        "subject_id": "top/u1/A", "predicate": "connected_to", "object_id": "net:n1",
    }]
    value["entities"].append({"object_id": "top/u1/A", "snapshot_id": "snap-1",
                                "kind": "pin", "name": "u1/A", "parent_id": "top/u1"})
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(value)
        instance = object_context(store, "snap-1", "top/u1")
        assert instance["target"] == {"type": "object", "id": "top/u1"}
        assert {row["object_id"] for row in instance["entities"]} == {
            "top/u1", "top/u1/A", "net:n1"}
        assert len(instance["relations"]) == 3
        assert instance["physical_context"][0]["object_id"] == "top/u1"
        net = net_context(store, "snap-1", "net:n1")
        assert net["target"] == {"type": "net", "id": "net:n1"}
        assert {row["kind"] for row in net["entities"]} == {"instance", "pin", "net"}
        assert net["physical_context"][0]["object_id"] == "net:n1"
        assert any(item["artifact_id"] == "netlist-1" for item in net["evidence"])
    finally:
        store.close()


def test_snapshot_rejects_missing_fact_boundary(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "data.db")
    try:
        value = pack()
        del value["snapshot"]["revision_id"]
        with pytest.raises(ContractError):
            store.register(value)
    finally:
        store.close()


def test_snapshot_rejects_replacing_an_existing_fact_boundary(tmp_path: Path) -> None:
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(pack())
        with pytest.raises(ContractError, match="snapshot already exists"):
            store.register(pack())
    finally:
        store.close()


def test_run_artifact_handoff_keeps_bundle_identity(tmp_path: Path) -> None:
    import zipfile

    source = tmp_path / "query-data"
    source.mkdir()
    (source / "manifest.json").write_text(json.dumps(pack()["snapshot"]), encoding="utf-8")
    archive = tmp_path / "snapshot.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.write(source / "manifest.json", "manifest.json")

    class Client:
        def download_artifact_to(self, run_id: str, artifact_id: str, destination: str) -> None:
            Path(destination).write_bytes(archive.read_bytes())

        def artifacts(self, run_id: str) -> list[dict]:
            return [{"artifact_id": "bundle-1", "sha256": "a" * 64,
                     "store_key": "query-data.zip", "kind": "data_snapshot",
                     "size_bytes": archive.stat().st_size},
                    {"artifact_id": "timing-1", "sha256": "b" * 64,
                     "store_key": "reports/timing.json", "kind": "raw_timing_report",
                     "stage_key": "route", "size_bytes": 42},
                    {"artifact_id": "runtime-1", "sha256": "c" * 64,
                     "store_key": "runtime_protocol_receipt.json",
                     "kind": "runtime_protocol_receipt", "size_bytes": 8}]

    handoff = load_run_bundle(Client(), "run-1", "bundle-1")
    refs = handoff["snapshot"]["source_artifacts"]
    assert any(item["artifact_id"] == "bundle-1" for item in refs)
    assert any(item["artifact_id"] == "timing-1" and item["stage"] == "route"
               for item in refs)
    assert all(item["artifact_id"] != "runtime-1" for item in refs)


def test_portable_objects_and_manifest_artifacts_are_indexed(tmp_path: Path) -> None:
    source = tmp_path / "query-data"
    source.mkdir()
    manifest = {**pack()["snapshot"], "source_artifacts": [{
        "artifact_id": "odb-1", "run_id": "run-1", "sha256": "a" * 64,
        "logical_path": "inputs/design.odb", "category": "input",
        "stage": "route", "format": "application/octet-stream", "size_bytes": 10,
    }]}
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (source / "objects.jsonl").write_text(
        json.dumps({"object_id": "inst:1", "snapshot_id": "snap-1",
                    "kind": "instance", "name": "u1"}) + "\n", encoding="utf-8")
    loaded = load_snapshot_directory(source)
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(loaded)
        assert store.snapshot("snap-1")["source_artifacts"][0]["artifact_id"] == "odb-1"
        assert store.find_instance("snap-1", "u1")[0]["object_id"] == "inst:1"
    finally:
        store.close()


def test_completed_snapshot_artifact_is_imported_once(tmp_path: Path) -> None:
    import zipfile

    source = tmp_path / "query-data"
    source.mkdir()
    (source / "manifest.json").write_text(json.dumps(pack()["snapshot"]), encoding="utf-8")
    archive = tmp_path / "snapshot.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.write(source / "manifest.json", "manifest.json")

    class Client:
        def runs(self, **_filters: object) -> list[dict]:
            return [{"run_id": "run-extract"}]

        def artifacts(self, run_id: str) -> list[dict]:
            assert run_id == "run-extract"
            return [{"artifact_id": "bundle-1", "kind": "data_snapshot",
                     "sha256": "a" * 64, "store_key": "query-data.zip",
                     "size_bytes": archive.stat().st_size}]

        def download_artifact_to(self, run_id: str, artifact_id: str, destination: str) -> None:
            assert (run_id, artifact_id) == ("run-extract", "bundle-1")
            Path(destination).write_bytes(archive.read_bytes())

    store = DataStore(tmp_path / "data.db")
    try:
        assert import_ready_bundles(store, Client()) == 1
        assert store.snapshot("snap-1")["run_id"] == "run-1"
        assert import_ready_bundles(store, Client()) == 0
    finally:
        store.close()


def test_stage_comparison_reports_timing_and_physical_fact_deltas(tmp_path: Path) -> None:
    placed = pack()
    placed["snapshot"] = {**placed["snapshot"], "snapshot_id": "snap-place", "stage": "place"}
    placed["entities"] = [{**item, "snapshot_id": "snap-place"} for item in placed["entities"]]
    placed["timing_paths"][0] = {**placed["timing_paths"][0], "snapshot_id": "snap-place", "slack": -0.12}
    placed["timing_points"][0] = {**placed["timing_points"][0], "net_id": "net:n1"}
    placed["physical_context"] = [
        {**placed["physical_context"][0], "snapshot_id": "snap-place", "x": 10.0, "y": 20.0},
        {**placed["physical_context"][1], "snapshot_id": "snap-place",
         "routing": [{"routing_type": "segment", "x_min": 0, "y_min": 0,
                      "x_max": 10, "y_max": 0}]},
    ]
    routed = {
        **placed,
        "snapshot": {**placed["snapshot"], "snapshot_id": "snap-route", "stage": "route"},
        "entities": [{**item, "snapshot_id": "snap-route"} for item in placed["entities"]],
        "timing_paths": [{**placed["timing_paths"][0], "snapshot_id": "snap-route", "slack": -0.58}],
        "physical_context": [
            {**placed["physical_context"][0], "snapshot_id": "snap-route", "x": 14.0, "y": 24.0},
            {**placed["physical_context"][1], "snapshot_id": "snap-route",
             "routing": [{"routing_type": "segment", "x_min": 0, "y_min": 0,
                          "x_max": 18, "y_max": 0}]},
        ],
    }
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(placed)
        store.register(routed)
        comparison = compare_timing_path(store, "snap-place", "snap-route", "path-1")
        assert comparison["status"] == "COMPARABLE"
        assert comparison["matching"]["basis"] == "scoped_name"
        assert comparison["timing"]["slack"]["delta"] == pytest.approx(-0.46)
        assert comparison["physical"]["instances"][0]["delta"] == {"x": 4.0, "y": 4.0}
        assert comparison["physical"]["nets"][0]["wire_length"]["delta"] == 8
        assert comparison["matched_objects"]
        assert all(item["matching_basis"] == "scoped_name"
                   for item in comparison["matched_objects"])
        assert all("identity" in item and "evidence" in item
                   for item in comparison["matched_objects"])
        assert {row["predicate"] for row in comparison["relations"]} == {
            "same_design_object_as"
        }
        assert all(row["matching_basis"] == "scoped_name" for row in comparison["relations"])
    finally:
        store.close()


def test_stage_comparison_rejects_different_design_revision(tmp_path: Path) -> None:
    placed = pack()
    routed = {
        **placed,
        "snapshot": {**placed["snapshot"], "snapshot_id": "snap-other",
                      "design_id": "other-chip"},
    }
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(placed)
        store.register(routed)
        comparison = compare_timing_path(store, "snap-1", "snap-other", "path-1")
        assert comparison["status"] == "INCOMPARABLE"
        assert comparison["matching"]["reasons"][0]["field"] == "design"
        assert "timing" not in comparison
    finally:
        store.close()


def test_stage_comparison_rejects_different_path_identity(tmp_path: Path) -> None:
    placed = pack()
    routed = {
        **placed,
        "snapshot": {**placed["snapshot"], "snapshot_id": "snap-route"},
        "timing_paths": [{**placed["timing_paths"][0],
                           "snapshot_id": "snap-route", "check": "hold"}],
    }
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(placed)
        store.register(routed)
        comparison = compare_timing_path(store, "snap-1", "snap-route", "path-1")
        assert comparison["status"] == "INCOMPARABLE"
        assert any(item["field"] == "check" for item in comparison["matching"]["reasons"])
        assert "timing" not in comparison
    finally:
        store.close()


def test_stage_comparison_uses_canonical_identity_when_native_ids_change(tmp_path: Path) -> None:
    placed = pack()
    routed = {
        **placed,
        "snapshot": {**placed["snapshot"], "snapshot_id": "snap-route"},
        "entities": [
            {"object_id": "native-inst-2", "snapshot_id": "snap-route",
             "kind": "instance", "name": "u1"},
            {"object_id": "native-net-2", "snapshot_id": "snap-route",
             "kind": "net", "name": "n1"},
        ],
        "timing_paths": [{**placed["timing_paths"][0], "snapshot_id": "snap-route",
                           "slack": -0.4}],
        "timing_points": [{"point_id": "point-route", "path_id": "path-1",
                            "ordinal": 0, "object_id": "native-inst-2",
                            "net_id": "native-net-2"}],
        "physical_context": [
            {"object_id": "native-inst-2", "snapshot_id": "snap-route",
             "x": 14.0, "y": 24.0},
            {"object_id": "native-net-2", "snapshot_id": "snap-route",
             "routing": [{"routing_type": "segment", "x_min": 0, "y_min": 0,
                           "x_max": 18, "y_max": 0}]},
        ],
    }
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(placed)
        store.register(routed)
        comparison = compare_timing_path(store, "snap-1", "snap-route", "path-1")
        assert comparison["physical"]["instances"][0]["from_object_id"] == "top/u1"
        assert comparison["physical"]["instances"][0]["to_object_id"] == "native-inst-2"
        assert all(row["matching_basis"] == "scoped_name" for row in comparison["relations"])
    finally:
        store.close()


@pytest.mark.parametrize(
    ("field", "expected"),
    (("native_path_id", "native_exact"),
     ("structural_fingerprint", "structural_verified")),
)
def test_stage_comparison_reports_explicit_path_matching_basis(
        tmp_path: Path, field: str, expected: str) -> None:
    placed = pack()
    placed["timing_paths"][0][field] = "path-proof"
    routed = {
        **placed,
        "snapshot": {**placed["snapshot"], "snapshot_id": "snap-route"},
        "entities": [{**item} for item in placed["entities"]],
        "timing_paths": [{**placed["timing_paths"][0], "snapshot_id": "snap-route",
                           "slack": -0.4}],
    }
    store = DataStore(tmp_path / "data.db")
    try:
        store.register(placed)
        store.register(routed)
        comparison = compare_timing_path(store, "snap-1", "snap-route", "path-1")
        assert comparison["status"] == "COMPARABLE"
        assert comparison["matching"]["basis"] == expected
    finally:
        store.close()


def test_scale_object_lookup_is_indexed_and_complete(tmp_path: Path) -> None:
    """CONTRACT section 5: an object query must not depend on table size.

    The previous implementation read the first 10000 entities and filtered in
    Python, so an object past row 10000 looked absent while returning HTTP 200.
    """
    total = 12050
    value = {
        "snapshot": {
            "snapshot_id": "snap-scale", "design_id": "chip", "revision_id": "rev-1",
            "run_id": "run-scale", "stage": "route",
            "created_at": "2026-01-01T00:00:00Z",
        },
        "entities": [
            {"object_id": f"inst:{i}", "snapshot_id": "snap-scale",
             "kind": "instance", "name": f"u{i:05d}"}
            for i in range(total)
        ],
        "relations": [
            {"relation_id": f"rel:{i}", "snapshot_id": "snap-scale",
             "subject_id": f"inst:{i}", "predicate": "connected_to",
             "object_id": f"net:{i}"}
            for i in range(total)
        ],
        "physical_context": [
            {"object_id": f"inst:{i}", "snapshot_id": "snap-scale",
             "instance_name": f"u{i:05d}", "x": float(i), "y": 0.0}
            for i in range(total)
        ],
    }
    store = DataStore(tmp_path / "scale.db")
    try:
        store.register(value)
        far = total - 1
        found = store.find_instance("snap-scale", f"u{far:05d}")
        assert [row["object_id"] for row in found] == [f"inst:{far}"]

        context = object_context(store, "snap-scale", f"inst:{far}")
        assert context["target"]["id"] == f"inst:{far}"
        assert [row["relation_id"] for row in context["relations"]] == [f"rel:{far}"]
        assert context["physical_context"][0]["x"] == float(far)

        plan = list(store.connection.execute(
            "EXPLAIN QUERY PLAN SELECT payload FROM records "
            "WHERE snapshot_id = ? AND record_type = ? "
            "AND json_extract(payload, '$.name') = ?",
            ("snap-scale", "entities", f"u{far:05d}")))
        detail = " ".join(str(row["detail"]) for row in plan)
        assert "records_json_name" in detail, detail
        assert "SEARCH" in detail.upper(), detail
    finally:
        store.close()


def test_list_pagination_reports_total_and_truncation(tmp_path: Path) -> None:
    """CONTRACT section 5: count is the total, not the page size."""
    value = pack()
    value["timing_paths"] = [
        {"path_id": f"path-{index}", "snapshot_id": "snap-1",
         "analysis": "view", "check": "setup", "group": "clk",
         "startpoint": "top/u1/A", "endpoint": "top/u2/Z",
         "corner": "slow", "unit": "s"}
        for index in range(5)
    ]
    store = DataStore(tmp_path / "page.db")
    try:
        store.register(value)
        first = list_timing_paths(store, "snap-1", {"limit": "2", "offset": "0"})
        assert first["count"] == 5
        assert first["returned"] == 2
        assert first["truncated"] is True
        assert first["next_offset"] == 2
        last = list_timing_paths(store, "snap-1", {"limit": "2", "offset": "4"})
        assert last["returned"] == 1
        assert last["truncated"] is False
        assert last["next_offset"] is None
    finally:
        store.close()


def test_canonical_metrics_project_orfs_stage_keys(tmp_path: Path) -> None:
    """A 66-key stage report becomes a small canonical set plus raw keys."""
    value = pack()
    value["snapshot"]["stage"] = "finish"
    value["observations"] = [
        {"observation_id": "metric:finish__timing__setup__ws", "kind": "metric",
         "value": -0.04544, "status": "parsed", "context": {"scene": "setup"}},
        {"observation_id": "metric:finish__timing__setup__tns", "kind": "metric",
         "value": -0.737691, "status": "parsed"},
        {"observation_id": "metric:finish__design__instance__count", "kind": "metric",
         "value": 655, "status": "parsed"},
        {"observation_id": "metric:finish__power__total", "kind": "metric",
         "value": 0.00373869, "status": "parsed"},
        {"observation_id": "metric:finish__clock__skew__setup", "kind": "metric",
         "value": 0.00129502, "status": "parsed"},
        {"observation_id": "metric:run__flow__platform__time_units", "kind": "metric",
         "value": "1ns", "status": "parsed"},
        {"observation_id": "metric:run__flow__platform__power_units", "kind": "metric",
         "value": "1nW", "status": "parsed"},
        {"observation_id": "metric:run__flow__platform__distance_units", "kind": "metric",
         "value": "1um", "status": "parsed"},
    ]
    store = DataStore(tmp_path / "canonical.db")
    try:
        store.register(value)
        result = list_metrics_for_run(store, "run-1", {})
        rows = {row["name"]: row for row in result["metrics"]}
        assert rows["WNS"]["value"] == -0.04544
        assert rows["WNS"]["unit"] == "ns"
        assert rows["WNS"]["analysis"] == "setup"
        assert rows["WNS"]["authoritative_source"] == "orfs_stage_report"
        assert rows["WNS"]["raw_key"] == "finish__timing__setup__ws"
        assert rows["WNS"]["status"] == "available"
        assert rows["TNS"]["value"] == -0.737691
        assert rows["INSTANCE_COUNT"]["unit"] == "count"
        assert rows["POWER_TOTAL"]["status"] == "partial"
        assert "1nW" in rows["POWER_TOTAL"]["reason"]
        assert rows["RUNTIME"]["status"] == "unavailable"
        assert "finish__clock__skew__setup" not in rows
        raw_result = list_metrics_for_run(store, "run-1", {"include_raw": "1"})
        raw_keys = {row["raw_key"] for row in raw_result["raw_metrics"]}
        assert "finish__clock__skew__setup" in raw_keys
        assert "run__flow__platform__time_units" in raw_keys
        assert result["metrics"][0]["stage"] == "finish"
    finally:
        store.close()


def test_context_detail_summary_projects_neighbour_geometry(tmp_path: Path) -> None:
    """CONTRACT 4.8 / 4.10: context packs are projected unless detail=full."""
    value = pack()
    value["entities"].append({
        "object_id": "top/u1/A", "snapshot_id": "snap-1", "kind": "pin",
        "name": "u1/A", "parent_id": "top/u1",
        "attributes": {"geometry": [{"geometry_type": "rect", "x_min": 1, "y_min": 2,
                                     "x_max": 3, "y_max": 4}]}})
    value["physical_context"].append({
        "object_id": "top/u1/A", "snapshot_id": "snap-1",
        "geometry": [{"geometry_type": "rect", "x_min": 1, "y_min": 2,
                      "x_max": 3, "y_max": 4}],
        "routing": [{"routing_type": "segment", "x_min": 0, "x_max": 5,
                     "y_min": 0, "y_max": 0}]})
    store = DataStore(tmp_path / "detail.db")
    try:
        store.register(value)
        summary = object_context(store, "snap-1", "top/u1")
        assert summary["detail"] == "summary"
        child = next(row for row in summary["entities"] if row["object_id"] == "top/u1/A")
        assert "geometry" not in child["attributes"]
        child_physical = next(row for row in summary["physical_context"]
                              if row["object_id"] == "top/u1/A")
        assert "geometry" not in child_physical and "routing" not in child_physical
        target = next(row for row in summary["physical_context"]
                      if row["object_id"] == "top/u1")
        assert target["x"] == 10.0

        full = object_context(store, "snap-1", "top/u1", detail="full")
        assert full["detail"] == "full"
        assert len(json.dumps(full)) > len(json.dumps(summary))
        child_full = next(row for row in full["entities"] if row["object_id"] == "top/u1/A")
        assert child_full["attributes"]["geometry"]

        with pytest.raises(ValueError):
            object_context(store, "snap-1", "top/u1", detail="verbose")
    finally:
        store.close()


def test_name_lookup_finds_the_hierarchical_name(tmp_path: Path) -> None:
    """CONTRACT 4.9: name or hierarchical name, through an index not a scan."""
    value = pack()
    value["entities"] = [{
        "object_id": "inst:1", "snapshot_id": "snap-1", "kind": "instance",
        "name": "short_name",
        "attributes": {"hierarchical_name": "top/deep/long_name",
                       "native_id": "1"}}]
    store = DataStore(tmp_path / "named.db")
    try:
        store.register(value)
        assert [row["object_id"] for row in
                store.find_instance("snap-1", "short_name")] == ["inst:1"]
        assert [row["object_id"] for row in
                store.find_instance("snap-1", "top/deep/long_name")] == ["inst:1"]
        assert store.find_instance("snap-1", "not-a-name") == []

        # The index must exist for the lookup to stay a search on a real design;
        # asserting a plan on a one-row fixture would only test SQLite's cost
        # heuristics.
        indexes = {row[0] for row in store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' "
            "AND tbl_name = 'records'")}
        assert "records_json_hier_name" in indexes, indexes
    finally:
        store.close()


def test_context_relation_cap_is_reported(tmp_path: Path) -> None:
    """CONTRACT 4.8: a context cap must say that it bit."""
    value = pack()
    value["relations"] = [
        {"relation_id": f"r{index}", "snapshot_id": "snap-1",
         "subject_id": "top/u1", "predicate": "connected_to",
         "object_id": f"net:{index}"} for index in range(5)]
    store = DataStore(tmp_path / "cap.db")
    try:
        store.register(value)
        uncapped = object_context(store, "snap-1", "top/u1", relation_limit=0)
        assert len(uncapped["relations"]) == 5
        assert "relations_truncated" not in uncapped

        capped = object_context(store, "snap-1", "top/u1", relation_limit=2)
        assert len(capped["relations"]) == 2
        assert capped["relations_truncated"] is True
        assert capped["relations_total"] == 5
        assert capped["relation_limit"] == 2
        assert capped["limitations"][0]["status"] == "truncated"
        assert capped["limitations"][0]["total"] == 5

        with pytest.raises(ValueError):
            object_context(store, "snap-1", "top/u1", relation_limit=-1)
    finally:
        store.close()


def test_metric_rows_state_whether_a_corner_was_declared(tmp_path: Path) -> None:
    """CONTRACT 5 rule 3: a corner the source omits is stated, not left as null."""
    store = DataStore(tmp_path / "corner.db")
    try:
        value = {
            "snapshot": {"snapshot_id": "snap-1", "design_id": "chip",
                         "revision_id": "rev-1", "run_id": "run-1",
                         "stage": "finish", "created_at": "2026-01-01T00:00:00Z"},
            "observations": [
                {"observation_id": "metric:finish__timing__setup__ws",
                 "snapshot_id": "snap-1", "kind": "metric", "value": -0.04,
                 "status": "parsed", "context": {}, "evidence": []},
                {"observation_id": "metric:finish__design__instance__area",
                 "snapshot_id": "snap-1", "kind": "metric", "value": 903.3,
                 "status": "parsed", "context": {"corner": "typical"},
                 "evidence": []},
            ],
            "relations": [], "entities": [], "timing_paths": [], "timing_points": [],
            "physical_context": [],
        }
        store.register(value)
        rows = {row["name"]: row for row in project_run(store, [store.snapshot("snap-1")])["metrics"]}
        assert rows["WNS"]["corner_status"] == "not_declared"
        assert rows["WNS"]["corner"] is None
        assert rows["WNS"]["status"] in {"available", "partial"}
        assert rows["AREA"]["corner_status"] == "declared"
        assert rows["AREA"]["corner"] == "typical"
        assert rows["RUNTIME"]["corner_status"] == "not_declared"
    finally:
        store.close()


def test_envelope_lifts_nested_evidence_and_declares_its_absence() -> None:
    """CONTRACT 1: provenance on the envelope, and never an unexplained empty list."""
    reference = {"artifact_id": "art-1", "logical_path": "query-data/timing_report.json"}
    lifted = envelope("/snapshots/snap-1/timing-paths/path-1", {},
                      {"timing_path": {"path_id": "path-1", "evidence": [reference]}})
    assert lifted["evidence"] == [reference]

    from_rows = envelope("/runs/run-1/metrics", {},
                         {"metrics": [{"name": "WNS", "evidence": [reference]}]})
    assert from_rows["evidence"] == [reference]

    absent = envelope("/snapshots", {}, {"snapshots": []})
    assert len(absent["evidence"]) == 1
    assert absent["evidence"][0]["status"] == "unavailable"
    assert absent["evidence"][0]["tool"] == "list_snapshots"


def test_physical_records_carry_the_placement_origin() -> None:
    """CONTRACT 4.11: x/y come from the adapter marker; ingesting dropped them."""
    from openroad_app_data_foundation.ingest import _physical_records

    records = _physical_records([{
        "object_id": "inst:1", "snapshot_id": "snap-1", "instance_name": "u1",
        "x": 16340, "y": 8400,
        "bbox": {"x_min": 16340, "y_min": 8400, "x_max": 17100, "y_max": 11200},
    }])
    assert records[0]["x"] == 16340 and records[0]["y"] == 8400
    assert records[0]["bbox"]["x_min"] == 16340


def test_physical_records_leave_an_absent_origin_absent() -> None:
    """A pin marker has geometry but no placement: x/y stay None, not invented."""
    from openroad_app_data_foundation.ingest import _physical_records

    records = _physical_records([{
        "object_id": "iterm:1", "snapshot_id": "snap-1",
        "geometry": [{"geometry_type": "rect", "coordinate_space": "master"}],
    }])
    assert records[0]["x"] is None and records[0]["y"] is None
    assert records[0]["bbox"] is None


def test_metric_availability_list_respects_the_requested_scope(tmp_path: Path) -> None:
    """A snapshot-scoped request must not advertise another stage's metric."""
    store = DataStore(tmp_path / "scope.db")
    try:
        store.register({
            "snapshot": {"snapshot_id": "snap-finish", "design_id": "chip",
                         "revision_id": "rev-1", "run_id": "run-1", "stage": "finish",
                         "created_at": "2026-01-01T00:00:00Z"},
            "observations": [
                # without a time-unit declaration the projection correctly calls
                # WNS partial, so the fixture has to declare it
                {"observation_id": "metric:finish__flow__platform__time_units",
                 "kind": "metric", "snapshot_id": "snap-finish", "value": "1ns",
                 "status": "parsed", "context": {}, "evidence": []},
                {"observation_id": "metric:finish__timing__setup__ws", "kind": "metric",
                 "snapshot_id": "snap-finish", "value": -0.04, "status": "parsed",
                 "context": {}, "evidence": []}],
        })
        store.register({
            "snapshot": {"snapshot_id": "snap-route", "design_id": "chip",
                         "revision_id": "rev-1", "run_id": "run-1", "stage": "route",
                         "created_at": "2026-01-01T00:00:00Z"},
            "observations": [
                {"observation_id": "metric:route__design__instance__count", "kind": "metric",
                 "snapshot_id": "snap-route", "value": 10, "status": "parsed",
                 "context": {}, "evidence": []}],
        })
        from openroad_app_data_foundation.metrics import project_run
        from openroad_app_data_foundation.queries import list_metrics_for_run

        run_wide = project_run(store, store.snapshots(run_id="run-1"))
        assert "WNS" in run_wide["canonical_names_available"]

        scoped = list_metrics_for_run(store, "run-1", {"snapshot_id": "snap-route"})
        assert scoped["canonical_names_available"] == ["INSTANCE_COUNT"], scoped[
            "canonical_names_available"]
    finally:
        store.close()


def test_import_skips_a_superseded_bundle_instead_of_failing(tmp_path: Path) -> None:
    """One stale bundle must not take the interface down.

    The importer runs on every GET, so a bundle whose snapshot already exists used
    to raise ContractError out of the request and every query answered an error -
    which is what happened while re-extracting a snapshot.
    """
    from unittest.mock import patch

    from openroad_app_data_foundation.bundle import import_ready_bundles

    class FakeKernel:
        def runs(self, *, status: str, limit: int):
            return [{"run_id": "run-1"}]

        def artifacts(self, run_id: str):
            return [{"kind": "data_snapshot", "artifact_id": "art-superseded"}]

    store = DataStore(tmp_path / "superseded.db")
    try:
        store.register({"snapshot": {"snapshot_id": "snap-1", "design_id": "chip",
                                     "revision_id": "rev-1", "run_id": "run-1",
                                     "stage": "route",
                                     "created_at": "2026-01-01T00:00:00Z"}})
        same_pack = {"snapshot": {"snapshot_id": "snap-1", "design_id": "chip",
                                  "revision_id": "rev-1", "run_id": "run-1",
                                  "stage": "route",
                                  "created_at": "2026-01-02T00:00:00Z"}}
        with patch("openroad_app_data_foundation.bundle.load_run_bundle",
                   return_value=same_pack):
            imported = import_ready_bundles(store, FakeKernel())
        assert imported == 0
        assert store.imported("art-superseded"), "the stale bundle must be marked seen"
        assert len(store.snapshots()) == 1
    finally:
        store.close()


def test_evidence_index_filters_by_record_type_and_flags_unknown(tmp_path: Path) -> None:
    """A type filter must narrow the scan, and an unknown one must not be ignored."""
    from openroad_app_data_foundation.queries import list_evidence

    store = DataStore(tmp_path / "evidence.db")
    try:
        store.register({
            "snapshot": {"snapshot_id": "snap-1", "design_id": "chip",
                         "revision_id": "rev-1", "run_id": "run-1", "stage": "route",
                         "created_at": "2026-01-01T00:00:00Z"},
            "observations": [{"observation_id": "obs:1", "kind": "metric",
                              "snapshot_id": "snap-1", "value": 1, "status": "parsed",
                              "context": {}, "evidence": [{"artifact_kind": "raw"}]}],
            "relations": [{"relation_id": "rel:1", "predicate": "loads",
                           "subject_id": "net:1",
                           "object_id": "iterm:1", "snapshot_id": "snap-1",
                           "evidence": [{"artifact_kind": "raw"}]}],
        })
        filtered = list_evidence(store, "snap-1", {"record_type": "observations",
                                                   "limit": "10"})
        assert [row["record_type"] for row in filtered["evidence"]] == ["observations"]
        assert filtered["filters"] == {"record_type": "observations"}

        unfiltered = list_evidence(store, "snap-1", {"limit": "10"})
        assert len({row["record_type"] for row in unfiltered["evidence"]}) > 1

        unknown = list_evidence(store, "snap-1", {"record_type": "nonsense"})
        assert unknown["evidence"] == [] and unknown["missing"] == ["record_type"]
    finally:
        store.close()


def test_a_statement_cannot_invalidate_another_threads_rows(tmp_path: Path) -> None:
    """Rows must be read out under the lock, not lazily by the caller.

    The server shares one connection across request threads.  When execute()
    handed back a live cursor, a second statement on that connection reset the
    first cursor's results, which showed up as a null payload (TypeError) and as a
    snapshot that exists answering "snapshot not found".
    """
    store = DataStore(tmp_path / "cursor.db")
    try:
        store.register({"snapshot": {"snapshot_id": "snap-1", "design_id": "chip",
                                     "revision_id": "rev-1", "run_id": "run-1",
                                     "stage": "route",
                                     "created_at": "2026-01-01T00:00:00Z"}})
        cursor = store.connection.execute(
            "SELECT payload FROM snapshots WHERE snapshot_id = ?", ("snap-1",))
        store.connection.execute("SELECT payload FROM snapshots")   # in between
        row = cursor.fetchone()
        assert row is not None and row["payload"] is not None
        assert store.snapshot("snap-1")["snapshot_id"] == "snap-1"
    finally:
        store.close()


def test_concurrent_readers_do_not_break_each_other(tmp_path: Path) -> None:
    """A threaded stress on the shared connection: no errors, no lost rows."""
    import threading

    store = DataStore(tmp_path / "threads.db")
    try:
        store.register({
            "snapshot": {"snapshot_id": "snap-1", "design_id": "chip",
                         "revision_id": "rev-1", "run_id": "run-1", "stage": "route",
                         "created_at": "2026-01-01T00:00:00Z"},
            "observations": [{"observation_id": "obs:1", "kind": "metric",
                              "snapshot_id": "snap-1", "value": 1,
                              "status": "parsed", "context": {}, "evidence": []}],
        })
        failures: list[str] = []

        def reader() -> None:
            for _ in range(150):
                try:
                    assert store.snapshot("snap-1")["snapshot_id"] == "snap-1"
                    assert len(store.records("snap-1", "observations")) == 1
                except Exception as exc:                     # noqa: BLE001
                    failures.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=reader) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert failures == [], failures[:3]
    finally:
        store.close()
