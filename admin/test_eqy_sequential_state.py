"""State cuts come from actual common Liberty models, never routed wire names."""

import copy
from pathlib import Path

import pytest

from chip_evolve import eqy


def model():
    return {
        "modules": {
            "design": {
                "netnames": {},
                "cells": {
                    "register": {"type": "storage"},
                    "net9999": {"type": "buffer"},
                },
            },
            "storage": {
                "cells": {"ff": {"type": "$_DFF_P_", "connections": {"Q": [4]}}},
                "netnames": {
                    "IQ": {"bits": [4], "hide_name": 0},
                    "Q": {"bits": [4], "hide_name": 0},
                    "CLK": {"bits": [2], "hide_name": 0},
                },
            },
            "buffer": {
                "cells": {"buf": {"type": "$_BUF_"}},
                "netnames": {"IQ": {"bits": [4], "hide_name": 0}},
            },
        }
    }


def test_one_state_alias_per_actual_common_flop_not_buffer_or_clock():
    gold = model()
    assert eqy.common_flop_states(gold, copy.deepcopy(gold), "design") == {
        "register.IQ"
    }


@pytest.mark.parametrize("change", ["instance", "master", "model"])
def test_unrelated_instances_or_different_logic_are_not_state_correspondences(change):
    gold, gate = model(), model()
    if change == "instance":
        gate["modules"]["design"]["cells"]["different"] = gate["modules"]["design"][
            "cells"
        ].pop("register")
    elif change == "master":
        gate["modules"]["design"]["cells"]["register"]["type"] = "other"
    else:
        gate["modules"]["storage"]["cells"]["ff"]["type"] = "$_DFF_N_"
    assert eqy.common_flop_states(gold, gate, "design") == set()


def test_old_parse_without_liberty_definitions_does_not_invent_states():
    value = {"modules": {"design": model()["modules"]["design"]}}
    assert eqy.common_flop_states(value, value, "design") == set()


def test_extra_state_cuts_require_qualified_pdr_and_remain_asserted_matches():
    checks = [
        {"ports": {"y": {"direction": "output", "width": 2}}, "zero_port_types": []}
    ] * 2
    args = ("design", [Path("gold.v"), Path("gate.v")], [], checks, [set()] * 2)
    with pytest.raises(ValueError, match="PDR"):
        eqy.configuration(*args, state_points={"register.IQ"})
    text = eqy.configuration(
        *args,
        strategy="abc-pdr",
        state_points={"register.IQ", "other.IQ"},
    )
    state_rule = r"final-gold-match /(?:other\.IQ|register\.IQ)/"
    assert state_rule in text
    assert text.index(state_rule) < text.index(r"gold-nomatch /.*\..*/")
    assert "final-gold-match /y/" in text
    assert "use sby\nengine abc pdr" in text
    assert "gold-match *" not in text.splitlines()


def test_registered_proof_keeps_state_derivation_and_solver_evidence(
    tmp_path, monkeypatch
):
    from admin.test_eqy_pdr import prepared
    from admin.test_local_eqy import checks
    from chip_evolve.config import read, write

    jobs, reference, candidate, _, _, _, calls = prepared(tmp_path, monkeypatch)
    jobs.deployment.value["validation"]["equivalence_match_flops"] = True
    for side in ["gold", "gate"]:
        write(jobs.experiment / (side + ".json"), model())
    _, receipt = eqy.verify(jobs, reference, candidate, [], checks())
    evidence = jobs.experiment / "proof-state-matches.json"
    assert read(evidence) == {"count": 1, "points": ["register.IQ"]}
    assert evidence in calls[0]["capture"]
    assert jobs.experiment / "proof-solver.json" in calls[0]["capture"]
    assert receipt["proposed_state_points"] == 1
    assert receipt["proven_points"] == 8


@pytest.mark.parametrize("enabled", [False, True])
def test_state_discovery_imports_fixed_models_only_for_explicit_pdr_preparation(
    tmp_path, monkeypatch, enabled
):
    from admin.test_adoption_consistency import frame_at
    from admin.test_local_business import deployment
    from chip_evolve import logic
    from chip_evolve.jobs import Jobs, digest

    d = deployment(tmp_path)
    source = frame_at(tmp_path, "reference")
    library = tmp_path / "fixed.lib"
    library.write_text("fixed model for preparation-boundary test")
    d.value["designs"]["gcd"] = {
        "top": "test",
        "libraries": [{"path": str(library), "sha256": digest(library)}],
    }
    d.value["tools"] = {"yosys": "yosys", "equivalence": "eqy"}
    d.value["validation"] = {
        "equivalence_strategy": "abc-pdr",
        "equivalence_match_flops": enabled,
    }

    class Prepared(Exception):
        pass

    def submitted(self, key, command, **kwargs):
        text = (self.experiment / "gold.ys").read_text()
        assert (
            f'read_liberty -ignore_miss_func -ignore_miss_dir "{library}"' in text
        ) == enabled
        assert text.index("read_verilog") < text.index("write_json")
        raise Prepared

    monkeypatch.setattr(Jobs, "command", submitted)
    monkeypatch.setattr(logic, "container", lambda deployment, command: command)
    with pytest.raises(Prepared):
        logic.verify_outputs(d, source, source, tmp_path / "proof")
