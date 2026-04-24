# Skills

These files are the repo-local operating skills for agents working on
`dpl_evolve`.

Read them in this order:

1. `patch_rules.md`
   Patch-surface boundaries and what not to touch.
2. `build_openroad.md`
   How to build the correct OpenROAD binary for clean and family-variant runs.
3. `run_single_baseline.md`
   How to run one canonical baseline/evolve line correctly.
4. `evaluate_run.md`
   How to inspect evaluator JSON and `metrics.json`.
5. `run_baseline_suite.md`
   How to run the small comparison bundle when one-line behavior looks good.
6. `run_codex_exec.md`
   How the external Codex wrapper is expected to behave.

Keep these rules in mind:

- resolve runtime through:
  - `DPL_EVOLVE_AGENT_ROOT`
  - `ORFS_ROOT`
  - `DPL_EVOLVE_STATE_ROOT`
- if you want a shortcut to the external ORFS workspace, use the ignored local
  mount at `$DPL_EVOLVE_AGENT_ROOT/.mounted_orfs`
- for any `--family-variant` run, use an explicit variant binary
- prefer the common-core plus variant-relink path over rebuilding the whole
  ORFS stack
- treat `metrics.json` as the primary result interface
