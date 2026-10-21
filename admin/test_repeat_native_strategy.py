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


def test_repetition_binds_actual_input_parent_and_separates_code_source(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    import admin.repeat_native_strategy as module
    from chip_evolve.config import read

    result, benchmark, _ = fixture(tmp_path)
    origin = result.parents[2]
    write(
        origin / "input-receipt.json",
        {
            "source": str(benchmark),
            "source_run_id": "actual-input",
            "context": "original-context",
        },
    )
    binary = tmp_path / "openroad"
    binary.write_text("fixed native binary")
    request = origin / "operations/physical/request.json"
    action = read(request)
    action["command"][0] = str(binary)
    write(request, action)
    frame = read(result)
    frame.update(
        design_id="gcd",
        conditions={"toolchain": "fixed"},
        objective="/objective.json",
        condition_id="condition",
        objective_id="goal",
    )
    write(result, frame)
    output = tmp_path / "repeat"
    output.mkdir()

    class Dispatched(Exception):
        pass

    class Jobs:
        def __init__(self, *args):
            pass

        def command(self, *args, **kwargs):
            assert kwargs["parent"] == "actual-input"
            assert read(output / "input-receipt.json")["source"] == str(benchmark)
            assert read(output / "request.json")["code_source"] == str(result.resolve())
            assert read(output / "request.json")["source"] == str(benchmark)
            raise Dispatched()

    monkeypatch.setattr(module, "Jobs", Jobs)
    monkeypatch.setattr(module, "container", lambda d, command: command)
    deployment = SimpleNamespace(
        value={"toolchain": "fixed"}, experiment=lambda *args: output
    )
    with pytest.raises(Dispatched):
        module.repeat(deployment, result, "trial2")


def test_fact_delivery_interruption_preserves_completed_optimization(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    import admin.repeat_native_strategy as module
    from chip_evolve.config import read
    from chip_evolve.lifecycle import WorkPending

    result, benchmark, _ = fixture(tmp_path)
    origin = result.parents[2]
    write(
        origin / "input-receipt.json",
        {"source": str(benchmark), "source_run_id": "original-input"},
    )
    binary = tmp_path / "openroad"
    binary.write_text("original binary")
    operation = origin / "operations/physical/request.json"
    action = read(operation)
    action["command"][0] = str(binary)
    write(operation, action)
    objective = tmp_path / "objective.json"
    write(objective, {})
    pdk = tmp_path / "pdk"
    pdk.mkdir()
    (pdk / "setRC.tcl").write_text("original RC")
    (pdk / "rcx_patterns.rules").write_text("original extraction rules")
    write(
        result.parent / "delivery-checkpoint.json",
        {"producer": "producer", "pdk": str(pdk)},
    )
    frame = read(result)
    frame.update(
        design_id="gcd",
        conditions={"toolchain": "fixed"},
        objective=str(objective),
        condition_id="condition",
        objective_id="goal",
    )
    write(result, frame)
    output = tmp_path / "repeat"
    output.mkdir()
    dispatched = []

    class Jobs:
        def __init__(self, *args):
            pass

        def command(self, *args, **kwargs):
            dispatched.append("unique-optimization")
            (output / "native/post_route.odb").write_text("completed optimized ODB")
            return {"run": {"run_id": "unique-optimization"}}

        def log(self, *args):
            pass

    def interrupted_delivery(deployment, experiment):
        saved = read(experiment / "delivery-checkpoint.json")
        assert saved["producer"] == "unique-optimization"
        assert saved["native_method"]["optimization_run_id"] == "unique-optimization"
        assert Path(saved["odb"]).read_text() == "completed optimized ODB"
        assert saved["pdk"] == str(pdk.resolve())
        raise WorkPending({"reason": "import_outcome_unknown"})

    monkeypatch.setattr(module, "Jobs", Jobs)
    monkeypatch.setattr(module, "container", lambda d, command: command)
    monkeypatch.setattr(module, "finish", interrupted_delivery)
    deployment = SimpleNamespace(
        value={"toolchain": "fixed"}, experiment=lambda *args: output
    )
    with pytest.raises(WorkPending, match="import_outcome_unknown"):
        module.repeat(deployment, result, "trial2")
    assert dispatched == ["unique-optimization"]
