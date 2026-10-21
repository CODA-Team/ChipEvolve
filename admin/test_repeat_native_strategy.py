"""An optimization repeat preserves actual original inputs and relocates outputs."""

from pathlib import Path

import pytest

from admin.repeat_native_strategy import recorded_action, relocated_script
from chip_evolve.config import write
from chip_evolve.jobs import digest


def fixture(tmp_path):
    origin = tmp_path / "search"
    native = origin / "round/student/output"
    native.mkdir(parents=True)
    benchmark = origin / "input.def"
    benchmark.write_text("original design")
    script = native / "evaluate.tcl"
    script.write_text(
        f"read_def {{{benchmark}}}\nrepair_timing -setup\nwrite_db {{{native}/post_route.odb}}\n"
    )
    operation = origin / "operations/physical"
    write(
        operation / "execution.json",
        {"run": {"run_id": "producer", "status": "succeeded"}},
    )
    write(
        operation / "request.json",
        {
            "operation": "physical",
            "cwd": str(native),
            "command": ["openroad", "-exit", str(script)],
            "inputs": {str(benchmark): digest(benchmark)},
        },
    )
    candidate = origin / "candidates/student2"
    write(
        candidate / "result.json", {"native_method": {"origin_experiment": str(origin)}}
    )
    write(candidate / "delivery-checkpoint.json", {"producer": "producer"})
    return candidate / "result.json", benchmark, script


def test_candidate_repeat_uses_original_inputs_and_producer(tmp_path):
    result, benchmark, script = fixture(tmp_path)
    _, action, saved = recorded_action(result)
    relocated = relocated_script(
        script.read_text(), Path(action["cwd"]), tmp_path / "repeat/native"
    )
    assert f"read_def {{{benchmark}}}" in relocated
    assert f"write_db {{{tmp_path}/repeat/native/post_route.odb}}" in relocated
    assert "repair_timing -setup" in relocated
    assert saved["producer"] == "producer"


def test_changed_original_input_is_not_silently_repeated(tmp_path):
    result, benchmark, _ = fixture(tmp_path)
    benchmark.write_text("changed design")
    with pytest.raises(ValueError, match="input changed"):
        recorded_action(result)


def test_routing_only_job_is_not_an_optimization_repeat(tmp_path):
    result, _, script = fixture(tmp_path)
    script.write_text("detailed_route\n")
    with pytest.raises(ValueError, match="optimization Tcl"):
        recorded_action(result)
