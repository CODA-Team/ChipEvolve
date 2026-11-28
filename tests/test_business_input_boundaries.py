"""Malformed business inputs must fail before a single EF submission."""

import ast
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from openroad_platform_client import KernelClient

from chip_evolve.workflow import commands, professional
from chip_evolve.core.command_requests import CompareCommand, RunCommand, SelectCommand
from chip_evolve.core.contracts import BusinessInputError
from chip_evolve.core.result_io import (
    load_physical_result,
    load_context_ref,
    specialist_reply,
)
from tests.test_business_contracts import result_file, context_file
from tests.test_local_business import deployment


@pytest.fixture
def submissions(monkeypatch):
    calls = []

    def submit(*args, **kwargs):
        calls.append((args, kwargs))
        pytest.fail("Invalid input reached EF submit")

    monkeypatch.setattr(KernelClient, "submit", submit)
    yield calls
    assert calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "container",
        "none",
        "bool",
        "string",
        "nan",
        "inf",
        "-inf",
        "overflow",
        "negative_count",
        "fraction_count",
        "schema",
        "objective",
        "condition",
        "clock",
    ],
)
def test_run_invalid_result_has_ef_submit_zero(tmp_path, submissions, mutation):
    d = deployment(tmp_path)
    path = result_file(tmp_path / "source")
    frame = json.loads(path.read_text())
    if mutation == "missing":
        del frame["run_id"]
    elif mutation == "container":
        frame["metrics"] = []
    elif mutation in {"none", "bool", "string", "nan", "inf", "-inf", "overflow"}:
        frame["metrics"]["finish__power__total"] = {
            "none": None,
            "bool": True,
            "string": "1",
            "nan": float("nan"),
            "inf": float("inf"),
            "-inf": float("-inf"),
            "overflow": float("inf"),
        }[mutation]
    elif mutation in {"negative_count", "fraction_count"}:
        frame["route_drc"] = -1 if mutation == "negative_count" else 0.1
    elif mutation == "schema":
        frame["schema_version"] = "unknown.v2"
    elif mutation in {"objective", "condition"}:
        frame[mutation + "_id"] = "a" * 64
    else:
        frame["conditions"]["clock_period_ns"] = 99
    raw = json.dumps(frame)
    if mutation == "overflow":
        raw = raw.replace("Infinity", "1e999")
    path.write_text(raw)
    before = path.read_bytes()
    with pytest.raises(BusinessInputError, match=r"\$"):
        commands.run_experiment(
            d, RunCommand(d.path, "gcd", "invalid", "eco", source=path)
        )
    assert submissions == []
    assert path.read_bytes() == before
    assert not (tmp_path / "experiments").exists()


@pytest.mark.parametrize("budget", [0, -1, True, "60", 1.5])
def test_run_invalid_budget_has_ef_submit_zero(tmp_path, submissions, budget):
    d = deployment(tmp_path)
    with pytest.raises(BusinessInputError, match="seconds"):
        commands.run_experiment(
            d, RunCommand(d.path, "gcd", "invalid", "eco", seconds=budget)
        )
    assert submissions == []
    assert not (tmp_path / "experiments").exists()


@pytest.mark.parametrize(
    "mutation", ["container", "missing", "citation", "snapshot", "run"]
)
def test_professional_bad_context_has_ef_submit_zero(tmp_path, submissions, mutation):
    d = deployment(tmp_path)
    path = result_file(tmp_path / "source")
    frame = json.loads(path.read_text())
    frame["snapshot_ids"] = {"opendb": "snapshot-db"}
    path.write_text(json.dumps(frame))
    context = context_file(tmp_path, load_physical_result(path))
    value = json.loads(context.read_text())
    if mutation == "container":
        value["evidence"] = []
    elif mutation == "missing":
        del value["scope"]["design_id"]
    elif mutation == "citation":
        value["confirmed_facts"][0]["evidence_ids"] = ["missing"]
    else:
        value["scope"]["snapshot_id" if mutation == "snapshot" else "run_id"] = (
            "another"
        )
    del value["context_id"]
    value["context_id"] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    context.write_text(json.dumps(value))
    request = RunCommand(
        d.path, "gcd", "invalid", "eco", source=path, context=context
    ).normalized()
    with pytest.raises(BusinessInputError, match=r"\$"):
        professional.execute(d, request, tmp_path / "unused")
    assert submissions == []
    assert not (tmp_path / "unused").exists()


