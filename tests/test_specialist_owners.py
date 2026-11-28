"""Public compatibility exports retain identity without coupling the specialists."""

import ast
import inspect
from pathlib import Path

from chip_evolve import eco, goal, native


def test_native_exports_the_six_original_public_objects():
    owners = {
        "run_goal": goal,
        "run_eco": eco,
        "restore_goal_checkpoint": goal,
        "goal_checkpoint_origin": goal,
        "goal_producer": goal,
        "latest_producer": goal,
    }
    assert set(native.__all__) == set(owners)
    for name, owner in owners.items():
        assert getattr(native, name) is getattr(owner, name)
    for adapter in (goal.run_goal, eco.run_eco):
        assert list(inspect.signature(adapter).parameters) == [
            "deployment",
            "request",
            "experiment",
            "source",
            "objective",
            "context",
        ]


def test_compatibility_module_contains_no_business_implementation():
    tree = ast.parse(Path(native.__file__).read_text())
    assert not any(
        isinstance(n, (ast.FunctionDef, ast.ClassDef)) for n in ast.walk(tree)
    )
    assert not any(isinstance(n, ast.Call) for n in ast.walk(tree))


def test_specialist_owners_do_not_import_each_other_or_the_compatibility_module():
    from tests.test_result_metric_boundaries import root_import_graph

    graph = root_import_graph()
    assert not graph["goal"] & {"native", "eco", "professional", "commands"}
    assert not graph["eco"] & {"native", "goal", "professional", "commands"}
