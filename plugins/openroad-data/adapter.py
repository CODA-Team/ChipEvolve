#!/usr/bin/env python3
"""Process bridge for native design-data extraction capabilities.

The native extractor is intentionally outside this repository. A deployment
supplies an OpenDB, timing, or flow script as a staged input and the bridge
records its command, environment, output snapshot, and failure evidence. The
kernel therefore manages the lifecycle while this plugin owns the external
algorithm boundary.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sta_inputs import library_paths

from opendb_adapter import prepare as prepare_opendb
from opensta_adapter import normalize as normalize_opensta
from opensta_adapter import prepare as prepare_opensta
from orfs_adapter import convert as convert_orfs
from report_adapter import declarations as report_declarations
from report_adapter import normalize as normalize_report
from report_adapter import prepare as prepare_report
from report_adapter import receipt as report_receipt


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def progress(stage: str, phase: str, **extra: Any) -> None:
    print("[progress] " + json.dumps({"stage": stage, "phase": phase, **extra}), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    result_path = Path(args.result)
    workspace = result_path.parent.resolve()
    started = now()
    try:
        request = json.loads(Path(args.request).read_text(encoding="utf-8"))
        task = request["task"]
        inputs = task.get("inputs", {})
        mode = inputs.get("adapter", "command")
        if mode == "opendb":
            plans = [prepare_opendb(inputs, workspace)]
        elif mode == "opensta":
            plans = [prepare_opensta(inputs, workspace)]
        elif mode == "openroad":
            plans = [prepare_opendb(inputs, workspace), prepare_opensta(inputs, workspace)]
        elif mode == "orfs":
            output_name = convert_orfs(inputs, workspace)
            _attach_source_artifacts(workspace / output_name, inputs)
            (workspace / "extractor.log").write_text(
                "converted structured ORFS metadata\n", encoding="utf-8")
            _write_receipt(workspace, {"adapter": mode, "output_directory": output_name,
                                       "started_at": started, "ended_at": now()})
            return _complete_result(result_path, started, workspace, output_name, inputs)
        elif mode == "report":
            return _run_report(result_path, started, workspace, inputs)
        elif mode == "command":
            command = inputs.get("extractor_command")
            if not isinstance(command, list) or not command or not all(
                    isinstance(item, str) and item for item in command):
                raise ValueError("inputs.extractor_command must be a non-empty string list")
            plans = [{"command": command, "output_directory": inputs.get(
                "output_directory", "query-data")}]
        else:
            raise ValueError("inputs.adapter must be command, opendb, openroad, opensta, orfs, or report")
        output_name = plans[0]["output_directory"]
        output_dir = (workspace / output_name).resolve()
        output_dir.relative_to(workspace)
        environment = os.environ.copy()
        supplied = inputs.get("environment", {})
        if not isinstance(supplied, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in supplied.items()):
            raise ValueError("inputs.environment must be a string mapping")
        environment.update(supplied)
        progress("extract", "started")
        output = ""
        completed = None
        for plan in plans:
            completed = subprocess.run(plan["command"], cwd=workspace, env=environment,
                                       text=True, capture_output=True, check=False)
            output += completed.stdout + completed.stderr
            if completed.returncode:
                break
        assert completed is not None
        (workspace / "extractor.log").write_text(output, encoding="utf-8")
        receipt = {"commands": [plan["command"] for plan in plans],
                   "output_directory": output_name, "returncode": completed.returncode,
                   "started_at": started, "ended_at": now()}
        (workspace / "extractor_receipt.json").write_text(
            json.dumps(receipt, indent=2), encoding="utf-8")
        if completed.returncode:
            progress("extract", "finished", status="failed")
            return _write_result(result_path, started, "failed", completed.returncode,
                                 _failure_artifacts(), {"category": "extractor_error",
                                      "message": f"extractor exited with status {completed.returncode}",
                                      "retryable": False})
        if mode in {"opensta", "openroad"}:
            normalize_opensta(output_dir, inputs)
        _attach_source_artifacts(output_dir, inputs)
        manifest = output_dir / "manifest.json"
        if not manifest.is_file():
            raise ValueError("extractor did not produce query-data/manifest.json")
        archive_path = workspace / "query-data.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source in sorted(item for item in output_dir.rglob("*") if item.is_file()):
                archive.write(source, source.relative_to(output_dir).as_posix())
        artifacts = _artifacts(inputs, workspace)
        progress("extract", "finished", status="succeeded")
        return _write_result(result_path, started, "succeeded", 0, artifacts, None)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        if not (workspace / "extractor.log").exists():
            (workspace / "extractor.log").write_text(str(exc) + "\n", encoding="utf-8")
        _write_receipt(workspace, {"status": "failed", "error": str(exc),
                                   "started_at": started, "ended_at": now()})
        return _write_result(result_path, started, "failed", 2, _failure_artifacts(), {
            "category": "configuration_error", "message": str(exc), "retryable": False,
        })


def _write_result(path: Path, started: str, status: str, exit_code: int,
                  artifacts: list[dict[str, Any]], failure: dict[str, Any] | None,
                  metrics: list[dict[str, Any]] | None = None) -> int:
    payload: dict[str, Any] = {"schema_version": 3, "status": status,
                               "exit_code": exit_code, "started_at": started,
                               "ended_at": now(), "artifacts": artifacts,
                               "metrics": metrics or []}
    if failure is not None:
        payload["failure"] = failure
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return exit_code


def _write_receipt(workspace: Path, value: dict[str, Any]) -> None:
    (workspace / "extractor_receipt.json").write_text(
        json.dumps(value, indent=2), encoding="utf-8")


_RAW_INPUTS = {
    "odb_path": "raw_design_database",
    "lef_path": "raw_technology",
    "def_path": "raw_layout",
    "netlist_path": "raw_netlist",
    "liberty_path": "raw_library",
    "sdc_path": "raw_constraints",
    "spef_path": "raw_parasitics",
    "global_routing_segments_path": "raw_layout",
    "rc_script_path": "analysis_script",
    "timing_report_path": "raw_timing_report",
    "metadata_path": "raw_flow_metadata",
    "producer_metadata_path": "raw_flow_metadata",
}


def _artifacts(inputs: dict[str, Any], workspace: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = [
        {"kind": "data_snapshot", "path": "query-data.zip"},
        {"kind": "extractor_log", "path": "extractor.log"},
        {"kind": "extractor_receipt", "path": "extractor_receipt.json"},
    ]
    occupied = {item["path"] for item in result}
    # Reports the plugin itself produced.  A fact's evidence names the file it came
    # from, so that file has to be registered: otherwise the reference resolves by
    # role to whichever report *is* registered, and the data foundation hands back
    # the wrong one - which is exactly why a hold path used to cite the setup report.
    output_directory = str(inputs.get("output_directory") or "query-data")
    for name, kind in (("timing_report_hold.json", "raw_timing_report"),
                       ("dbnetwork_map.json", "raw_dbnetwork_map"),
                       ("effective.sdc", "raw_constraints"),
                       ("check_setup.rpt", "analysis_report")):
        path = f"{output_directory}/{name}"
        if path in occupied or not (workspace / path).is_file():
            continue
        occupied.add(path)
        result.append({"kind": kind, "path": path,
                       "metadata": {"produced_by": "openroad-data"}})
    result.extend(_raw_input_declarations(inputs, workspace, occupied=occupied))
    return result


def _raw_input_declarations(inputs: dict[str, Any], workspace: Path,
                            *, occupied: set[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    sources = [(field, kind, inputs.get(field)) for field, kind in _RAW_INPUTS.items()
               if field != "liberty_path"]
    sources.extend(("liberty_paths", "raw_library", value) for value in library_paths(inputs))
    extra_paths = inputs.get('native_extra_paths', [])
    if not isinstance(extra_paths, list) or any(not isinstance(p, str) for p in extra_paths):
        raise ValueError('native_extra_paths must be a list of staged paths')
    kinds = {'.odb': 'raw_design_database', '.lib': 'raw_library', '.sdc': 'raw_constraints',
             '.spef': 'raw_parasitics', '.def': 'raw_layout', '.gds': 'raw_layout',
             '.lef': 'raw_technology', '.v': 'raw_netlist', '.tcl': 'analysis_script', '.rpt': 'analysis_report'}
    sources.extend(('native_extra_paths', kinds.get(Path(p).suffix, 'raw_flow_metadata'), p) for p in extra_paths)
    for field, kind, value in sources:
        if value is None:
            continue
        if not isinstance(value, str) or not value or value.startswith("/") \
                or ".." in Path(value).parts:
            raise ValueError(f"inputs.{field} must be a relative staged path")
        path = (workspace / value).resolve()
        path.relative_to(workspace)
        if not path.is_file() or value in occupied:
            continue
        occupied.add(value)
        result.append({"kind": kind, "path": value,
                       "metadata": {"source_field": field}})
    return result


def _run_report(result_path: Path, started: str, workspace: Path,
                inputs: dict[str, Any]) -> int:
    plan = prepare_report(inputs, workspace)
    environment = os.environ.copy()
    supplied = inputs.get("environment", {})
    if not isinstance(supplied, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in supplied.items()):
        raise ValueError("inputs.environment must be a string mapping")
    environment.update(supplied)
    progress("report", "started", report=plan["report"])
    completed = subprocess.run(plan["command"], cwd=workspace, env=environment,
                               text=True, capture_output=True, check=False)
    (workspace / "extractor.log").write_text(
        completed.stdout + completed.stderr, encoding="utf-8")
    if plan['report'] == 'native':
        (workspace / plan['report_path']).write_text(
            completed.stdout + completed.stderr, encoding='utf-8')
    _write_receipt(workspace, {
        **report_receipt(plan, returncode=completed.returncode),
        "started_at": started, "ended_at": now(),
    })
    declared = report_declarations(plan, workspace)
    artifacts = [
        {"kind": "extractor_log", "path": "extractor.log"},
        {"kind": "extractor_receipt", "path": "extractor_receipt.json"},
        *declared,
    ]
    artifacts.extend(_raw_input_declarations(
        inputs, workspace, occupied={item["path"] for item in artifacts}))
    if completed.returncode:
        progress("report", "finished", status="failed")
        return _write_result(result_path, started, "failed", completed.returncode,
                             artifacts, {
                                 "category": "report_error",
                                 "message": f"report command exited with status {completed.returncode}",
                                 "retryable": False,
                             })
    if not any(item["kind"] == "analysis_report" for item in declared):
        progress("report", "finished", status="failed")
        return _write_result(result_path, started, "failed", 1, artifacts, {
            "category": "report_output_missing",
            "message": "OpenROAD exited successfully but produced no report file",
            "retryable": False,
        })
    try:
        normalize_report(plan, workspace)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _write_receipt(workspace, {
            **report_receipt(plan, returncode=completed.returncode),
            "status": "failed", "parse_status": "failed", "parse_error": str(exc),
            "started_at": started, "ended_at": now(),
        })
        declared = report_declarations(plan, workspace)
        artifacts = [
            {"kind": "extractor_log", "path": "extractor.log"},
            {"kind": "extractor_receipt", "path": "extractor_receipt.json"},
            *declared,
        ]
        artifacts.extend(_raw_input_declarations(
            inputs, workspace, occupied={item["path"] for item in artifacts}))
        progress("report", "finished", status="failed")
        return _write_result(result_path, started, "failed", 1, artifacts, {
            "category": "report_parse_error", "message": str(exc),
            "retryable": False,
        })
    _write_receipt(workspace, {
        **report_receipt(plan, returncode=completed.returncode),
        "status": "succeeded", "parse_status": "parsed" if plan.get("result_path") else "raw_only",
        "result_path": plan.get("result_path"),
        "started_at": started, "ended_at": now(),
    })
    declared = report_declarations(plan, workspace)
    artifacts = [
        {"kind": "extractor_log", "path": "extractor.log"},
        {"kind": "extractor_receipt", "path": "extractor_receipt.json"},
        *declared,
    ]
    artifacts.extend(_raw_input_declarations(
        inputs, workspace, occupied={item["path"] for item in artifacts}))
    progress("report", "finished", status="succeeded")
    return _write_result(result_path, started, "succeeded", 0, artifacts, None,
                         plan.get("metrics"))


def _failure_artifacts() -> list[dict[str, str]]:
    return [
        {"kind": "extractor_log", "path": "extractor.log"},
        {"kind": "extractor_receipt", "path": "extractor_receipt.json"},
    ]


def _complete_result(result_path: Path, started: str, workspace: Path,
                     output_name: str, inputs: dict[str, Any]) -> int:
    output_dir = workspace / output_name
    if not (output_dir / "manifest.json").is_file():
        raise ValueError("metadata adapter did not produce manifest.json")
    archive_path = workspace / "query-data.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(item for item in output_dir.rglob("*") if item.is_file()):
            archive.write(source, source.relative_to(output_dir).as_posix())
    return _write_result(result_path, started, "succeeded", 0,
                         _artifacts(inputs, workspace), None)


def _attach_source_artifacts(output_dir: Path, inputs: dict[str, Any]) -> None:
    refs = inputs.get("source_artifacts", [])
    if not isinstance(refs, list):
        raise ValueError("inputs.source_artifacts must be a list")
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file() or not refs:
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("snapshot manifest must be an object")
    snapshot = manifest.get("snapshot", manifest)
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot manifest must contain an object")
    snapshot["source_artifacts"] = refs
    if "snapshot" in manifest:
        manifest["snapshot"] = snapshot
    else:
        manifest = snapshot
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