@pytest.mark.parametrize("entry", ["compare", "select", "validate", "diagnose"])
def test_all_result_command_boundaries_reject_bad_metrics(tmp_path, submissions, entry):
    from chip_evolve.core.command_requests import ValidateCommand, DiagnoseCommand

    d = deployment(tmp_path)
    path = result_file(tmp_path / "source")
    frame = json.loads(path.read_text())
    frame["metrics"]["finish__power__total"] = None
    path.write_text(json.dumps(frame))
    with pytest.raises(BusinessInputError, match="finish__power__total"):
        if entry == "compare":
            commands.compare(d, CompareCommand(path, path))
        elif entry == "select":
            commands.select(
                d, SelectCommand(path, "reject", tmp_path / "not-read.json")
            )
        elif entry == "validate":
            commands.validate(d, ValidateCommand(path, path, "invalid"))
        else:
            commands.diagnose(d, DiagnoseCommand(path, "explain"))
    assert submissions == []


def test_argparse_is_confined_to_cli_and_never_passed_to_business():
    root = Path(__file__).parents[1] / "chip_evolve"
    allowed = {"cli", "comparisons", "continuation"}
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            and (
                (isinstance(node, ast.ImportFrom) and node.module == "argparse")
                or (
                    isinstance(node, ast.Import)
                    and any(n.name == "argparse" for n in node.names)
                )
            )
        ]
        assert not imports or path.stem in allowed, path
        if path.stem not in allowed:
            assert not any(
                isinstance(n, ast.Attribute)
                and n.attr in {"Namespace", "ArgumentParser", "parse_args"}
                for n in ast.walk(tree)
            ), path
    cli = ast.parse((root / "workflow/cli.py").read_text())
    for node in ast.walk(cli):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "handlers"
        ):
            assert not any(
                isinstance(a, ast.Name) and a.id in {"args", "parser"}
                for a in node.args
            )


def test_canonical_interface_annotations_name_contracts_not_any_dictionaries():
    targets = {
        "professional": ["execute"],
        "flow": ["run_flow"],
        "dpl": ["run_dpl"],
        "goal": ["run_goal"],
        "eco": ["run_eco"],
        "comparison_facts": ["compare_results"],
        "selection": ["select_result", "result_violations"],
    }
    root = Path(__file__).parents[1] / "chip_evolve"
    for module, names in targets.items():
        functions = {
            n.name: n
            for n in ast.parse(next(root.rglob(module + ".py")).read_text()).body
            if isinstance(n, ast.FunctionDef)
        }
        for name in names:
            function = functions[name]
            for arg in function.args.args:
                assert arg.annotation is not None, (module, name, arg.arg)
                annotation = ast.unparse(arg.annotation)
                assert "Any" not in annotation and "dict[" not in annotation, (
                    module,
                    name,
                    annotation,
                )


@pytest.mark.parametrize("capability", ["flow", "dpl", "goal", "eco"])
def test_public_specialist_adapters_deliver_typed_replies(
    tmp_path, monkeypatch, capability
):
    from tests.contract_fixtures import unit_admission

    unit_admission(monkeypatch, orchestration=True)
    from chip_evolve.workflow import flow, dpl, goal, eco
    from chip_evolve.core.candidates import deliver_candidates
    from tests.test_professional_handoff_contract import registered_source
    from tests.contract_fixtures import specialist_request

    source_path = result_file(tmp_path / "source")
    raw = json.loads(source_path.read_text())
    raw["snapshot_ids"] = {"opendb": "snapshot-db"}
    registered_source(tmp_path, raw)
    source_path.write_text(json.dumps(raw))
    source = load_physical_result(source_path)
    context = load_context_ref(context_file(tmp_path, source))
    d = deployment(tmp_path)
    experiment = d.experiment("gcd", "delivery")
    output = result_file(tmp_path / "measured")
    captured = []

    def native_transport(*args):
        captured.append(args)
        if capability == "flow":
            return deliver_candidates(experiment, [output])
        (experiment / "result.json").write_bytes(output.read_bytes())
        return json.loads(output.read_text())

    module = {"flow": flow, "dpl": dpl, "goal": goal, "eco": eco}[capability]
    monkeypatch.setattr(module, "_run_" + capability + "_transport", native_transport)
    reply = getattr(module, "run_" + capability)(
        d, specialist_request(capability), experiment, source, source.objective, context
    )
    assert reply.capability == capability and reply.outcome == "delivered"
    assert reply.output.origin.path == experiment / "result.json"
    assert (
        reply.output.origin.sha256
        == hashlib.sha256((experiment / "result.json").read_bytes()).hexdigest()
    )
    assert captured[0][1].capability == capability
    assert captured[0][3] == json.loads(source_path.read_text())


