"""Inspect real root calls and aliases, including deferred/private access."""

import ast
from pathlib import Path


def private_boundary_accesses(root):
    from tests.root_architecture import module_paths, import_bindings

    paths = module_paths(root)
    modules = set(paths)
    found = []
    for source, path in paths.items():
        tree = ast.parse(path.read_text())
        bindings = import_bindings(source, tree, modules)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    target = bindings.get(alias.asname or alias.name)
                    if target and target[0] != source and target[1].startswith("_"):
                        found.append(
                            (source, node.lineno, target[0], target[1], "import")
                        )

        def resolve(node):
            if isinstance(node, ast.Name):
                return bindings.get(node.id)
            if isinstance(node, ast.Attribute):
                base = resolve(node.value)
                if base and not base[1]:
                    return (base[0], node.attr)
                chain = ast.unparse(node)
                for name in modules:
                    prefix = "chip_evolve." + name + "."
                    if chain.startswith(prefix):
                        return (name, chain[len(prefix) :])
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
            ):
                base = resolve(node.args[0])
                if base and not base[1]:
                    name = node.args[1]
                    return (
                        base[0],
                        name.value
                        if isinstance(name, ast.Constant)
                        and isinstance(name.value, str)
                        else "<dynamic>",
                    )
            return None

        for _ in range(3):
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    bound = resolve(node.value)
                    if bound:
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                bindings[target.id] = bound
        for node in ast.walk(tree):
            if isinstance(node, (ast.Attribute, ast.Call)):
                target = (
                    resolve(node.func) if isinstance(node, ast.Call) else resolve(node)
                )
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "getattr"
                ):
                    target = resolve(node)
                if (
                    target
                    and target[0] != source
                    and (target[1].startswith("_") or target[1] == "<dynamic>")
                ):
                    found.append((source, node.lineno, target[0], target[1], "access"))
    return sorted(set(found))


def test_root_product_has_no_private_cross_module_access():
    assert private_boundary_accesses(Path(__file__).parents[1] / "chip_evolve") == []


def test_scanner_finds_import_alias_deferred_alias_and_getattr(tmp_path):
    (tmp_path / "source.py").write_text("def _private(): pass\n")
    (tmp_path / "caller.py").write_text(
        "from .source import _private as public\n"
        "from . import source as owner\n"
        "def nested():\n"
        "    import chip_evolve.source as other\n"
        "    alias = other._private\n"
        "    alias()\n"
        "    return getattr(owner, '_private')()\n"
        "public()\n"
    )
    found = private_boundary_accesses(tmp_path)
    assert any(row[1] == 1 and row[4] == "import" for row in found)
    assert {5, 6, 7, 8} <= {row[1] for row in found}


def test_scanner_rejects_dynamic_root_attribute_access(tmp_path):
    (tmp_path / "source.py").write_text("def operation(): pass\n")
    (tmp_path / "caller.py").write_text(
        "from . import source\ndef call(name): return getattr(source, name)()\n"
    )
    assert any(row[3] == "<dynamic>" for row in private_boundary_accesses(tmp_path))


def test_private_scanner_inspects_all_four_packages(tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "workflow").mkdir()
    (tmp_path / "core/source.py").write_text("def _private(): pass\n")
    (tmp_path / "workflow/caller.py").write_text(
        "from ..core import source as owner\ndef f():\n    return owner._private()\n"
    )
    assert any(
        row[0] == "workflow.caller" and row[2:4] == ("core.source", "_private")
        for row in private_boundary_accesses(tmp_path)
    )
