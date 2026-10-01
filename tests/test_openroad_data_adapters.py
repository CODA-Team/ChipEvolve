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
        "data_snapshot", "extractor_log", "extractor_receipt", "raw_flow_metadata"}
    assert next(item for item in result["artifacts"]
                if item["kind"] == "raw_flow_metadata")["path"] == "metadata.json"
    with zipfile.ZipFile(tmp_path / "query-data.zip") as archive:
        observations = json.loads(archive.read("observations.jsonl").splitlines()[0])
        assert observations["kind"] == "metric"
        assert observations["evidence"][0]["detail"]["field"] == "metrics.tns"
        assert observations["evidence"][0]["artifact_kind"] == "raw_flow_metadata"


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


def test_opendb_plan_preserves_pin_geometry_and_via_layers(tmp_path: Path) -> None:
    _run_adapter(tmp_path, _task({"adapter": "opendb", "odb_path": "design.odb",
                                  "openroad_bin": "/does/not/exist"}), expected_exit=2)
    script = (tmp_path / "opendb_extract.tcl").read_text(encoding="utf-8")
    assert "getMPins" in script
    assert "getGeometry" in script
    assert "getBPins" in script
    assert "geometry_type [json_q via]" in script
    assert "bottom_layer" in script and "top_layer" in script
    assert "db_pin_geometry $pin_geometry master" in script


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
    assert rows[0]["evidence"][0]["artifact_kind"] == "raw_timing_report"
    assert "artifact_id" not in rows[0]["evidence"][0]
    assert rows[0]["evidence"][0]["logical_path"] == "query-data/timing_report.json"


def test_opensta_does_not_promote_unmapped_report_ids_to_physical_identity(tmp_path: Path) -> None:
    fake = tmp_path / "fake-openroad"
    fake.write_text("""#!/usr/bin/env python3
import json
from pathlib import Path
out = Path('query-data')
out.mkdir()
(out / 'timing_report.json').write_text(json.dumps({'checks': [{
    'points': [{'pin': 'u1/A', 'instance_id': 'unverified-instance'}]
}]}))
""", encoding="utf-8")
    fake.chmod(0o755)
    _run_adapter(tmp_path, _task({"adapter": "opensta", "odb_path": "design.odb",
                                  "openroad_bin": str(fake)}))
    row = json.loads((tmp_path / "query-data/timing_points.jsonl").read_text().splitlines()[0])
    assert row["mapping_status"] == "unmapped"
    assert row["mapping_basis"] == "none"
    assert "instance_id" not in row


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


def test_successful_native_extraction_registers_raw_design_inputs(tmp_path: Path) -> None:
    fake = tmp_path / "fake-openroad"
    fake.write_text("""#!/usr/bin/env python3
import json
from pathlib import Path
out = Path('query-data')
out.mkdir(exist_ok=True)
(out / 'manifest.json').write_text(json.dumps({
    'snapshot_id': 'snap-1', 'design_id': 'chip', 'revision_id': 'rev-1',
    'run_id': 'run-1', 'stage': 'route', 'created_at': '2026-01-01T00:00:00Z'
}))
(out / 'summary.json').write_text('{}')
""", encoding="utf-8")
    fake.chmod(0o755)
    (tmp_path / "design.odb").write_bytes(b"odb")
    (tmp_path / "constraints.sdc").write_text("create_clock clk\n", encoding="utf-8")
    result = _run_adapter(tmp_path, _task({
        "adapter": "opendb", "odb_path": "design.odb",
        "sdc_path": "constraints.sdc", "openroad_bin": str(fake),
    }))
    assert result["status"] == "succeeded"
    by_kind = {item["kind"]: item for item in result["artifacts"]}
    assert by_kind["raw_design_database"]["path"] == "design.odb"
    assert by_kind["raw_constraints"]["path"] == "constraints.sdc"


