from pathlib import Path

import pytest

from admin.verify_long_task_reliability import (
    linked_binary,
    preserve_incumbents,
    require_idle,
    verify_source,
)
from chip_evolve.config import read, write
from chip_evolve.jobs import digest


@pytest.mark.parametrize(
    "queued,running,attempts", [([1], [], []), ([], [1], []), ([], [], ["a"])]
)
def test_active_execution_service_cannot_be_replaced(queued, running, attempts):
    with pytest.raises(RuntimeError, match="active consumers"):
        require_idle({"workers": [{"active_attempt_ids": attempts}]}, queued, running)


def test_saved_candidate_identity_refuses_a_later_source_revision(tmp_path: Path):
    source = tmp_path / "policy.cc"
    source.write_text("original mechanism")
    files = {source.name: digest(source)}
    verify_source(tmp_path, files)
    source.write_text("later candidate")
    with pytest.raises(ValueError, match="Saved source changed"):
        verify_source(tmp_path, files)
    with pytest.raises(ValueError, match="nonempty"):
        verify_source(tmp_path, {})


def test_private_replay_uses_the_original_cmake_output_directory(tmp_path):
    build = tmp_path / "original"
    build.mkdir()
    link = build / "link.txt"
    link.write_text('c++ input.o -o "../bin/openroad"')
    request = {
        "command": ["cmake", "-E", "cmake_link_script", str(link)],
        "cwd": str(build / "src"),
        "build": str(build),
    }
    assert (
        linked_binary(request, tmp_path / "private")
        == tmp_path / "private/bin/openroad"
    )


def test_new_business_state_retains_the_correct_design_incumbent(tmp_path):
    frame = tmp_path / "result.json"
    write(frame, {"design_id": "d", "objective_id": "o"})
    pointer = {"result": str(frame), "objective_id": "o", "run_id": "r"}
    write(tmp_path / "old/designs/d/incumbent.json", pointer)
    previous = {"state_root": str(tmp_path / "old"), "designs": {"d": {}}}
    preserve_incumbents(previous, tmp_path / "new")
    assert read(tmp_path / "new/designs/d/incumbent.json") == pointer
    write(frame, {"design_id": "another", "objective_id": "o"})
    with pytest.raises(ValueError, match="another design"):
        preserve_incumbents(previous, tmp_path / "bad")
