"""Failed native work retains its actual raw evidence and original failure."""

import json
import subprocess
import sys
from pathlib import Path


def execute(tmp_path: Path, body: str):
    request = tmp_path / "request.json"
    result = tmp_path / "result.json"
    request.write_text(
        json.dumps(
            {
                "task": {
                    "inputs": {
                        "adapter": "command",
                        "extractor_command": [sys.executable, "-c", body],
                        "native_extra_paths": ["outputs/partial.v"],
                    }
                }
            }
        )
    )
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "eda_toolkits.openroad.adapter",
            "--request",
            str(request),
            "--result",
            str(result),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return process, json.loads(result.read_text())


def test_native_failure_retains_raw_logs_receipt_and_partial_outputs(tmp_path):
    process, result = execute(
        tmp_path,
        "from pathlib import Path;import json\n"
        'p=Path("query-data/3");p.mkdir(parents=True)\n'
        '(p/"evaluation.log").write_text("repair_power entered; original native timeout")\n'
        '(p/"checkpoint.odb").write_bytes(b"actual incomplete checkpoint")\n'
        'Path("query-data/manifest.json").write_text(json.dumps({"evidence_only":True,"returncode":143}))\n'
        'Path("outputs").mkdir();Path("outputs/partial.v").write_text("module partial;endmodule")\n'
        "raise SystemExit(143)\n",
    )
    assert process.returncode == result["exit_code"] == 143
    assert (
        result["status"] == "failed"
        and result["failure"]["category"] == "extractor_error"
    )
    artifacts = {row["path"]: row for row in result["artifacts"]}
    assert artifacts["query-data/3/evaluation.log"]["kind"] == "raw_flow_metadata"
    assert artifacts["query-data/3/checkpoint.odb"]["kind"] == "raw_design_database"
    assert artifacts["query-data/manifest.json"]["kind"] == "raw_flow_metadata"
    assert artifacts["outputs/partial.v"]["kind"] == "raw_netlist"
    assert all(
        artifacts[name]["metadata"]["incomplete_output"]
        for name in artifacts
        if name.startswith(("query-data/", "outputs/"))
    )
    assert not any(row["kind"] == "data_snapshot" for row in result["artifacts"])


def test_failure_without_outputs_keeps_original_minimal_artifacts(tmp_path):
    process, result = execute(tmp_path, "raise SystemExit(7)")
    assert process.returncode == result["exit_code"] == 7
    assert result["status"] == "failed"
    assert {row["kind"] for row in result["artifacts"]} == {
        "extractor_log",
        "extractor_receipt",
    }


def test_failed_outputs_cross_runtime_custody_without_becoming_design_snapshot(
    tmp_path,
):
    from openroad_platform_contracts import PluginManifest, RuntimeStatus, TaskSpec
    from openroad_platform_runtime import RuntimeStore, WorkflowRuntime
    from openroad_platform_runtime.adapter import ProcessAdapter
    from openroad_platform_runtime.guardian import ProcessGuardian

    manifest = PluginManifest(
        plugin_id="openroad-data",
        plugin_version="0.1.0",
        adapter_entry=(sys.executable, "-m", "eda_toolkits.openroad.adapter"),
        capabilities=("data.extract",),
        supported_arch=("x86_64",),
        artifact_rules=tuple(
            {
                "kind": name,
                "required": name
                in {"data_snapshot", "extractor_log", "extractor_receipt"},
            }
            for name in (
                "data_snapshot",
                "extractor_log",
                "extractor_receipt",
                "raw_flow_metadata",
            )
        ),
    )

    class Resolver:
        def resolve(self, plugin_id, **kwargs):
            assert plugin_id == manifest.plugin_id
            return manifest

    store = RuntimeStore(tmp_path / "fixture.sqlite")
    runtime = WorkflowRuntime(
        store,
        Resolver(),
        workspace_root=tmp_path / "workspaces",
        worker_id="failed-output-fixture",
        adapter=ProcessAdapter(
            ProcessGuardian(poll_interval=0.02, terminate_grace=1.0)
        ),
    )
    try:
        run = runtime.submit(
            TaskSpec(
                task_id="failed-command",
                project_id="fixture",
                design_id="design",
                plugin_id=manifest.plugin_id,
                inputs={
                    "adapter": "command",
                    "extractor_command": [
                        sys.executable,
                        "-c",
                        'from pathlib import Path;p=Path("query-data");p.mkdir();(p/"evaluation.log").write_text("actual failed native phase");raise SystemExit(7)',
                    ],
                },
                expected_artifacts=("data_snapshot",),
            )
        )
        finished = runtime.execute_once(run.run_id)
        assert finished.status is RuntimeStatus.FAILED
        attempt = runtime.describe(run.run_id)["stages"][0]["attempts"][0]
        assert attempt["failure"]["category"] == "extractor_error"
        assert "status 7" in attempt["failure"]["message"]
        assert not any(a["kind"] == "data_snapshot" for a in attempt["artifacts"])
        artifact = next(
            a for a in attempt["artifacts"] if a["kind"] == "raw_flow_metadata"
        )
        excerpt = runtime.read_artifact_excerpt(
            run.run_id, artifact["artifact_id"], offset=0, max_bytes=1024
        )
        assert excerpt["text"] == "actual failed native phase"
    finally:
        store.close()
