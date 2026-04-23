# Accepted Patches

This folder stores patch artifacts for families that have shown real value in
evaluation and should remain easy to reapply, inspect, or stack later.

The canonical status and interpretation still live in:

- `../replay_bank/family_registry.yaml`
- `../family_components/*.yaml`

This folder is for the code-level patch artifacts themselves.

If a family has moved to a clean reusable variant patch, prefer the matching
asset under `../../family_variants/` instead of keeping multiple overlapping
patch dumps here.

Guidelines:

- keep only patches that showed meaningful value on at least one real case
- if a patch is only a donor idea or was rejected, keep it in replay-bank notes
  instead of here
- prefer one patch file per promoted or promising family
