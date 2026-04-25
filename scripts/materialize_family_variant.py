#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import signal
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = AGENT_ROOT / "scripts"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

signal.signal(signal.SIGPIPE, signal.SIG_DFL)

from family_mutations import apply_matrix_mutation, list_supported_families, resolve_family_mutation
from runtime_paths import resolve_runtime_paths


@dataclass(frozen=True)
class MaterializedFamily:
    family: str
    base_src: Path
    output_dir: Path
    patch_file: Path | None
    touched_files: list[str]
    metadata_path: Path
    source_kind: str
    status: str


def _copy_tree(src: Path, dst: Path, *, force: bool) -> None:
    if dst.exists():
        if not force:
            raise FileExistsError(f"Output already exists: {dst}. Re-run with --force.")
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, symlinks=True)


def _run_git_apply(patch_file: Path, cwd: Path) -> None:
    proc = subprocess.run(
        ["git", "-C", str(cwd), "apply", str(patch_file)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git apply failed for {patch_file} in {cwd}\n{proc.stdout}")


def _write_metadata(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def materialize_family_variant(
    family: str,
    output_dir: Path | None = None,
    *,
    force: bool = False,
    agent_root: Path | None = None,
    orfs_root: Path | None = None,
    state_root: Path | None = None,
) -> MaterializedFamily:
    agent_root = (agent_root or AGENT_ROOT).resolve()
    if orfs_root is None or state_root is None:
        runtime = resolve_runtime_paths(
            anchor_file=__file__,
            agent_root_levels_up=1,
            script_name="materialize_family_variant.py",
        )
        orfs_root = orfs_root or runtime.orfs_root
        state_root = state_root or runtime.state_root
    orfs_root = orfs_root.resolve()
    state_root = state_root.resolve()

    recipe = resolve_family_mutation(family)
    clean_base = orfs_root / "tools" / "OpenROAD" / "src" / "dpl_evolve"
    if not clean_base.is_dir():
        raise RuntimeError(
            "Prepared dpl_evolve source is missing: "
            f"{clean_base}. Run scripts/prepare_workspace.sh first."
        )

    output_dir = (
        output_dir
        or state_root / "family_variants" / family / "dpl_evolve"
    ).resolve()

    if recipe.source_family not in {"clean_evolve_base", family} and recipe.source_family != "clean_evolve_base":
        parent_dir = output_dir.parent / "_parent" / recipe.source_family / "dpl_evolve"
        parent = materialize_family_variant(
            recipe.source_family,
            parent_dir,
            force=force,
            agent_root=agent_root,
            orfs_root=orfs_root,
            state_root=state_root,
        )
        base_src = parent.output_dir
    else:
        base_src = clean_base

    _copy_tree(base_src, output_dir, force=force)

    patch_file: Path | None = None
    touched_files: list[str] = []
    mutation_metadata: dict[str, Any] = {}

    if recipe.patch_file:
        patch_file = (agent_root / recipe.patch_file).resolve()
        if not patch_file.is_file():
            raise RuntimeError(f"Missing family patch: {patch_file}")
        _run_git_apply(patch_file, output_dir)
        touched_files.append(str(patch_file))

    generated_touched, mutation_metadata = apply_matrix_mutation(family, output_dir)
    touched_files.extend(generated_touched)
    touched_files = sorted(set(touched_files))

    metadata = {
        "schema_version": 1,
        "family": family,
        "source_kind": recipe.source_kind,
        "status": recipe.status,
        "summary": recipe.summary,
        "agent_root": str(agent_root),
        "orfs_root": str(orfs_root),
        "state_root": str(state_root),
        "base_src": str(base_src),
        "clean_base": str(clean_base),
        "output_dir": str(output_dir),
        "patch_file": str(patch_file) if patch_file else None,
        "touched_files": touched_files,
        "mutation": mutation_metadata,
    }
    metadata_path = output_dir.parent / "materialization.json"
    _write_metadata(metadata_path, metadata)

    return MaterializedFamily(
        family=family,
        base_src=base_src,
        output_dir=output_dir,
        patch_file=patch_file,
        touched_files=touched_files,
        metadata_path=metadata_path,
        source_kind=recipe.source_kind,
        status=recipe.status,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize a private dpl_evolve family source tree."
    )
    parser.add_argument("--family", help="Family or matrix variant id to materialize.")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--list-families", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_families:
        for item in list_supported_families():
            print(f"{item.family}\t{item.source_kind}\t{item.status}\t{item.summary}")
        return 0
    if not args.family:
        raise SystemExit("--family is required unless --list-families is used")

    result = materialize_family_variant(
        args.family,
        args.output_dir,
        force=args.force,
    )
    print("[INFO] Materialized family variant")
    print(f"[INFO] family={result.family}")
    print(f"[INFO] source_kind={result.source_kind}")
    print(f"[INFO] status={result.status}")
    print(f"[INFO] base={result.base_src}")
    print(f"[INFO] patch={result.patch_file}")
    print(f"[INFO] output={result.output_dir}")
    print(f"[INFO] metadata={result.metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
