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
        "toolchain",
        "resources",
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


def test_every_physical_module_and_skeleton_is_audited():
    from pathlib import Path
    from tests.root_architecture import physical_import_graph, implementation_graph

    root = Path(__file__).parents[1] / "chip_evolve"
    graph = physical_import_graph(root)
    implementations = implementation_graph(root)
    assert len(implementations) == 51
    assert {
        package: sum(n.startswith(package + ".") for n in implementations)
        for package in ("core", "facts", "execution", "workflow")
    } == {"core": 19, "facts": 6, "execution": 5, "workflow": 21}
    assert set(graph) - set(implementations) == {
        "__init__",
        "_compat",
        "comparisons",
        "continuation",
        "core.__init__",
        "facts.__init__",
        "execution.__init__",
        "workflow.__init__",
    }
    assert cycle_groups(graph) == []
    assert cycle_groups(implementations) == []
    assert layer_violations(root_import_graph()) == []
    for name, targets in implementations.items():
        for target in targets:
            assert (
                target.split(".")[0] in {"core", name.split(".")[0]}
                or {"workflow": 3, "execution": 2, "facts": 1, "core": 0}[
                    target.split(".")[0]
                ]
                < {"workflow": 3, "execution": 2, "facts": 1, "core": 0}[
                    name.split(".")[0]
                ]
            )
    assert not any(
        t in {"comparisons", "continuation", "_compat", "__init__"}
        for targets in implementations.values()
        for t in targets
    )


def test_recursive_scanner_finds_cross_package_nested_cycles(tmp_path):
    from tests.root_architecture import physical_import_graph

    for name in ("core", "workflow"):
        (tmp_path / name).mkdir()
    (tmp_path / "core/a.py").write_text("def f():\n    from ..workflow.b import f\n")
    (tmp_path / "workflow/b.py").write_text(
        "class C:\n    from chip_evolve.core import a\n"
    )
    graph = physical_import_graph(tmp_path)
    assert graph == {"core.a": {"workflow.b"}, "workflow.b": {"core.a"}}
    assert cycle_groups(graph) == [("core.a", "workflow.b")]


def test_implementation_imports_use_only_canonical_physical_owners():
    import ast
    from pathlib import Path
    from tests.root_architecture import module_paths

    root = Path(__file__).parents[1] / "chip_evolve"
    for name, path in module_paths(root).items():
        if "." not in name or name.endswith(".__init__"):
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.ImportFrom)
                and not node.level
                and (node.module or "").startswith("chip_evolve")
            ):
                assert node.module.split(".")[1] in {
                    "core",
                    "facts",
                    "execution",
                    "workflow",
                }, (name, node.lineno)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("chip_evolve."):
                        assert alias.name.split(".")[1] in {
                            "core",
                            "facts",
                            "execution",
                            "workflow",
                        }, (name, node.lineno)
