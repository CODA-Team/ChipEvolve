"""Independent replay retains the completed routing boundary of its input."""

from pathlib import Path
from typing import Any

import pytest

from admin.test_local_business import deployment
from chip_evolve import physical, validation
from chip_evolve.config import read, write
from chip_evolve.delivery import checkpoint
from chip_evolve.jobs import Jobs, digest


@pytest.mark.parametrize(
    "stage,drc,preserve",
    [("detailed_route", 0, True), ("detailed_route", 54, False), (None, None, False)],
)
@pytest.mark.parametrize("platform", ["asap7", "nangate45"])
def test_replay_uses_the_original_routed_boundary(
    tmp_path, monkeypatch, stage, drc, preserve, platform
):
    d = deployment(tmp_path)
    d.value.update(
        runtime={"executable": "runtime", "image": "image", "bind_roots": []},
        tools={"openroad": "openroad"},
    )
    sdc = tmp_path / "design.sdc"
    sdc.write_text("original constraints")
    d.value["designs"]["gcd"] = {"platform": platform, "libraries": [], "sdc": str(sdc)}
    objective = tmp_path / "goal.json"
    write(
        objective,
        {
            "design_id": "gcd",
            "conditions": {
                "libraries": [],
                "sdc": {"path": str(sdc), "sha256": digest(sdc)},
            },
        },
    )
    original = d.experiment("gcd", "original")
    odb = original / "native.odb"
    odb.write_bytes(b"original routed geometry")
    pdk = original / platform
    pdk.mkdir()
    for name in ["setRC.tcl", "rcx_patterns.rules"]:
        (pdk / name).write_text("original RC model")
    method: dict[str, Any] = {"kind": "native-ECO" if stage else "native-search"}
    if stage:
        method.update(
            physical_stage=stage,
            route_drc=drc,
            route_drc_evidence={"artifact_id": "original-native-counter"},
        )
    checkpoint(
        original,
        design_id="gcd",
        odb=odb,
        producer="original-producer",
        objective=objective,
        pdk=pdk,
        native_method=method,
    )
    result = original / "result.json"
    write(result, {"design_id": "gcd", "native_method": method})
    frozen = {
        str(p): digest(p) for p in [odb, result, original / "delivery-checkpoint.json"]
    }
    replay = d.experiment("gcd", "replay")
    calls = []

    def command(self, key, argv, **options):
        script = (replay / "qualification/route.tcl").read_text()
        assert options["parent"] == "original-producer"
        for action in ["dbWire_destroy", "global_route", "detailed_route -"]:
            assert (action in script) is not preserve
        assert ("check_drc -output_file" in script) is preserve
        assert "extract_parasitics" in script
        assert (replay / "inputs/checkpoint.odb").read_bytes() == odb.read_bytes()
        write(replay / "qualification/native-metrics.json", {"route__drc_errors": 17})
        calls.append(key)
        return {"run": {"run_id": "independent-extraction"}}

    monkeypatch.setattr(Jobs, "command", command)
    monkeypatch.setattr(physical, "measure", lambda *a: {"run_id": "measured"})
    monkeypatch.setattr(physical, "publish", lambda _jobs, frame, **kw: frame)
    monkeypatch.setattr("chip_evolve.code_evidence.maybe_collect", lambda *a: None)
    frame = validation.replay(d, result, replay)
    assert calls == ["qualification"]
    assert frame["native_method"]["kind"] == "independent-routing-replay"
    assert frame["native_method"]["original_result"] == str(result)
    assert frame["route_drc"] == (0 if preserve else 17)
    if stage:
        for name in ["physical_stage", "route_drc", "route_drc_evidence"]:
            assert frame["native_method"][name] == method[name]
    assert all(digest(Path(p)) == sha for p, sha in frozen.items())
    assert read(replay / "delivery-checkpoint.json")["producer"] == "original-producer"
