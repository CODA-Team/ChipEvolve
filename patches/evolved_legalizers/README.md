# Evolved Legalizer Patches

This directory preserves the final code from the three legalization-only
evolve tracks:

- `legalm`: global differential / LEGALM-oriented line, source commit
  `7f71b2f`, tag
  `candidate/legalm_20iter_001_iter_30_final_target_release_probes`.
- `negotiation`: NBLG / negotiation-oriented line, source commit `52f3b85`,
  tags `negotiation_20iter_001_iter_29` and
  `negotiation_20iter_001_iter_30`.
- `diamond`: Diamond/local-greedy-oriented line, source commit `c4d758a`, tag
  `diamond_20iter_001_iter_30`.

The clean OpenROAD target is the `openroad_base_commit` in
`../../metadata/anchors.json`, currently
`d14d526a6f8ce5388e2a8dc30da88a0189df2f46`.

## Lineage Table

| line | source commit | source tag | apply to clean OpenROAD | apply to base+framework |
| --- | --- | --- | --- | --- |
| `legalm` | `7f71b2f` | `candidate/legalm_20iter_001_iter_30_final_target_release_probes` | `openroad_dpl_evolve_legalm_iter30_from_clean.patch` | `openroad_dpl_evolve_legalm_iter30_framework_delta.patch` |
| `negotiation` | `52f3b85` | `negotiation_20iter_001_iter_29`, `negotiation_20iter_001_iter_30` | `openroad_dpl_evolve_negotiation_iter30_from_clean.patch` | `openroad_dpl_evolve_negotiation_iter30_framework_delta.patch` |
| `diamond` | `c4d758a` | `diamond_20iter_001_iter_30` | `openroad_dpl_evolve_diamond_iter30_from_clean.patch` | `openroad_dpl_evolve_diamond_iter30_framework_delta.patch` |

The table is the patch base contract.  If a patch is used outside that target
state, conflicts or misleading partial application are expected.

## Patch Types

- `openroad_dpl_evolve_<line>_iter30_from_clean.patch`: standalone patch for a
  clean OpenROAD checkout at the recorded anchor.  It includes the base
  `dpl_evolve` integration, the framework patch, and the selected evolved
  legalizer implementation.  Use this only when starting from the clean
  OpenROAD anchor.
- `openroad_dpl_evolve_<line>_iter30_framework_delta.patch`: compact review
  patch from the base+framework state to the selected evolved legalizer.  Apply
  it only after `openroad_dpl_evolve_base.patch` and
  `openroad_dpl_evolve_framework.patch`.  This is the patch type
  `prepare_workspace.sh` uses to materialize evolved start-kind seeds.

## Agent-Facing Meaning

These files are active donor/start-point artifacts, not stale backups.  The
`legalm`, `negotiation`, and `diamond` lines are prior iter30 evolved legalizer
starts with measured wins on some case archetypes.  They are not universal
defaults.  When a Teacher assigns a route, it should decide whether the Student
should start from:

- a clean route seed such as `diamond` or `framework`,
- the matching materialized evolved seed, such as `evolved_diamond`,
  `evolved_legalm`, or `evolved_negotiation`, or
- another start kind while borrowing only a specific evolved mechanism.

For normal Teacher/Student rounds, do not ask Students to manually apply these
OpenROAD-root patch files inside their private source tree.  Run
`scripts/prepare_workspace.sh` to materialize the corresponding seed sources
under `.dpl_evolve_state/seed_sources/`, then launch with
`--start-kind evolved_diamond`, `--start-kind evolved_legalm`, or
`--start-kind evolved_negotiation`.

## Usage

Apply one standalone line to clean OpenROAD:

```bash
git -C /path/to/OpenROAD checkout d14d526a6f8ce5388e2a8dc30da88a0189df2f46
git -C /path/to/OpenROAD apply /path/to/dpl_evolve_agent/patches/evolved_legalizers/openroad_dpl_evolve_legalm_iter30_from_clean.patch
```

Review or port only the evolved delta on top of the prepared framework:

```bash
git -C /path/to/OpenROAD apply /path/to/dpl_evolve_agent/patches/openroad_dpl_evolve_base.patch
git -C /path/to/OpenROAD apply /path/to/dpl_evolve_agent/patches/openroad_dpl_evolve_framework.patch
git -C /path/to/OpenROAD apply /path/to/dpl_evolve_agent/patches/evolved_legalizers/openroad_dpl_evolve_legalm_iter30_framework_delta.patch
```

`generation_manifest.tsv` records source commits and patch paths.
`validation.tsv` records `git apply --check` results for both patch types.
