# LEGALM Engine Reference

Role: complete LEGALM-style sidecar source donor.

The durable source artifact is:

```text
dpl_evolve.patch
```

Use it as reference for staged legalization ideas:

1. relaxed/static-constraint initial placement,
2. ALM-style overflow reduction,
3. bounded no-overflow refinement.

This directory is not the active default evolve path.  New algorithm work
should port useful mechanisms into the constrained `EvolveLegalizer` framework
behind `detailed_placement_evolve`.

Old LEGALM worker notes, repair-lineage reports, and rejected/incremental
R4/R5 deltas were moved to:

```text
local_backups/legacy_family_flow_cleanup_20260425/
local_backups/reference_patch_audit_20260425/
```

Read those only for explicit forensics.
