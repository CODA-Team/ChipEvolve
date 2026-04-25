# Family Variants

This directory is now a compact algorithm-reference shelf, not the active
family-tree router.

Default agent context should read only:

- `REFERENCE_INDEX.yaml`
- `reference_sources/`
- `negotiation_parallel_frontier/` when negotiation-history code is assigned
- `legalm_engine/` when LEGALM sidecar code is assigned
- `../patches/PATCH_AUDIT.yaml` when deciding whether a patch-like file is a
  direct apply target or only a reference delta

Everything from the previous family-tree flow that is not part of those
references has been moved to:

```text
local_backups/legacy_family_flow_cleanup_20260425/
```

That backup is intentionally ignored by git.  Use it only for explicit
forensics, not as default context.

## Selection

- Use OpenROAD diamond as the current strict-track comparison anchor.
- Use `negotiation_parallel_frontier` only as a selected negotiation-history
  donor; old r5 records are superseded for default context.
- Use `legalm_engine/dpl_evolve.patch` as a complete LEGALM source donor, not
  as a direct base for the current framework.
- Use `reference_sources/dreamplace_abacus` as a row-assignment/compaction
  reference.
- Do not treat files under `reference_deltas/` as direct patches for the
  current framework.  They are compact mechanism examples to be ported.

New algorithm work should become a patch to the constrained framework behind
`detailed_placement_evolve`, not another default family directory.
