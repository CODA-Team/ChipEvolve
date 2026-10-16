"""Native PDR keeps the complete model, coverage and registered tool identity."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from admin.test_local_eqy import checks
from chip_evolve import eqy
from chip_evolve.config import read, write
from chip_evolve.jobs import Jobs, digest


def test_pdr_keeps_identical_model_and_match_policy_to_default_sat():
    args = (
        "design",
        [Path("gold.v"), Path("gate.v")],
        [Path("fixed.lib")],
        checks(),
        [{"block.state"}, {"block.state"}],
    )
    original = eqy.configuration(*args)
    pdr = eqy.configuration(*args, strategy="abc-pdr")
    assert original.split("[strategy")[0] == pdr.split("[strategy")[0]
    assert "use sat\ndepth 10" in original
    assert "use sby\nengine abc pdr\ndepth 10\nxprop on\noption aigsmt z3" in pdr


def test_unknown_strategy_is_rejected():
    with pytest.raises(ValueError, match="strategy"):
        eqy.configuration("design", [], [], [], [], strategy="unknown")


def prepared(tmp_path: Path, monkeypatch):
    binary, library = tmp_path / "solver/bin/z3", tmp_path / "solver/lib/libz3.so"
    binary.parent.mkdir(parents=True)
    library.parent.mkdir(parents=True)
    binary.write_bytes(b"verified solver binary")
    library.write_bytes(b"verified solver library")
    manifest = tmp_path / "solver.json"
    write(
        manifest,
        {
            "name": "z3",
            "image_sha256": "actual-image",
            "binary": {"path": str(binary), "sha256": digest(binary)},
            "library": {"path": str(library), "sha256": digest(library)},
            "version": "pinned native version",
        },
    )
    folder = tmp_path / "proof"
    folder.mkdir()
    for side in ("gold", "gate"):
        write(folder / (side + ".json"), {"modules": {"design": {"netnames": {}}}})
    deployment = SimpleNamespace(
        value={
            "tools": {"yosys": "/native/bin/yosys", "eqy": "/native/bin/eqy"},
            "toolchain": {"image_sha256": "actual-image"},
            "validation": {
                "equivalence_strategy": "abc-pdr",
                "equivalence_solver_manifest": str(manifest),
                "equivalence_memory_gib": 32,
                "equivalence_jobs": 1,
            },
        },
        design=lambda design_id: {"top": "design"},
    )
    calls = []

    def command(key, argv, **kwargs):
        calls.append({"key": key, "argv": argv, **kwargs})
        work = folder / "eqy-work"
        (work / "strategies/design.out/pdr").mkdir(parents=True)
        (work / "strategies/design.out/pdr/status").write_text("PASS\n")
        (work / "partition.list").write_text("design design.out : out[7:0]\n")
        (work / "PASS").touch()
        return {"run": {"run_id": "registered-proof"}}

    jobs = cast(
        Jobs,
        SimpleNamespace(
            deployment=deployment,
            experiment=folder,
            command=command,
            log=lambda record, path: path.write_text("native proof log"),
        ),
    )
    monkeypatch.setattr(eqy, "container", lambda deployment, argv: argv)
    reference = {"files": {"v": "gold.v"}}
    candidate = {
        "files": {"v": "gate.v"},
        "design_id": "design",
        "run_id": "actual-candidate",
        "objective": "objective.json",
    }
    return jobs, reference, candidate, manifest, binary, library, calls


def test_pdr_submission_binds_solver_and_preserves_all_output_acceptance(
    tmp_path, monkeypatch
):
    jobs, reference, candidate, manifest, _, _, calls = prepared(tmp_path, monkeypatch)
    record, result = eqy.verify(
        jobs, reference, candidate, [Path("fixed.lib")], checks()
    )
    assert record["run"]["run_id"] == "registered-proof"
    assert result["proven_points"] == 8 and result["proven_partitions"] == 1
    assert result["strategy"] == "abc-pdr" and result["solver"] == read(manifest)
    call = calls[0]
    launcher = jobs.experiment / "launch-proof.py"
    assert call["argv"] == ["python3", str(launcher)]
    assert call["parent"] == "actual-candidate" and call["memory_gib"] == 32
    assert (
        launcher in call["capture"]
        and jobs.experiment / "proof-solver.json" in call["capture"]
    )
    text = launcher.read_text()
    assert str(tmp_path / "solver/bin") in text and "os.execv" in text
    assert "--abc" in text and "/native/bin/yosys-abc" in text
    assert read(jobs.experiment / "proof-solver.json") == read(manifest)


@pytest.mark.parametrize("changed", ["binary", "library", "image"])
def test_changed_solver_or_tool_image_fails_before_ef_submission(
    tmp_path, monkeypatch, changed
):
    jobs, reference, candidate, manifest, binary, library, calls = prepared(
        tmp_path, monkeypatch
    )
    if changed == "image":
        value = read(manifest)
        value["image_sha256"] = "another-image"
        write(manifest, value)
    else:
        (binary if changed == "binary" else library).write_bytes(b"changed")
    with pytest.raises(ValueError, match="solver"):
        eqy.verify(jobs, reference, candidate, [], checks())
    assert not calls


def test_pdr_global_marker_cannot_hide_a_missing_partition(tmp_path, monkeypatch):
    jobs, reference, candidate, _, _, _, calls = prepared(tmp_path, monkeypatch)
    original: Any = jobs.command

    def incomplete(*args, **kwargs):
        result = original(*args, **kwargs)
        (jobs.experiment / "eqy-work/partition.list").write_text(
            "design design.out : out[7:0]\ndesign design.state : state\n"
        )
        return result

    monkeypatch.setattr(jobs, "command", incomplete)
    with pytest.raises(ValueError, match="partition remains unproven"):
        eqy.verify(jobs, reference, candidate, [], checks())
    assert len(calls) == 1


def test_pdr_cannot_fall_back_to_an_unconfigured_solver(tmp_path, monkeypatch):
    jobs, reference, candidate, _, _, _, calls = prepared(tmp_path, monkeypatch)
    del jobs.deployment.value["validation"]["equivalence_solver_manifest"]
    with pytest.raises(ValueError, match="solver manifest"):
        eqy.verify(jobs, reference, candidate, [], checks())
    assert not calls


def test_legacy_sat_cannot_issue_a_new_certificate_after_failed_negative_control(
    tmp_path, monkeypatch
):
    jobs, reference, candidate, _, _, _, calls = prepared(tmp_path, monkeypatch)
    jobs.deployment.value["validation"]["equivalence_strategy"] = "sat"
    with pytest.raises(ValueError, match="negative control"):
        eqy.verify(jobs, reference, candidate, [], checks())
    assert not calls
