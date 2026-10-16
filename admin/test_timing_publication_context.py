"""Common final STA facts keep their declared corner and native JSON units."""

import json

import pytest
from eda_toolkits.openroad.opensta_adapter import normalize

from admin.test_design_fact_materialization import publication
from chip_evolve.config import read, write
from chip_evolve.jobs import digest
from chip_evolve.physical import publish


@pytest.mark.parametrize("corner", ["FF", "SS"])
def test_final_timing_export_keeps_context_and_raw_seconds(
    tmp_path, monkeypatch, corner
):
    _, source, frame, jobs, kernel, _ = publication(tmp_path, monkeypatch)
    frame["conditions"] = {"corner": corner, "units": {"time": "ns"}}
    publish(jobs, frame, result_path=source, modes=("orfs", "opensta"))
    task = next(t for t in kernel.tasks if t["inputs"]["adapter"] == "opensta")
    inputs = task["inputs"]
    assert inputs["analysis"] == "post_route"
    assert inputs["corner"] == corner
    assert inputs["unit"] == "s", (
        "Native report_checks JSON uses SI, unlike metric/UI units"
    )
    output = tmp_path / "native-report"
    output.mkdir()
    for filename, kind, slack in [
        ("timing_report.json", "max", -2.014e-11),
        ("timing_report_hold.json", "min", 1.2e-11),
    ]:
        (output / filename).write_text(
            json.dumps(
                {
                    "checks": [
                        {
                            "path_type": kind,
                            "path_group": "reg2reg",
                            "startpoint": "a/Q",
                            "endpoint": "b/D",
                            "slack": slack,
                            "source_path": [],
                        }
                    ]
                }
            )
        )
    normalize(output, inputs)
    rows = [
        json.loads(s) for s in (output / "timing_paths.jsonl").read_text().splitlines()
    ]
    assert [r["slack"] for r in rows] == [-2.014e-11, 1.2e-11]
    assert {r["check"] for r in rows} == {"setup", "hold"}
    assert all(
        (r["analysis"], r["corner"], r["unit"]) == ("post_route", corner, "s")
        for r in rows
    )
    summary = json.loads((output / "summary.json").read_text())
    assert summary["timing_context"]["corner"] == corner
    assert summary["timing_context"]["analysis"] == "post_route"


def test_legacy_resume_preserves_saved_task_and_snapshot_identity(
    tmp_path, monkeypatch
):
    _, source, frame, jobs, kernel, _ = publication(tmp_path, monkeypatch)
    frame["conditions"] = {"corner": "FF"}
    first = publish(jobs, frame, result_path=source, modes=("orfs", "opensta"))
    task_path = next(
        p
        for p in (jobs.experiment / "jobs").glob("*/task.json")
        if read(p)["inputs"]["adapter"] == "opensta"
    )
    legacy = read(task_path)
    for field in ("analysis", "corner", "unit"):
        legacy["inputs"].pop(field)
    write(task_path, legacy)
    saved_sha = digest(task_path)
    kernel.tasks.clear()
    second = publish(jobs, frame, result_path=source, modes=("orfs", "opensta"))
    assert digest(task_path) == saved_sha
    assert first["snapshot_ids"] == second["snapshot_ids"]
    assert read(task_path) == legacy
    assert kernel.tasks == [], "Completed exports must reuse their saved submissions"
