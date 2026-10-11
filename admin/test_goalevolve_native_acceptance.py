"""Prevent mock, stale source and unchecked metrics from passing L3 gates."""

import hashlib
import json
from pathlib import Path

import pytest
from accept_goalevolve_native import audit_candidate, surface_inventory


@pytest.fixture
def evidence(tmp_path: Path) -> tuple[Path, Path, Path]:
    seed = tmp_path / "seed"
    source = tmp_path / "student/workspace/source"
    for root, code in ((seed, "int value = 1;\n"), (source, "int value = 2;\n")):
        (root / "src/rsz").mkdir(parents=True)
        (root / "src/rsz/Repair.cc").write_text(code)
    artifacts = tmp_path / "student/artifacts"
    output = artifacts / "contest_output"
    output.mkdir(parents=True)
    log = output / "evaluation.log"
    log.write_text(
        "GOALEVOLVE_CHECKPOINT_END post_route\n[INFO] Flow running time: 2\n"
    )
    official = output / "official_4of4.log"
    official.write_text("SUMMARY: 4/4 checks passed\n")
    metrics = output / "metrics.csv"
    metrics.write_text(
        "design,tns,total_power,leakage_power,slew_over_count,cap_over_count,fanout_over_count\n"
        "aes_cipher_top,-10,120,20,0,0,0\n"
    )
    for name in ("post_route.odb", "aes_cipher_top.def", "aes_cipher_top.v"):
        (output / name).write_text("fixture\n")
    binary = tmp_path / "student/workspace/build_goalevolve/bin/openroad"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"fixture binary")
    candidate = {
        "student_id": "student_1",
        "implementation_diff": "a/Repair.cc\nb/Repair.cc\n",
        "source_commit": surface_inventory(source)[1],
        "evaluation_error": None,
        "metrics": {"tns_abs_ns": 10, "dynamic_power_pw": 100, "leakage_power_pw": 20},
        "checks": [
            {"name": name, "passed": True}
            for name in ("build", "flow", "metrics", "placement", "lec")
        ],
        "artifacts": {
            "candidate_source": str(source),
            "evaluation_log": str(log),
            "official_4of4_log": str(official),
            "metrics_csv": str(metrics),
        },
    }
    path = artifacts / "candidate.json"
    path.write_text(json.dumps(candidate))
    return path, seed, source


def test_content_hash_uses_exact_source_bytes(
    evidence: tuple[Path, Path, Path],
) -> None:
    path, seed, source = evidence
    inventory, content_hash = surface_inventory(source)
    assert (
        content_hash == hashlib.sha256(b"src/rsz/Repair.ccint value = 2;\n").hexdigest()
    )
    assert len(inventory) == 1
    assert audit_candidate(path, seed)["passed"]
    (source / "src/rsz/Repair.cc").write_text("int value = 3;\n")
    assert not audit_candidate(path, seed)["checks"]["source_content_matches_candidate"]


@pytest.mark.parametrize(
    "mutation,failed_gate",
    [
        ("mock", "native_build_flow_metrics_placement_validity"),
        ("no_cpp", "real_cpp_change"),
        ("metrics", "metrics_match_csv"),
        ("validity", "official_four_checks"),
        ("drv", "zero_drvs"),
        ("binary", "private_binary"),
    ],
)
def test_rejects_incomplete_or_false_eda_evidence(
    evidence: tuple[Path, Path, Path],
    mutation: str,
    failed_gate: str,
) -> None:
    path, seed, source = evidence
    candidate = json.loads(path.read_text())
    if mutation == "mock":
        candidate["checks"] = [{"name": "mock", "passed": True}]
    elif mutation == "no_cpp":
        (source / "src/rsz/Repair.cc").write_bytes(
            (seed / "src/rsz/Repair.cc").read_bytes()
        )
        candidate["source_commit"] = surface_inventory(source)[1]
    elif mutation == "metrics":
        candidate["metrics"]["dynamic_power_pw"] = 10
    elif mutation == "validity":
        Path(candidate["artifacts"]["official_4of4_log"]).write_text(
            "SUMMARY: 3/4 checks passed\n"
        )
    elif mutation == "drv":
        csv = Path(candidate["artifacts"]["metrics_csv"])
        csv.write_text(csv.read_text().replace("120,20,0,0,0", "120,20,0,1,0"))
    else:
        (path.parent.parent / "workspace/build_goalevolve/bin/openroad").unlink()
    path.write_text(json.dumps(candidate))
    report = audit_candidate(path, seed)
    assert not report["passed"]
    assert not report["checks"][failed_gate]
