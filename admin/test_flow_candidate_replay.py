"""Selected Flow candidates replay their actual placement and frozen recipe."""

import zipfile
from pathlib import Path

import pytest

from admin.test_local_business import deployment
from chip_evolve.config import read, write
from chip_evolve.jobs import digest
from chip_evolve.validation import replay


def candidate(tmp_path):
    d = deployment(tmp_path)
    folder = tmp_path / "selected"
    folder.mkdir()
    archive = folder / "flow.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(
            "flow/results/pdk/arbitrary/variant/3_place.odb", b"actual placement"
        )
        bundle.writestr(
            "flow/results/pdk/arbitrary/variant/3_place.sdc", b"tuned clock"
        )
        bundle.writestr(
            "flow/results/pdk/arbitrary/variant/6_final.odb", b"routed state"
        )
    for name in ("config.mk", "recipe.json", "objective.json"):
        (folder / name).write_text(name)
    result = folder / "result.json"
    write(
        result,
        {
            "design_id": "arbitrary",
            "candidate_id": "native-candidate",
            "physical_run_id": "actual-route-producer",
            "flow_archive": str(archive),
            "native_config": str(folder / "config.mk"),
            "native_flow_dir": str(folder / "source/flow"),
            "flow_recipe": str(folder / "recipe.json"),
            "objective": str(folder / "objective.json"),
        },
    )
    return d, result, tmp_path / "replay"


def test_flow_replay_uses_actual_placement_and_existing_delivery(tmp_path, monkeypatch):
    d, result, output = candidate(tmp_path)
    original = digest(result)
    seen = []

    def finish(deployment, experiment):
        saved = read(experiment / "delivery-checkpoint.json")
        seen.append(saved)
        assert saved["design_id"] == "arbitrary"
        assert Path(saved["odb"]).read_bytes() == b"actual placement"
        assert saved["source"] == str(result)
        assert read(saved["source"])["native_config"] == read(result)["native_config"]
        assert saved["producer"] == "actual-route-producer"
        assert saved["kind"] == "layout"
        return {"run_id": "independent-real-routing"}

    monkeypatch.setattr("chip_evolve.delivery.finish", finish)
    assert replay(d, result, output)["run_id"] == "independent-real-routing"
    assert replay(d, result, output)["run_id"] == "independent-real-routing"
    assert len(seen) == 2 and seen[0] == seen[1]
    assert digest(result) == original
    saved = read(output / "flow-replay-inputs.json")
    assert set(saved["input_hashes"]) == {
        str(result),
        read(result)["flow_archive"],
        read(result)["native_config"],
        read(result)["flow_recipe"],
        read(result)["objective"],
    }


@pytest.mark.parametrize("field", ["flow_archive", "native_config", "flow_recipe"])
def test_flow_resume_rejects_changed_recorded_inputs(tmp_path, monkeypatch, field):
    d, result, output = candidate(tmp_path)
    calls = []
    monkeypatch.setattr("chip_evolve.delivery.finish", lambda *a: calls.append(a) or {})
    replay(d, result, output)
    Path(read(result)[field]).write_bytes(b"changed after first replay")
    with pytest.raises(ValueError, match="Flow replay inputs changed"):
        replay(d, result, output)
    assert len(calls) == 1


def test_existing_code_checkpoint_keeps_precedence(tmp_path, monkeypatch):
    d, result, output = candidate(tmp_path)
    odb = result.parent / "code.odb"
    odb.write_bytes(b"code checkpoint")
    from chip_evolve.delivery import checkpoint

    checkpoint(
        result.parent,
        design_id="arbitrary",
        odb=odb,
        producer="actual-code-producer",
        objective=Path(read(result)["objective"]),
        source=result,
        native_method={"kind": "professional-code"},
    )
    monkeypatch.setattr(
        "chip_evolve.validation.finish",
        lambda *a: read(output / "delivery-checkpoint.json"),
    )
    value = replay(d, result, output)
    assert value["producer"] == "actual-code-producer"
    assert not (output / "flow-replay-inputs.json").exists()