def test_openroad_report_uses_allowlisted_official_report_modes(tmp_path: Path) -> None:
    fake = tmp_path / "fake-openroad"
    fake.write_text("""#!/usr/bin/env python3
from pathlib import Path
Path('reports').mkdir(exist_ok=True)
Path('reports/timing.json').write_text('{\\"checks\\": [{\\"slack\\": -0.1}]}\\n')
""", encoding="utf-8")
    fake.chmod(0o755)
    (tmp_path / "design.odb").write_bytes(b"odb")
    result = _run_adapter(tmp_path, _task({
        "adapter": "report", "report": "timing", "odb_path": "design.odb",
        "openroad_bin": str(fake),
    }))
    assert result["status"] == "succeeded"
    by_kind = {item["kind"]: item for item in result["artifacts"]}
    assert by_kind["analysis_report"]["path"] == "reports/timing.json"
    assert by_kind["analysis_script"]["path"] == "openroad_report.tcl"
    assert by_kind["analysis_result"]["path"] == "analysis_result.json"
    analysis_result = json.loads((tmp_path / "analysis_result.json").read_text())
    assert analysis_result["record_count"] == 1
    assert analysis_result["records"][0]["evidence"][0]["json_pointer"] == "/checks/0"
    assert {metric["name"] for metric in result["metrics"]} == {
        "timing_path_count", "worst_slack"}
    assert next(metric for metric in result["metrics"] if metric["name"] == "worst_slack")[
        "value"] == -0.1
    receipt = json.loads((tmp_path / "extractor_receipt.json").read_text())
    assert receipt["parse_status"] == "parsed"
    assert receipt["result_path"] == "analysis_result.json"
    assert "report_checks -path_delay max -format json" in (
        tmp_path / "openroad_report.tcl").read_text(encoding="utf-8")


def test_openroad_report_rejects_unlisted_commands(tmp_path: Path) -> None:
    result = _run_adapter(tmp_path, _task({
        "adapter": "report", "report": "arbitrary_shell", "odb_path": "design.odb",
    }), expected_exit=2)
    assert result["status"] == "failed"
    assert result["failure"]["category"] == "configuration_error"


def test_openroad_area_report_is_structured_from_official_line(tmp_path: Path) -> None:
    fake = tmp_path / "fake-openroad"
    fake.write_text("""#!/usr/bin/env python3
from pathlib import Path
Path('reports').mkdir(exist_ok=True)
Path('reports/area.rpt').write_text('Design area 670 um^2 10% utilization.\\n')
""", encoding="utf-8")
    fake.chmod(0o755)
    (tmp_path / "design.odb").write_bytes(b"odb")
    result = _run_adapter(tmp_path, _task({
        "adapter": "report", "report": "area", "odb_path": "design.odb",
        "openroad_bin": str(fake),
    }))
    assert result["status"] == "succeeded"
    assert {metric["name"] for metric in result["metrics"]} == {
        "design_area", "utilization",
    }
    metrics = {metric["name"]: metric for metric in result["metrics"]}
    assert metrics["design_area"]["value"] == 670.0
    assert metrics["utilization"]["unit"] == "%"
    structured = json.loads((tmp_path / "analysis_result.json").read_text())
    assert structured["records"][0]["evidence"][0]["line_start"] == 1
    script = (tmp_path / "openroad_report.tcl").read_text(encoding="utf-8")
    assert "report_design_area" in script


def test_openroad_power_json_report_is_structured_from_official_shape(tmp_path: Path) -> None:
    fake = tmp_path / "fake-openroad"
    fake.write_text("""#!/usr/bin/env python3
import json
from pathlib import Path
Path('reports').mkdir(exist_ok=True)
Path('reports/power.json').write_text(json.dumps({
    'Sequential': {'internal': 8.01e-6, 'switching': 4.99e-8,
                   'leakage': 1.45e-9, 'total': 8.06e-6},
    'Total': {'internal': 8.22e-6, 'switching': 1.03e-7,
              'leakage': 1.61e-9, 'total': 8.32e-6},
}))
""", encoding="utf-8")
    fake.chmod(0o755)
    (tmp_path / "design.odb").write_bytes(b"odb")
    result = _run_adapter(tmp_path, _task({
        "adapter": "report", "report": "power", "odb_path": "design.odb",
        "openroad_bin": str(fake),
    }))
    assert result["status"] == "succeeded"
    metrics = {metric["name"]: metric for metric in result["metrics"]}
    assert metrics["power_total"]["value"] == 8.32e-6
    assert metrics["power_total"]["unit"] == "W"
    structured = json.loads((tmp_path / "analysis_result.json").read_text())
    assert structured["record_count"] == 2
    assert structured["records"][1]["evidence"][0]["json_pointer"] == "/Total"
    assert "report_power -format json" in (
        tmp_path / "openroad_report.tcl").read_text(encoding="utf-8")


def test_openroad_report_rejects_congestion_without_a_supported_command(tmp_path: Path) -> None:
    fake = tmp_path / "fake-openroad"
    fake.write_text("""#!/usr/bin/env python3
from pathlib import Path
Path('reports').mkdir(exist_ok=True)
Path('reports/congestion.rpt').write_text('would be misleading\\n')
""", encoding="utf-8")
    fake.chmod(0o755)
    (tmp_path / "design.odb").write_bytes(b"odb")
    result = _run_adapter(tmp_path, _task({
        "adapter": "report", "report": "congestion", "odb_path": "design.odb",
        "openroad_bin": str(fake),
    }), expected_exit=2)
    assert result["status"] == "failed"
    assert result["failure"]["category"] == "configuration_error"


