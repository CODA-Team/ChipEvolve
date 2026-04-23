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

- run commands from an ORFS workspace where this repo is mounted as
  `evolve_agent/`
- for any `--family-variant` run, use an explicit variant binary
- prefer `build_openroad_only.sh` over rebuilding the whole ORFS stack
- treat `metrics.json` as the primary result interface
