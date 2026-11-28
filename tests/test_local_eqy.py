"""Complete partition proof and declared design state are required for acceptance."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from chip_evolve.eqy import configuration, proof_receipt
from chip_evolve.jobs import Jobs


def checks():
    ports = {
        "out": {"direction": "output", "width": 8},
        "clk": {"direction": "input", "width": 1},
    }
    return [{"ports": ports, "zero_port_types": ["TAPCELL_ZERO"]}] * 2


def test_netlist_hierarchical_state_and_all_ports_survive_alias_filter():
    result = configuration(
        "design",
        [Path("gold.v"), Path("gate.v")],
        [Path("actual-ff.lib")],
        checks(),
        [{"keygen.state", "old_only"}, {"keygen.state", "gate_only"}],
    )
    filter_at = result.index(r"gold-nomatch /.*\..*/")
    for name in ("clk", "out", r"keygen\.state"):
        assert result.index(f"final-gold-match /{name}/") < filter_at
    assert "old_only" not in result and "gate_only" not in result
    assert (
        result.count('read_liberty -ignore_miss_func -ignore_miss_dir "actual-ff.lib"')
        == 2
    )
    assert result.count("delete t:TAPCELL_ZERO") == 2
    assert "use sat\ndepth 10" in result


def test_generated_route_names_are_not_implicit_correspondence_points():
    result = configuration(
        "design",
        [Path("gold.v"), Path("gate.v")],
        [],
        checks(),
        [{"net9999", "clknet_leaf_9_clk", "block.state"}] * 2,
    )
    assert "gold-match *" not in result.splitlines()
    assert "final-gold-match /net9999/" not in result
    assert "final-gold-match /clknet_leaf_9_clk/" not in result
    assert r"final-gold-match /block\.state/" in result
    assert "final-gold-match /out/" in result


def test_actual_top_port_is_preserved_even_with_a_generated_looking_name():
    frames = checks()
    frames = [
        {**c, "ports": {**c["ports"], "net9999": {"direction": "output", "width": 1}}}
        for c in frames
    ]
    result = configuration(
        "design", [Path("gold.v"), Path("gate.v")], [], frames, [{"net9999"}] * 2
    )
    assert "final-gold-match /net9999/" in result


def test_no_pass_marker_is_not_a_completed_proof(tmp_path):
    with pytest.raises(ValueError, match="complete design"):
        proof_receipt(tmp_path, checks())


def test_global_success_cannot_hide_an_unproven_partition(tmp_path):
    (tmp_path / "PASS").write_text("native success")
    (tmp_path / "partition.list").write_text("design design.out : out[7:0]\n")
    status = tmp_path / "strategies/design.out/simple/status"
    status.parent.mkdir(parents=True)
    status.write_text("UNKNOWN\n")
    with pytest.raises(ValueError, match="partition remains unproven"):
        proof_receipt(tmp_path, checks())
    status.write_text("PASS\n")
    assert proof_receipt(tmp_path, checks()) == {
        "engine": "eqy",
        "proven_points": 8,
        "proven_partitions": 1,
    }
    (tmp_path / "FAIL").write_text("failed control")
    with pytest.raises(ValueError, match="complete design"):
        proof_receipt(tmp_path, checks())


def test_empty_partition_listing_is_not_proof(tmp_path):
    (tmp_path / "PASS").touch()
    (tmp_path / "partition.list").write_text("")
    with pytest.raises(ValueError, match="no proof partitions"):
        proof_receipt(tmp_path, checks())


@pytest.mark.parametrize("engine", ["eqy", "yosys"])
@pytest.mark.parametrize("seconds", [None, 14400])
def test_proof_submission_uses_explicit_validation_budget_without_changing_strategy(
    tmp_path, monkeypatch, engine, seconds
):
    from chip_evolve import eqy, logic
    from chip_evolve.config import write

    class Submitted(Exception):
        pass

    calls = []

    def command(key, argv, **kwargs):
        calls.append({"key": key, "argv": argv, **kwargs})
        raise Submitted

    value: dict[str, Any] = {"tools": {"yosys": "/yosys", "eqy": "/eqy"}}
    if engine == "eqy":
        from chip_evolve.jobs import digest

        solver = tmp_path / "z3"
        solver.write_bytes(b"fixed solver fixture")
        manifest = tmp_path / "solver.json"
        write(
            manifest,
            {
                "name": "z3",
                "image_sha256": "image",
                "binary": {"path": str(solver), "sha256": digest(solver)},
                "library": {"path": str(solver), "sha256": digest(solver)},
            },
        )
        value["toolchain"] = {"image_sha256": "image"}
        value["validation"] = {
            "equivalence_strategy": "abc-pdr",
            "equivalence_solver_manifest": str(manifest),
        }
    if seconds is not None:
        value.setdefault("validation", {}).update(
            equivalence_seconds=seconds,
            equivalence_memory_gib=64,
            equivalence_jobs=1,
        )
    deployment = SimpleNamespace(
        value=value, design=lambda design_id: {"top": "design"}
    )
    jobs = cast(
        Jobs,
        SimpleNamespace(deployment=deployment, experiment=tmp_path, command=command),
    )
    monkeypatch.setattr(eqy, "container", lambda deployment, argv: argv)
    monkeypatch.setattr(logic, "container", lambda deployment, argv: argv)
    for side in ["gold", "gate"]:
        write(tmp_path / (side + ".json"), {"modules": {"design": {"netnames": {}}}})
    reference = {"files": {"v": "gold.v"}}
    candidate = {
        "files": {"v": "gate.v"},
        "design_id": "design",
        "run_id": "run-candidate",
        "objective": "objective.json",
    }
    with pytest.raises(Submitted):
        if engine == "eqy":
            eqy.verify(jobs, reference, candidate, [Path("actual.lib")], checks())
        else:
            logic._yosys_proof(
                jobs,
                candidate,
                reference,
                tmp_path / "proof.ys",
                tmp_path / "models.json",
            )
    assert calls[0]["seconds"] == (3600 if seconds is None else seconds)
    assert calls[0]["cpu"] == 4
    assert calls[0]["memory_gib"] == (32 if seconds is None else 64)
    assert calls[0]["parent"] == "run-candidate"
    assert calls[0]["objective"] == Path("objective.json")
    if engine == "eqy":
        import ast

        launcher = (tmp_path / "launch-proof.py").read_text()
        argv = ast.literal_eval(launcher.split("command=", 1)[1].splitlines()[0])
        assert argv[argv.index("-j") + 1] == ("2" if seconds is None else "1")
        text = (tmp_path / "proof.eqy").read_text()
        assert "use sby\nengine abc pdr\ndepth 10" in text
        assert "final-gold-match /out/" in text
