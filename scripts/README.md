# Scripts

This directory contains the active helper scripts for the constrained
`detailed_placement_evolve` framework.

Runtime roots:

- `DPL_EVOLVE_AGENT_ROOT`
- `ORFS_ROOT`
- `DPL_EVOLVE_STATE_ROOT`

## Active Entry Points

- `prepare_workspace.sh`: apply ORFS/OpenROAD patches, including the framework
  patch.
- `run_place_batch.sh`: create reusable placement snapshots.
- `run_canonical_line.sh`: run one canonical baseline/evolve line.
- `run_baseline_suite.sh` under `baseline/`: run the canonical comparison set.
- `configure_openroad_core.sh` and `build_openroad_core.sh`: build common core.
- `configure_openroad_variant_relink.sh` and
  `build_openroad_variant_relink.sh`: relink a private candidate binary.
- `checkpoint.py`: checkpoint/restore local candidate source state.
- `compare_runs.py`: compare evaluator outputs.
- `audit_repo_hygiene.py`: verify tracked patch/diff artifacts are explicitly
  classified and no old `family_variants/**/research_patches` reappears in
  default context.
- `run_codex_exec.py`, `run_codex_once.sh`, `run_codex_loop.sh`: Codex command
  wrappers.

Old family-matrix/materializer scripts were moved to:

```text
local_backups/legacy_family_flow_cleanup_20260425/scripts/
```

They are not part of the default workflow anymore.

## Typical Framework Flow

1. Prepare ORFS once:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/prepare_workspace.sh" \
  --workspace-root "$ORFS_ROOT"
```

2. Build or reuse common OpenROAD core:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" 10
```

3. Copy a candidate `dpl_evolve` source into `DPL_EVOLVE_STATE_ROOT`, relink,
   and run a canonical line with an explicit binary.

The default evolved command remains `detailed_placement_evolve`.
