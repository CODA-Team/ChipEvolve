# Calibration

This directory is the tracked contract for ReviewDSE Level 1 calibration.
It is distinct from the target-local start-kind probe that writes
`$DPL_EVOLVE_STATE_ROOT/<round_id>/start_seed_calibration/`.

Use `$DPL_EVOLVE_AGENT_ROOT`, `$ORFS_ROOT`, and `$DPL_EVOLVE_STATE_ROOT` for
all directory prefixes in calibration plans, reports, scripts, and generated
packets.

Level 1 calibration builds frozen method evidence and source-start provenance
from diagnostic calibration designs before target-case Teacher/Student search.
Target search may consume this frozen evidence as prior guidance, but it must
not update global Level 1 records.

## Directory Roles

- `case_sets/`: calibration-only case-set definitions and target-disjointness
  notes.
- `plans/`: reusable calibration run plans.
- `evidence/`: reviewed mechanism evidence records and compact summaries.
- `source_starts/`: source-start branch specifications and provenance.
- `schemas/`: JSON schemas for calibration manifests, evidence records, and
  source-start specs.
- `reports/`: frozen human-readable summaries for Teacher initialization.

Generated calibration runs stay under:

```text
$DPL_EVOLVE_STATE_ROOT/calibrations/<calibration_id>/
```

## Evidence Rules

- Calibration designs are diagnostic probes, not target designs.
- Evidence records describe mechanisms, not whole-patch winners only.
- Source-start specs describe how a source basin was constructed; generated
  source trees stay under the state root.
- Level 2 target search can accumulate target-local evidence, but it does not
  rewrite Level 1 evidence.
