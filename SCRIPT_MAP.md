# Script Map

Canonical entrypoints for the standalone `dpl_evolve_agent` control plane.

All commands assume:

- `DPL_EVOLVE_AGENT_ROOT` points at this repo.
- `ORFS_ROOT` points at the external ORFS workspace.
- `DPL_EVOLVE_STATE_ROOT` points at mutable runtime state.

## Setup And Prepare

- `scripts/attach_orfs_workspace.sh`
  Optional ignored `.mounted_orfs` convenience link.
- `scripts/prepare_workspace.sh`
  Reset/apply the minimal ORFS/OpenROAD prepare patches.
- `scripts/run_place_batch.sh`
  Create reusable `3_4_place_resized.odb` snapshots.

## Common-Core Variant Relink

- `scripts/configure_openroad_core.sh`
  Select `${DPL_EVOLVE_STATE_ROOT}/openroad_core/<openroad_sha>`.
- `scripts/build_openroad_core.sh`
  Build reusable common OpenROAD core once.
- `scripts/configure_openroad_variant_relink.sh`
  Create `<variant-root>/variant_env.sh`.
- `scripts/build_openroad_variant_relink.sh`
  Rebuild only variant `dpl_evolve`, relink private `openroad`, and symlink
  common-core `sta` when available.

## Evaluation

- `adapters/science_codeevolve/evaluator.py`
  Preferred guarded single/suite evaluator.
- `scripts/run_canonical_line.sh`
  Manual one-line wrapper.
- `baseline/run_baseline_suite.sh`
  Manual suite wrapper.
- `scripts/compare_runs.py`
  Compare evaluator JSON or metrics summaries.

Always pass an explicit `--openroad-binary` for variant/family runs.

## Codex Loop

- `adapters/science_codeevolve/kb_query.py`
  Emit compact current-run packet.
- `scripts/run_design_evolve_loop.py`
  Outer loop: checkpoint -> packet -> Codex -> build -> evaluate ->
  accept/reject.
- `scripts/run_codex_exec.py`
  Low-level `codex exec --json` wrapper with usage logs.

Loop-driven Codex attempts should patch only target-plane files and should not
run build/evaluator/checkpoint commands themselves.

## Agent-Facing Docs

- `AGENTS.md`
  Hard operating contract.
- `skills/patch_rules.md`
  Patch boundaries.
- `skills/build_openroad.md`
  Build/relink rules.
- `skills/evaluate_run.md`
  Evaluator and metrics rules.
- `tasks/design_evolve/*.md`
  Minimal design prompts.

## Source vs Artifact

Authoring surfaces:

- `$DPL_EVOLVE_AGENT_ROOT/scripts/`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/`
- `$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/`
- `tools/OpenROAD/src/dpl_evolve/`

Generated artifacts, not source:

- `${DPL_EVOLVE_STATE_ROOT}/checkpoints/`
- `${DPL_EVOLVE_STATE_ROOT}/variants/*/build/`
- `flow/results/`
- `flow/reports/`
- `flow/logs/`
- `flow/objects/`
