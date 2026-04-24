#!/usr/bin/env python3
"""Preflight diff-scope validation for bounded Codex patches."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from runtime_paths import resolve_runtime_paths


FORBIDDEN_PREFIXES = (
    "flow/",
    "baseline/",
    "scripts/",
    "adapters/",
    "knowledge/",
    "problems/",
    "configs/",
    "tasks/",
    ".github/",
    "tools/OpenROAD/src/dpl/",
)

FORBIDDEN_EXACT = {
    ".gitmodules",
    "flow/Makefile",
    "Makefile",
}


def _run_git(root: Path, args: list[str]) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def changed_files(root: Path) -> list[str]:
    files: set[str] = set()
    files.update(_run_git(root, ["diff", "--name-only"]))
    files.update(_run_git(root, ["diff", "--cached", "--name-only"]))
    files.update(_run_git(root, ["ls-files", "--others", "--exclude-standard"]))
    return sorted(files)


def _norm_repo_path(path: str) -> str | None:
    if not path:
        return None
    expanded = os.path.expandvars(path)
    if expanded.startswith("$"):
        return None
    candidate = Path(expanded)
    if candidate.is_absolute():
        return None
    return str(candidate)


def allowed_files_from_packet(packet: dict[str, Any]) -> set[str]:
    surface = packet.get("selected_patch_surface", {})
    allowed: set[str] = set()
    target = _norm_repo_path(str(surface.get("file") or packet.get("target_file") or ""))
    if target:
        allowed.add(target)

    # Bounded mechanism patches may need a nearby declaration in the owning
    # legalizer header. Keep this narrow rather than allowing the whole problem
    # patch surface.
    if target in {
        "tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.cpp",
        "tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizerPass.cpp",
    }:
        allowed.add("tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.h")
    if target == "tools/OpenROAD/src/dpl_evolve/src/Opendp.cpp":
        allowed.add("tools/OpenROAD/src/dpl_evolve/src/Opendp.tcl")
    return allowed


def _is_forbidden(path: str) -> bool:
    if path in FORBIDDEN_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)


def run_preflight(*, orfs_root: Path, packet: dict[str, Any]) -> dict[str, Any]:
    files = changed_files(orfs_root)
    allowed = allowed_files_from_packet(packet)
    surface = packet.get("selected_patch_surface", {})
    family_variant_required = bool(surface.get("family_variant_required"))
    violations: list[dict[str, str]] = []
    warnings: list[str] = []

    for path in files:
        if _is_forbidden(path):
            violations.append(
                {
                    "path": path,
                    "reason": "forbidden control-plane, flow, or classic dpl path",
                }
            )
        elif path.startswith("tools/OpenROAD/src/dpl_evolve/") and path not in allowed:
            violations.append(
                {
                    "path": path,
                    "reason": "outside selected bounded dpl_evolve patch surface",
                }
            )
        elif path not in allowed:
            violations.append(
                {
                    "path": path,
                    "reason": "outside selected target file and narrow helper allowlist",
                }
            )

    if not files and not family_variant_required:
        violations.append({"path": "", "reason": "no source diff produced by bounded patch"})
    if family_variant_required:
        warnings.append(
            "materialized variant source may live outside ORFS git diff; outer loop must ensure variant source and binary paths are explicit"
        )

    ok = not violations
    return {
        "ok": ok,
        "status": "ok" if ok else "failed",
        "changed_files": files,
        "allowed_files": sorted(allowed),
        "violations": violations,
        "warnings": warnings,
        "selected_family": packet.get("selected_patch_family", {}).get("id"),
        "selected_symbol": surface.get("symbol"),
        "failure_signature": "; ".join(v["reason"] for v in violations[:3]) if violations else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orfs-root", type=Path)
    parser.add_argument("--packet-json", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    if args.orfs_root is None:
        runtime = resolve_runtime_paths(
            anchor_file=__file__,
            agent_root_levels_up=1,
            script_name="preflight.py",
        )
        orfs_root = runtime.orfs_root
    else:
        orfs_root = args.orfs_root.resolve()
    packet = json.loads(args.packet_json.read_text(encoding="utf-8"))
    result = run_preflight(orfs_root=orfs_root, packet=packet)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    raise SystemExit(0 if result["ok"] else 2)


if __name__ == "__main__":
    main()

