# Family Robustness Gate

This directory records whether a family is safe as an initial parent for
normal evolve loops.  Exploration ideas can be bold, but a base family must be
boring in one specific way: it must compile, run the strict evaluator, avoid
legality failures, and avoid obvious runtime blowups on small, medium, and
large stress cases.

Current rollup: `ROBUST_BASE_DECISION_20260425.md`.

Read these compact family notes before opening raw experiment artifacts:

- `negotiation_row_bucket/HARDENING_SUMMARY_20260425.md`
- `netaware_objective/HARDENING_SUMMARY_20260425.md`
- `legalm_engine/NEXT_ALGORITHM_DIRECTION_20260425.md`
- `priority_escape/HARDENING_DECISION_20260425.md`
- `localized_swap/HARDENING_DECISION_20260425.md`

## Current Decision

Use `robust_base` as the default family group:

- `negotiation_row_bucket_active_set`
- `search_narrow_runtime`
- `netaware02_history_sqrt_anchor`

Keep `netaware03_row_guard_frontier` in `netaware_base_robust` as a
quality-biased opt-in, not the default robust-base runtime path.

Do not add a family to this default group just because it builds, passes
`aes`, or survives through a diagnostic fallback. The current base-family phase
is focused on making a few real algorithms high-quality and scale-safe. Broad
idea-bank composites and algobank-style mixtures are evidence only until their
mechanism is isolated and hardened.

Keep these groups opt-in:

- broader `netaware10`: only `netaware02` and `netaware03` currently have
  robust-base evidence.  `netaware06` and `netaware08` pass legality but are
  quality-neutral or quality-negative.
- `priority_repair`: priority-escape candidates need runtime and HPWL guards
  before promotion.  Current evidence includes a jpeg timeout and a legal
  aes/jpeg variant with severe HPWL degradation.  The repair group now leads
  with `priority_escape_scale_safe_base`, which uses row buckets,
  dirty-region bystander scans, bounded frontier expansion, and per-cell
  candidate caps; older small-case escape probes remain secondary exploration.
- `localized_swap`: follow-up polish only.  Current runnable variants are
  postopt/cost composites over a full-pair `cellSwap()` implementation, so they
  are not robust bases for `jpeg` or `bp_quad`.
- `legalm_engine`: important structural base-family direction, but currently
  pending legality repair.  The R3 bounded Stage1 repair still fails
  `aes_nangate45` with `DPL-1803`, so LEGALM is not in the default base group
  until telemetry identifies and fixes the failing stage. Broader `legalm10`
  exploration remains opt-in. Same command path is required; full-grid scans
  or fallback-to-diamond do not count as robust-family evidence.
- `runtime_diagnostics`: contains fallback/safety-fuse variants such as
  `large_design_diamond_fallback`; these are useful to prove the harness and
  snapshot can finish, but they are not robust-base candidates.

Fallback-to-diamond or fallback-to-default may be kept as diagnostic safety
fuses, but they are not robust bases.  A base family must adapt its own
algorithmic path to large designs through bounded candidate generation,
spatial buckets, dirty-region scans, hotsets, capped repair queues, or
transactional rollback.
Small-case tuning does not override this rule: `aes` legality or HPWL gains
are smoke evidence only until the same family has a scale mechanism and
`jpeg`/`bp_quad` gate evidence.

## Promotion Gate

A family may become a robust base only after:

- representative variants build and relink private OpenROAD binaries;
- `aes_nangate45` passes strict legality with reasonable HPWL/runtime;
- `jpeg_nangate45` passes strict legality without large runtime blowup;
- `bp_quad_nangate45` either passes within the runtime budget or has an
  algorithmic scale mechanism, such as bounded active sets, buckets, dirty
  scans, or capped repair queues, that completes the legalizer and has an
  explicit full-metrics timeout record;
- failures, if any, are recorded as family-specific evidence rather than hidden
  by changing evaluator commands.

All families must use the same strict evolve entrypoint.  Family differences
belong inside the private `dpl_evolve` implementation.

For `bp_quad_nangate45`, the current full strict metrics stage is heavy.  Use
`--eval-timeout-sec 900` for robustness gates unless that metrics path is
separately optimized.

## Useful Commands

Build-only smoke for representative families:

```bash
source env.sh
python3 scripts/run_variant_experiment_matrix.py \
  --experiment-id matrix_family_representative_build_smoke_$(date +%Y%m%d_%H%M%S) \
  --family-groups flow_ready_candidates \
  --cases aes_nangate45 \
  --build-only \
  --build-jobs 2 \
  --build-threads 4
```

Default robust-base matrix:

```bash
source env.sh
scripts/run_family_variant_matrix.sh matrix_robust_base_$(date +%Y%m%d_%H%M%S)
```

Full exploration matrix, opt-in only:

```bash
source env.sh
DPL_EVOLVE_MATRIX_FAMILY_GROUPS="netaware10 localized_swap10 priority_escape10 legalm10" \
scripts/run_family_variant_matrix.sh matrix_family_explore_$(date +%Y%m%d_%H%M%S)
```
