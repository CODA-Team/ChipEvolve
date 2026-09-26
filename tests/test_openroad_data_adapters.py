"""Business tests for the replaceable native-data capability boundary."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "plugins" / "openroad-data" / "adapter.py"


def _run_adapter(tmp_path: Path, task: dict, *, expected_exit: int = 0) -> dict:
    request = tmp_path / "request.json"
    result = tmp_path / "result.json"
    request.write_text(json.dumps({"task": task}), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(ADAPTER), "--request", str(request),
         "--result", str(result)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == expected_exit, completed.stderr
    return json.loads(result.read_text(encoding="utf-8"))


def _task(inputs: dict) -> dict:
    return {"inputs": {"snapshot_id": "snap-1", "design_id": "chip",
                        "revision_id": "rev-1", "run_id": "run-1",
                        "created_at": "2026-01-01T00:00:00Z", **inputs}}


def test_orfs_adapter_reads_structured_metadata_without_log_scraping(tmp_path: Path) -> None:
    (tmp_path / "metadata.json").write_text(json.dumps({
        "metrics": {"wns": -0.2, "tns": -1.3},
        "stages": [{"stage_id": "route", "status": "succeeded"}],
    }), encoding="utf-8")
    result = _run_adapter(tmp_path, _task({"adapter": "orfs",
                                           "metadata_path": "metadata.json"}))
    assert result["status"] == "succeeded"
    assert {item["kind"] for item in result["artifacts"]} == {
        "data_snapshot", "extractor_log", "extractor_receipt"}
    with zipfile.ZipFile(tmp_path / "query-data.zip") as archive:
        observations = json.loads(archive.read("observations.jsonl").splitlines()[0])
        assert observations["kind"] == "metric"
        assert observations["evidence"][0]["detail"]["field"] == "metrics.tns"


def test_opendb_plan_uses_native_openroad_entrypoint(tmp_path: Path) -> None:
    result = _run_adapter(tmp_path, _task({"adapter": "opendb", "odb_path": "design.odb",
                                           "openroad_bin": "/opt/openroad/bin/openroad"}),
                          expected_exit=2)
    assert result["status"] == "failed"
    script = (tmp_path / "opendb_extract.tcl").read_text(encoding="utf-8")
    assert "read_db \"design.odb\"" in script
    assert "ord::get_db" in script
    assert "getITerms" in script
    assert {item["kind"] for item in result["artifacts"]} == {
        "extractor_log", "extractor_receipt"}


def test_opensta_plan_uses_native_dbnetwork_conversion(tmp_path: Path) -> None:
    _run_adapter(tmp_path, _task({"adapter": "opensta", "odb_path": "design.odb",
                                  "openroad_bin": "/does/not/exist"}), expected_exit=2)
    script = (tmp_path / "opensta_extract.tcl").read_text(encoding="utf-8")
    assert "sta::sta_to_db_pin" in script
    assert "sta::sta_to_db_port" in script
    assert "lappend db_mapping $pin_name" in script
    assert "lappend db_mapping [json_q $pin_name]" not in script


def test_opensta_normalization_consumes_native_mapping_receipt(tmp_path: Path) -> None:
    fake = tmp_path / "fake-openroad"
    fake.write_text("""#!/usr/bin/env python3
import json
from pathlib import Path
out = Path('query-data')
out.mkdir()
(out / 'timing_report.json').write_text(json.dumps({'checks': [{
    'path_id': 'path:0', 'check': 'setup', 'points': [
        {'pin': 'u1/A', 'arrival': 1.0}, {'pin': 'clk', 'arrival': 0.0}
    ]}]}))
(out / 'dbnetwork_map.json').write_text(json.dumps({
    'u1/A': {'dbnetwork': 'native', 'pin_id': 'iterm:1',
             'instance_id': 'inst:2', 'net_id': 'net:3'},
    'clk': {'dbnetwork': 'native', 'pin_id': 'bterm:4', 'net_id': 'net:5'}
}))
""", encoding="utf-8")
    fake.chmod(0o755)
    _run_adapter(tmp_path, _task({"adapter": "opensta", "odb_path": "design.odb",
                                  "openroad_bin": str(fake)}))
    output = tmp_path / "query-data"
    rows = [json.loads(line) for line in
            (output / "timing_points.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["mapping_status"] for row in rows] == ["mapped", "mapped"]
    assert rows[0]["instance_id"] == "inst:2"
    assert rows[1]["pin_id"] == "bterm:4"


def test_openroad_snapshot_combines_native_physical_and_timing_facts(tmp_path: Path) -> None:
    fake = tmp_path / "fake-openroad"
    fake.write_text("""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

out = Path('query-data')
out.mkdir(exist_ok=True)
script = Path(sys.argv[-1]).name
if script == 'opendb_extract.tcl':
    (out / 'manifest.json').write_text(json.dumps({
        'snapshot_id': 'snap-1', 'design_id': 'chip', 'revision_id': 'rev-1',
        'run_id': 'run-1', 'stage': 'route', 'created_at': '2026-01-01T00:00:00Z'
    }))
    (out / 'summary.json').write_text('{}')
    (out / 'objects.jsonl').write_text(json.dumps({
        'object_id': 'inst:2', 'snapshot_id': 'snap-1', 'kind': 'instance', 'name': 'u1'
    }) + '\\n')
    (out / 'relations.jsonl').write_text('')
    (out / 'markers.jsonl').write_text('')
else:
    (out / 'timing_report.json').write_text(json.dumps({'checks': [{
        'path_id': 'path:0', 'check': 'setup', 'points': [{'pin': 'u1/A'}]
    }]}))
    (out / 'dbnetwork_map.json').write_text(json.dumps({
        'u1/A': {'dbnetwork': 'native', 'pin_id': 'iterm:1', 'instance_id': 'inst:2'}
    }))
""", encoding="utf-8")
    fake.chmod(0o755)

    result = _run_adapter(tmp_path, _task({
        "adapter": "openroad", "odb_path": "design.odb", "openroad_bin": str(fake),
    }))

    assert result["status"] == "succeeded"
    with zipfile.ZipFile(tmp_path / "query-data.zip") as archive:
        assert json.loads(archive.read("objects.jsonl").splitlines()[0])["object_id"] == "inst:2"
        assert json.loads(archive.read("timing_points.jsonl").splitlines()[0])["instance_id"] == "inst:2"
