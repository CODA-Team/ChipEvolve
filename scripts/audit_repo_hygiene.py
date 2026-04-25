#!/usr/bin/env python3
"""Repository hygiene checks for patch-like artifacts.

This keeps default agent context honest: every tracked `.patch` / `.diff` must
be explicitly classified, and old `research_patches` directories must not creep
back into the visible repo.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


AGENT_ROOT = Path(__file__).resolve().parents[1]
PATCH_AUDIT = AGENT_ROOT / "patches" / "PATCH_AUDIT.yaml"


def git_ls_files(*patterns: str) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(AGENT_ROOT), "ls-files", *patterns],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def audited_paths() -> set[str]:
    text = PATCH_AUDIT.read_text(encoding="utf-8")
    return set(re.findall(r"^\s*-\s+path:\s+(.+?)\s*$", text, flags=re.MULTILINE))


def main() -> int:
    tracked_patch_files = set(git_ls_files("*.patch", "*.diff"))
    audit_paths = audited_paths()
    missing = sorted(tracked_patch_files - audit_paths)
    stale = sorted(
        path
        for path in audit_paths
        if path.endswith((".patch", ".diff")) and path not in tracked_patch_files
    )
    visible_research = sorted(
        path for path in git_ls_files("family_variants/**") if "/research_patches/" in path
    )

    ok = True
    if missing:
        ok = False
        print("[FAIL] Tracked patch/diff files missing from patches/PATCH_AUDIT.yaml:")
        for path in missing:
            print(f"  - {path}")
    if stale:
        ok = False
        print("[FAIL] PATCH_AUDIT.yaml lists patch/diff files that are not tracked:")
        for path in stale:
            print(f"  - {path}")
    if visible_research:
        ok = False
        print("[FAIL] Visible family_variants research_patches are not allowed:")
        for path in visible_research:
            print(f"  - {path}")
    if ok:
        print("[OK] Patch inventory is explicit and default context has no research_patches.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
