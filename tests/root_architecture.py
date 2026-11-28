"""Resolve every physical module and nested import for architecture gates."""

import ast
from pathlib import Path


def module_paths(root):
    return {
        ".".join(p.relative_to(root).with_suffix("").parts): p
        for p in sorted(root.rglob("*.py"))
    }


def import_base(source, node):
    if not node.level:
        return (
            (node.module or "").removeprefix("chip_evolve.")
            if node.module != "chip_evolve"
            else ""
        )
    parts = source.split(".")[:-1]
    if node.level > len(parts) + 1:
        raise ValueError(f"Import escapes package: {source}:{node.lineno}")
    return ".".join(
        parts[: len(parts) - node.level + 1] + ([node.module] if node.module else [])
    )


def import_bindings(source, tree, modules):
    """Local binding -> (physical owner, exported member); inspect all AST depths."""
    bindings = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if not node.level and not (node.module or "").startswith("chip_evolve"):
                continue
            base = import_base(source, node)
            for alias in node.names:
                candidate = ".".join(filter(None, [base, alias.name]))
                if candidate in modules:
                    bindings[alias.asname or alias.name] = (candidate, "")
                elif base in modules:
                    bindings[alias.asname or alias.name] = (base, alias.name)
                elif candidate + ".__init__" in modules:
                    bindings[alias.asname or alias.name] = (candidate + ".__init__", "")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("chip_evolve."):
                    target = alias.name.removeprefix("chip_evolve.")
                    if target in modules:
                        bindings[alias.asname or alias.name] = (target, "")
    return bindings


def physical_import_graph(root):
    paths = module_paths(root)
    graph = {name: set() for name in paths}
    for name, path in paths.items():
        tree = ast.parse(path.read_text())
        graph[name].update(
            owner for owner, _ in import_bindings(name, tree, paths).values()
        )
        # The approved fixed alias table is an explicit set of runtime edges.
        if name == "_compat":
            table = next(
                n.value
                for n in tree.body
                if isinstance(n, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "ALIASES" for t in n.targets
                )
            )
            aliases = ast.literal_eval(table)
            for target in aliases.values():
                resolved = target.removeprefix("chip_evolve.")
                assert resolved in paths, target
                graph[name].add(resolved)
    return graph


def implementation_graph(root):
    graph = physical_import_graph(root)
    if not (root / "_compat.py").exists():
        return graph
    implementations = {
        name
        for name in graph
        if name.split(".")[0] in {"core", "facts", "execution", "workflow"}
        and not name.endswith(".__init__")
    }
    return {name: graph[name] & implementations for name in implementations}
