"""The native gate must reject proxy-only, illegal, and inconsistent metrics."""

import json
import subprocess
from pathlib import Path

import pytest
from accept_dplevolve_native import audit_candidate_source, audit_metrics
from run_dplevolve_native import digest, source_inventory


@pytest.fixture
def metrics_path(tmp_path: Path) -> Path:
    log = tmp_path / "dpl.log"
    log.write_text("[INFO DPL-0022] HPWL after 123.456 u\n")
    (tmp_path / "raw.json").write_text(
        json.dumps({"detailedplace__design__violations": 0})
    )
    (tmp_path / "post.json").write_text(
        json.dumps({"status": "ok", "check_command": "check_placement_evolve"})
    )
    path = tmp_path / "metrics.json"
    path.write_text(
        json.dumps(
            {
                "status": "ok",
                "legalize_exit_status": 0,
                "runtime_seconds": 1.2,
                "manifest": {
                    "line": "evolve_default",
                    "flow_variant": "test",
                    "input_stage": "3_4_place_resized",
                },
                "hpwl": {
                    "source": "openroad_dpl_log",
                    "log": str(log),
                    "after_micron": 123.456,
                },
                "legality": {"placement_violations": ""},
                "supporting_files": {
                    "raw_metrics_json": "raw.json",
                    "post_metrics_summary_json": "post.json",
                },
            }
        )
    )
    return path


@pytest.mark.parametrize(
    "change",
    [
        "proxy_only",
        "illegal",
        "missing_legality",
        "wrong_log",
        "wrong_scope",
        "raw_violation",
    ],
)
def test_rejects_invalid_measurements(metrics_path: Path, change: str) -> None:
    data = json.loads(metrics_path.read_text())
    if change == "proxy_only":
        data["hpwl_proxy"] = data.pop("hpwl")
    elif change == "illegal":
        data["legality"]["placement_violations"] = "7"
    elif change == "missing_legality":
        data["legality"] = {}
    elif change == "wrong_log":
        data["hpwl"]["after_micron"] = 1.0
    elif change == "wrong_scope":
        data["manifest"]["flow_variant"] = "another_run"
    else:
        (metrics_path.parent / "raw.json").write_text(
            json.dumps({"detailedplace__design__violations": 2})
        )
    metrics_path.write_text(json.dumps(data))
    assert not audit_metrics(metrics_path, "evolve_default", "test")["accepted"]


def test_accepts_measured_legal_result(metrics_path: Path) -> None:
    assert audit_metrics(metrics_path, "evolve_default", "test")["accepted"]


@pytest.fixture
def source_record(tmp_path: Path) -> dict:
    repo = tmp_path / "source"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    def git(*args: str) -> str:
        return subprocess.check_output(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                *args,
            ],
            cwd=repo,
            text=True,
        ).strip()

    source = repo / "algorithm.cpp"
    source.write_text("int gain() { return 0; }\n")
    git("add", "algorithm.cpp")
    git("commit", "-qm", "seed")
    base = git("rev-parse", "HEAD")
    source.write_text("int gain() { return 1; }\n")
    git("add", "algorithm.cpp")
    git("commit", "-qm", "candidate")
    git("branch", "candidate/test")
    record = {
        "source_repo": str(repo),
        "source_base_commit": base,
        "source_commit": git("rev-parse", "HEAD"),
        "candidate_ref": "candidate/test",
        "source_files": source_inventory(repo),
    }
    for name, content in (
        ("binary", b"fixture binary"),
        ("input_odb", b"fixture ODB"),
        ("input_sdc", b"fixture SDC"),
        ("metrics_path", b"fixture metrics"),
    ):
        path = tmp_path / name
        path.write_bytes(content)
        record[name] = str(path)
        hash_key = "metrics_sha256" if name == "metrics_path" else name + "_sha256"
        record[hash_key] = digest(path)
    return record


def test_source_and_measured_artifacts_are_pinned(source_record: dict) -> None:
    assert all(audit_candidate_source(source_record).values())


@pytest.mark.parametrize(
    "artifact", ["binary", "input_odb", "input_sdc", "metrics_path"]
)
def test_rejects_artifact_replacement(source_record: dict, artifact: str) -> None:
    Path(source_record[artifact]).write_bytes(b"another experiment")
    assert not all(audit_candidate_source(source_record).values())


def test_rejects_stale_candidate_reference(source_record: dict) -> None:
    subprocess.run(
        ["git", "branch", "-f", "candidate/test", source_record["source_base_commit"]],
        cwd=source_record["source_repo"],
        check=True,
    )
    assert not audit_candidate_source(source_record)["pinned_source"]
