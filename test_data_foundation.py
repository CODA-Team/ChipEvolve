"""Deterministic data-foundation business tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from openroad_platform_contracts import ContractError

from openroad_app_data_foundation.bundle import import_ready_bundles, load_run_bundle
from openroad_app_data_foundation.ingest import load_snapshot_directory
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
        assert store.net("snap-1", "net:n1")["physical_context"]["routing"]
        assert store.run_summary("snap-1")["record_counts"]["timing_paths"] == 1
        assert store.run_summary_for_run("run-1")["snapshots"][0]["snapshot"][
            "snapshot_id"] == "snap-1"
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
                     "size_bytes": archive.stat().st_size}]

    handoff = load_run_bundle(Client(), "run-1", "bundle-1")
    assert handoff["snapshot"]["source_artifacts"][0]["artifact_id"] == "bundle-1"


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
