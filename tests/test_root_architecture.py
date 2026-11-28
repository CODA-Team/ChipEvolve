"""All root imports, including deferred imports, follow the release layers."""

from tests.test_result_metric_boundaries import reachable_modules, root_import_graph

LAYER_MODULES = {
    0: (
        "artifact_inputs",
        "candidates",
        "clock",
        "comparison_facts",
        "command_requests",
        "config",
        "contracts",
        "handoff_io",
        "jobs",
        "lifecycle",
        "metrics",
        "native_process",
        "progress",
        "proof_policy",
        "runtime",
        "result_io",
        "selection",
    ),
    1: (
        "code_evidence",
        "design_facts",
        "dpl_case",
        "flow_recipe",
        "source_snapshot",
        "stage_facts",
    ),
    2: ("delivery", "eqy", "logic", "native_physical", "physical"),
    3: (
        "comparisons",
        "dpl",
        "environment",
        "eco",
        "goal",
        "flow",
        "flow_evidence",
        "flow_delivery",
        "flow_replay",
        "goal_replay",
        "native",
        "validation",
    ),
    4: (
        "candidate_facts",
        "cli",
        "commands",
        "continuation",
        "controller",
        "diagnosis",
        "handoff",
        "professional",
        "recovery",
    ),
}


def cycle_groups(graph):
    reachable = {name: reachable_modules(graph, name) for name in graph}
    return sorted(
        {
            tuple(
                sorted(
                    {name}
                    | {
                        target
                        for target in reachable[name]
                        if name in reachable[target]
                    }
                )
            )
            for name in graph
            if name in reachable[name]
        }
    )


def layer_violations(graph):
    layers = {
        name: layer for layer, modules in LAYER_MODULES.items() for name in modules
    }
    return sorted(
        (source, target)
        for source, targets in graph.items()
        for target in targets
        if layers[target] > layers[source]
    )


def test_every_root_module_has_a_declared_layer():
    graph = root_import_graph()
    modules = [name for names in LAYER_MODULES.values() for name in names]
    assert len(modules) == len(set(modules))
    assert set(modules) == set(graph) - {"__init__"}


def test_all_root_imports_follow_the_declared_layers():
    assert layer_violations(root_import_graph()) == []


def test_root_package_has_zero_cyclic_import_groups():
    assert cycle_groups(root_import_graph()) == []


def test_import_analysis_includes_nested_functions_and_class_bodies(tmp_path):
    (tmp_path / "first.py").write_text(
        "def outer():\n"
        "    def inner():\n"
        "        from .second import value\n"
        "    return inner\n"
    )
    (tmp_path / "second.py").write_text(
        "class Consumer:\n    if True:\n        import chip_evolve.first\n"
    )
    graph = root_import_graph(tmp_path)
    assert graph == {"first": {"second"}, "second": {"first"}}
    assert cycle_groups(graph) == [("first", "second")]
