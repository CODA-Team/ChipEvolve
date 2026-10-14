import hashlib
import zipfile

import pytest
from resume_placement import placement_archive, verify_stage_archive


def test_stale_successors_are_removed_and_dpl_is_the_frozen_predecessor(tmp_path):
    original = tmp_path / "flow.zip"
    with zipfile.ZipFile(original, "w") as archive:
        archive.writestr("flow/results/3_5_place_dp.odb", b"old placement")
        archive.writestr("flow/results/3_place.odb", b"old placement")
        archive.writestr("flow/results/3_place.sdc", "old period")
        archive.writestr("flow/results/4_cts.odb", b"stale clocks")
        archive.writestr("flow/logs/6_report.json", "stale metrics")
        archive.writestr("flow/objects/copyright.txt", "native metadata")
    odb = tmp_path / "candidate.odb"
    odb.write_bytes(b"DPL result")
    sdc = tmp_path / "common.sdc"
    sdc.write_text("set_cmd_units -time ps\ncreate_clock -period 310\n")
    output = tmp_path / "checkpoint.zip"
    placement_archive(original, odb, output, sdc)
    with zipfile.ZipFile(output) as archive:
        assert archive.read("flow/results/3_place.odb") == b"DPL result"
        assert archive.read("flow/results/3_5_place_dp.odb") == b"DPL result"
        assert archive.read("flow/results/3_place.sdc") == sdc.read_bytes()
        assert "flow/results/4_cts.odb" not in archive.namelist()
        assert "flow/logs/6_report.json" not in archive.namelist()
        assert archive.read("flow/objects/copyright.txt") == b"native metadata"


@pytest.mark.parametrize("failure", [None, "overwrite", "rebuild", "wrong-consumer"])
def test_stage_success_requires_preservation_and_actual_consumption(tmp_path, failure):
    output = tmp_path / "result.zip"
    candidate = b"candidate"
    log = (
        "read_db /attempt/flow/results/3_place.odb\nRunning detailed_placement in CTS\n"
    )
    if failure == "rebuild":
        log += "Running detail_place.tcl, stage 3_5_place_dp\n"
    if failure == "wrong-consumer":
        log = "read_db /attempt/flow/results/unrelated.odb\n"
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("flow/results/3_5_place_dp.odb", candidate)
        archive.writestr(
            "flow/results/3_place.odb",
            b"old baseline" if failure == "overwrite" else candidate,
        )
        archive.writestr("flow/combined.log", log)
    sha = hashlib.sha256(candidate).hexdigest()
    if failure:
        with pytest.raises(ValueError):
            verify_stage_archive(output, sha, "cts")
    else:
        assert "3_place.odb" in verify_stage_archive(output, sha, "cts")[0]
