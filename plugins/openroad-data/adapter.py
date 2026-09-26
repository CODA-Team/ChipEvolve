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

from opendb_adapter import prepare as prepare_opendb
from opensta_adapter import normalize as normalize_opensta
from opensta_adapter import prepare as prepare_opensta
from orfs_adapter import convert as convert_orfs


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
            plan = prepare_opendb(inputs, workspace)
        elif mode == "opensta":
            plan = prepare_opensta(inputs, workspace)
        elif mode == "orfs":
            output_name = convert_orfs(inputs, workspace)
            _attach_source_artifacts(workspace / output_name, inputs)
            (workspace / "extractor.log").write_text(
                "converted structured ORFS metadata\n", encoding="utf-8")
            _write_receipt(workspace, {"adapter": mode, "output_directory": output_name,
                                       "started_at": started, "ended_at": now()})
            return _complete_result(result_path, started, workspace, output_name)
        elif mode == "command":
            command = inputs.get("extractor_command")
            if not isinstance(command, list) or not command or not all(
                    isinstance(item, str) and item for item in command):
                raise ValueError("inputs.extractor_command must be a non-empty string list")
            plan = {"command": command, "output_directory": inputs.get(
                "output_directory", "query-data")}
        else:
            raise ValueError("inputs.adapter must be command, opendb, opensta, or orfs")
        command = plan["command"]
        output_name = plan["output_directory"]
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
        completed = subprocess.run(command, cwd=workspace, env=environment,
                                   text=True, capture_output=True, check=False)
        output = completed.stdout + completed.stderr
        (workspace / "extractor.log").write_text(output, encoding="utf-8")
        receipt = {"command": command, "output_directory": output_name,
                   "returncode": completed.returncode, "started_at": started,
                   "ended_at": now()}
        (workspace / "extractor_receipt.json").write_text(
            json.dumps(receipt, indent=2), encoding="utf-8")
        if completed.returncode:
            progress("extract", "finished", status="failed")
            return _write_result(result_path, started, "failed", completed.returncode,
                                 _failure_artifacts(), {"category": "extractor_error",
                                      "message": f"extractor exited with status {completed.returncode}",
                                      "retryable": False})
        if mode == "opensta":
            normalize_opensta(output_dir, inputs)
        _attach_source_artifacts(output_dir, inputs)
        manifest = output_dir / "manifest.json"
        if not manifest.is_file():
            raise ValueError("extractor did not produce query-data/manifest.json")
        archive_path = workspace / "query-data.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source in sorted(item for item in output_dir.rglob("*") if item.is_file()):
                archive.write(source, source.relative_to(output_dir).as_posix())
        artifacts = _artifacts()
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
                  artifacts: list[dict[str, str]], failure: dict[str, Any] | None) -> int:
    payload: dict[str, Any] = {"schema_version": 3, "status": status,
                               "exit_code": exit_code, "started_at": started,
                               "ended_at": now(), "artifacts": artifacts}
    if failure is not None:
        payload["failure"] = failure
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return exit_code


def _write_receipt(workspace: Path, value: dict[str, Any]) -> None:
    (workspace / "extractor_receipt.json").write_text(
        json.dumps(value, indent=2), encoding="utf-8")


def _artifacts() -> list[dict[str, str]]:
    return [
        {"kind": "data_snapshot", "path": "query-data.zip"},
        {"kind": "extractor_log", "path": "extractor.log"},
        {"kind": "extractor_receipt", "path": "extractor_receipt.json"},
    ]


def _failure_artifacts() -> list[dict[str, str]]:
    return [
        {"kind": "extractor_log", "path": "extractor.log"},
        {"kind": "extractor_receipt", "path": "extractor_receipt.json"},
    ]


def _complete_result(result_path: Path, started: str, workspace: Path,
                     output_name: str) -> int:
    output_dir = workspace / output_name
    if not (output_dir / "manifest.json").is_file():
        raise ValueError("metadata adapter did not produce manifest.json")
    archive_path = workspace / "query-data.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(item for item in output_dir.rglob("*") if item.is_file()):
            archive.write(source, source.relative_to(output_dir).as_posix())
    return _write_result(result_path, started, "succeeded", 0, _artifacts(), None)


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