def test_failed_native_search_with_measured_evidence_is_not_success(tmp_path):
    from chip_evolve.core.candidates import deliver_candidates

    path = result_file(tmp_path / "source")
    experiment = tmp_path / "delivery"
    experiment.mkdir()
    deliver_candidates(
        experiment,
        [path],
        native_campaign={"status": "failed", "reason": "retained measured evidence"},
    )
    reply = specialist_reply("flow", experiment / "result.json")
    assert reply.outcome == "evidence_only"
    assert reply.output.execution_state == "failed"
    assert reply.output.wire["adopted"] is False


@pytest.mark.parametrize(
    "field", ["receiver", "source_files", "source_run_id", "sha256"]
)
def test_bad_handoff_is_rejected_without_submitting(
    tmp_path, monkeypatch, submissions, field
):
    from chip_evolve.core import artifact_inputs
    from tests.test_professional_handoff_contract import registered_source
    from types import SimpleNamespace

    path = result_file(tmp_path / "source")
    frame = json.loads(path.read_text())
    client, _ = registered_source(tmp_path, frame)
    path.write_text(json.dumps(frame))
    source = load_physical_result(path)
    jobs = SimpleNamespace(design_id="gcd", client=client)
    wire = artifact_inputs.input_contract(jobs, frame, "eco")
    if field == "receiver":
        wire["receiver"] = "goal"
    elif field == "source_files":
        del wire["source_files"]["spef"]
    elif field == "source_run_id":
        wire["source_run_id"] = "another"
    else:
        wire["source_files"]["odb"]["sha256"] = "invalid"
    monkeypatch.setattr(artifact_inputs, "input_contract", lambda *a, **kw: wire)
    with pytest.raises(BusinessInputError, match=r"\$"):
        artifact_inputs.build_handoff(jobs, source, "eco")
    assert submissions == []


@pytest.mark.parametrize("field", ["rounds", "candidates"])
@pytest.mark.parametrize("value", [0, -1, True, "2", 1.5])
def test_other_invalid_search_budgets_submit_nothing(
    tmp_path, submissions, field, value
):
    d = deployment(tmp_path)
    request = replace(RunCommand(d.path, "gcd", "invalid", "flow"), **{field: value})
    with pytest.raises(BusinessInputError, match=field):
        commands.run_experiment(d, request)
    assert submissions == []


@pytest.mark.parametrize(
    "capability,seconds,rounds,candidates,recipe",
    [
        ("orfs", 5400, 1, None, "legacy"),
        ("flow", 10800, 2, 12, "source"),
        ("dpl", 10800, 1, 3, "legacy"),
        ("goal", 10800, 1, 4, "legacy"),
        ("eco", 5400, 1, None, "legacy"),
    ],
)
def test_default_normalization_preserves_flat_request_wire(
    tmp_path, capability, seconds, rounds, candidates, recipe
):
    command = RunCommand(tmp_path / "local.json", "gcd", "test", capability)
    normalized = command.normalized()
    assert command.seconds is None and command.flow_recipe is None
    wire = normalized.to_wire()
    assert wire == {
        "config": str(command.config),
        "command": "run",
        "design": "gcd",
        "key": "test",
        "capability": capability,
        "source": None,
        "objective": None,
        "context": None,
        "code_source": None,
        "environment": None,
        "operation": "evolve",
        "seconds": seconds,
        "rounds": rounds,
        "candidates": candidates,
        "flow_recipe": recipe,
    }
    assert "budget" not in wire


@pytest.mark.parametrize(
    "mutation", ["sha", "summary", "duplicate", "identity", "state", "cycle"]
)
def test_bad_collection_cannot_reach_a_specialist(tmp_path, submissions, mutation):
    from chip_evolve.core.candidates import deliver_candidates

    d = deployment(tmp_path)
    one = result_file(tmp_path / "source", "one")
    two = result_file(tmp_path / "source", "two", 1.5)
    target = tmp_path / "collection"
    target.mkdir()
    wire = deliver_candidates(target, [one, two])
    path = target / "result.json"
    if mutation == "sha":
        two.write_text(two.read_text() + " ")
    elif mutation == "summary":
        wire["candidate_results"][0]["metrics"]["finish__power__total"] = 99
    elif mutation == "duplicate":
        wire["candidate_results"][1] = wire["candidate_results"][0]
    elif mutation == "identity":
        wire["candidate_results"][1]["condition_id"] = "a" * 64
    elif mutation == "state":
        wire["execution_state"] = "running"
    else:
        wire["candidate_results"][0]["result"] = str(path)
    path.write_text(json.dumps(wire))
    with pytest.raises(BusinessInputError, match=r"\$"):
        commands.run_experiment(
            d, RunCommand(d.path, "gcd", "invalid", "eco", source=path)
        )
    assert submissions == []
