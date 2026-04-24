# Routing

Routing turns existing project knowledge into a bounded patch target.

- `patch_family_router.py` chooses the startpoint/family from design profile
  and effective-family rules.
- `region_selector.py` maps that family to one function-level patch surface
  from `adapters/science_codeevolve/patch_surface.yaml`.

Codex should not redo this routing during a bounded patch turn. It should follow
the selected family, target file, symbol, and line window in the current packet.

