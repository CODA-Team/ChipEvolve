"""The OpenROAD report capability crosses the real runtime boundary."""

from __future__ import annotations

import sys
from pathlib import Path

from openroad_platform_contracts import InputFile, PluginManifest, RuntimeStatus, TaskSpec
from openroad_platform_runtime import RuntimeStore, WorkflowRuntime
from openroad_platform_runtime.adapter import ProcessAdapter
from openroad_platform_runtime.guardian import ProcessGuardian

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "plugins" / "openroad-data" / "adapter.py"


class Resolver:
    def __init__(self, manifest: PluginManifest):
        self.manifest = manifest

    def resolve(self, plugin_id, *, version=None, capability=None, arch=None):
        assert plugin_id == self.manifest.plugin_id
        return self.manifest


def test_report_run_registers_report_script_and_input_artifact(tmp_path: Path) -> None:
    fake_openroad = tmp_path / "fake-openroad"
    fake_openroad.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "Path('reports').mkdir(exist_ok=True)\n"
        "Path('reports/timing.json').write_text('{\\\"checks\\\": "
        "[{\\\"slack\\\": -0.25}]}\\n')\n",
        encoding="utf-8",
    )
    fake_openroad.chmod(0o755)
    odb = tmp_path / "design.odb"
    odb.write_bytes(b"odb-bytes")
    manifest = PluginManifest(
        plugin_id="openroad-data", plugin_version="0.1.0",
        adapter_entry=(sys.executable, str(ADAPTER)),
        capabilities=("analysis.report",),
        supported_arch=("x86_64",),
        artifact_rules=(
            {"kind": "extractor_log", "required": True},
            {"kind": "extractor_receipt", "required": True},
            {"kind": "analysis_report"}, {"kind": "analysis_script"},
            {"kind": "analysis_result"},
            {"kind": "raw_design_database"},
        ),
    )
    store = RuntimeStore(tmp_path / "runtime.db")
    runtime = WorkflowRuntime(
        store, Resolver(manifest), workspace_root=tmp_path / "workspaces",
        worker_id="report-test",
        adapter=ProcessAdapter(ProcessGuardian(poll_interval=0.02, terminate_grace=1.0)),
    )
    try:
        run = runtime.submit(TaskSpec(
            task_id="report-runtime", project_id="p", design_id="chip",
            plugin_id="openroad-data", inputs={
                "adapter": "report", "report": "timing", "odb_path": "design.odb",
                "openroad_bin": str(fake_openroad),
            }, expected_artifacts=("analysis_report", "analysis_script"),
            staged_inputs=(InputFile(source=str(odb), destination="design.odb"),),
        ))
        finished = runtime.execute_once(run.run_id)
        assert finished.status is RuntimeStatus.SUCCEEDED
        attempt = runtime.describe(run.run_id)["stages"][0]["attempts"][0]
        kinds = {item["kind"] for item in attempt["artifacts"]}
        assert {"analysis_report", "analysis_script", "analysis_result",
                "raw_design_database", "extractor_log", "extractor_receipt"} <= kinds
        report = next(item for item in attempt["artifacts"]
                      if item["kind"] == "analysis_report")
        excerpt = runtime.read_artifact_excerpt(
            run.run_id, report["artifact_id"], offset=0, max_bytes=1024)
        assert '"slack": -0.25' in excerpt["text"]
        metrics = {item["name"]: item for item in attempt["metrics"]}
        assert metrics["worst_slack"]["value"] == -0.25
        assert metrics["worst_slack"]["source_artifact_id"] == report["artifact_id"]
    finally:
        store.close()