def test_openroad_report_keeps_script_and_inputs_when_tool_fails(tmp_path: Path) -> None:
    fake = tmp_path / "fake-openroad"
    fake.write_text("#!/usr/bin/env python3\nraise SystemExit(7)\n", encoding="utf-8")
    fake.chmod(0o755)
    (tmp_path / "design.odb").write_bytes(b"odb")
    result = _run_adapter(tmp_path, _task({
        "adapter": "report", "report": "area", "odb_path": "design.odb",
        "openroad_bin": str(fake),
    }), expected_exit=7)
    assert result["failure"]["category"] == "report_error"
    kinds = {item["kind"] for item in result["artifacts"]}
    assert {"extractor_log", "extractor_receipt", "analysis_script",
            "raw_design_database"} <= kinds
    assert "analysis_report" not in kinds


def test_openroad_report_rejects_success_without_report_output(tmp_path: Path) -> None:
    fake = tmp_path / "fake-openroad"
    fake.write_text("#!/usr/bin/env python3\npass\n", encoding="utf-8")
    fake.chmod(0o755)
    (tmp_path / "design.odb").write_bytes(b"odb")
    result = _run_adapter(tmp_path, _task({
        "adapter": "report", "report": "area", "odb_path": "design.odb",
        "openroad_bin": str(fake),
    }), expected_exit=1)
    assert result["status"] == "failed"
    assert result["failure"]["category"] == "report_output_missing"
    assert result["artifacts"][-1]["kind"] == "raw_design_database"


def test_openroad_timing_report_rejects_invalid_json_after_preserving_report(tmp_path: Path) -> None:
    fake = tmp_path / "fake-openroad"
    fake.write_text("""#!/usr/bin/env python3
from pathlib import Path
Path('reports').mkdir(exist_ok=True)
Path('reports/timing.json').write_text('not-json\\n')
""", encoding="utf-8")
    fake.chmod(0o755)
    (tmp_path / "design.odb").write_bytes(b"odb")
    result = _run_adapter(tmp_path, _task({
        "adapter": "report", "report": "timing", "odb_path": "design.odb",
        "openroad_bin": str(fake),
    }), expected_exit=1)
    assert result["failure"]["category"] == "report_parse_error"
    assert {item["kind"] for item in result["artifacts"]} >= {
        "analysis_report", "analysis_script", "raw_design_database",
    }


def test_multilib_directed_sta_and_boundary_validation(tmp_path: Path) -> None:
    _run_adapter(tmp_path, _task({'adapter': 'opensta', 'odb_path': 'design.odb',
        'openroad_bin': '/does/not/exist', 'liberty_paths': ['standard.lib', 'macro.lib'],
        'to_pin': 'core/register[7]/D', 'rc_script_path': 'rc.tcl',
        'parasitic_mode': 'placement'}), expected_exit=2)
    script = (tmp_path / 'opensta_extract.tcl').read_text()
    assert 'read_liberty "standard.lib"' in script and 'read_liberty "macro.lib"' in script
    assert script.index('read_liberty "macro.lib"') < script.index('source "rc.tcl"')
    assert 'estimate_parasitics -placement' in script and 'must resolve to one pin' in script
    for paths in (['../outside.lib'], ['a.lib', 'a.lib'], 'a.lib', [None]):
        result = _run_adapter(tmp_path, _task({'adapter': 'opensta', 'odb_path': 'design.odb',
            'liberty_paths': paths}), expected_exit=2)
        assert result['failure']['category'] == 'configuration_error'


def test_native_report_preserves_stdout_without_requiring_sta_redirect_file(tmp_path):
    fake = tmp_path / 'fake-openroad'
    fake.write_text('#!/usr/bin/env python3\nprint("SIGNAL_COUNT=58")\n')
    fake.chmod(0o755)
    (tmp_path / 'design.odb').write_bytes(b'odb')
    result = _run_adapter(tmp_path, _task({'adapter': 'report', 'report': 'native',
        'script': 'puts "SIGNAL_COUNT=58"', 'odb_path': 'design.odb', 'openroad_bin': str(fake)}))
    assert result['status'] == 'succeeded'
    assert (tmp_path / 'reports/native.rpt').read_text() == 'SIGNAL_COUNT=58\n'
    assert 'sta::redirect_file_begin' not in (tmp_path / 'openroad_report.tcl').read_text()
    report = next(a for a in result['artifacts'] if a['kind'] == 'analysis_report')
    assert report['metadata']['report'] == 'native'
