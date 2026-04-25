# Robust Base Decision (2026-04-25)

This note summarizes the current family-compression decision.  It is meant to
protect future evolve runs from starting on families that build but are not yet
safe across small, medium, and large cases.

## Default Base Set

The default matrix group is now `robust_base`:

- `negotiation_row_bucket_active_set`
- `search_narrow_runtime`
- `netaware02_history_sqrt_anchor`

This is intentionally smaller than the idea bank.  Exploration families remain
available through explicit groups such as `family40`, `priority_repair`,
`priority_scale_safe_base`, `postopt_polish`, and `structural_experimental`.
Diagnostic fallback variants
remain available through `runtime_diagnostics`, but they are not base-family
evidence.

Current phase rule: base-family tuning temporarily ignores broad idea-bank
mixtures and self-evolution variants.  They may explain which mechanisms are
promising or dangerous, but they are not promoted until the mechanism is
isolated into a clean, scale-safe algorithm.  A legal result that materially
worsens HPWL, runtime, displacement, or timing proxy versus the same-run
baseline is not a successful base family.

## Evidence Used

Representative build smoke:

- Experiment id: `matrix_robust_base2_build_smoke_20260425`
- Historical result: the earlier robust-base candidate set relinked private
  OpenROAD binaries with no build errors.
- Current row-bucket re-gate:
  `negotiation_row_bucket_cap_aes_jpeg_gate_20260425`
- Result: `negotiation_row_bucket_active_set` relinked a private OpenROAD
  binary and passed strict `aes_nangate45` and `jpeg_nangate45`.

Large-design diagnostic gate:

- Experiment id: `large_design_fallback_gate_20260425`
- `aes_nangate45`: ok, legal, HPWL delta `9104.1865`, runtime `3.886s`.
- `jpeg_nangate45`: ok, legal, HPWL delta `164045.8655`, runtime `33.633s`.
- `bp_quad_nangate45`: the diagnostic implementation-level fallback triggered
  behind the same `detailed_placement_evolve -use_negotiation` entrypoint.  A
  `900s` retry produced legal metrics with HPWL delta `633663.4635`, average
  displacement `0.663um`, max displacement `61.656um`, and full evaluator
  elapsed time `574.551s`.
- Interpretation: this proves the snapshot, evaluator, and private-binary
  plumbing can finish.  It does not prove the negotiation or LEGALM family
  scales, because the evolved algorithm was routed around.  Keep this variant
  out of `robust_base`.

Scale-safe negotiation candidate:

- `negotiation_row_bucket_active_set` replaces the old
  illegal-seed-by-all-cell expansion with per-row spatial buckets, bounded
  row-local neighbor expansion, and bounded horizontal candidate sampling on
  large designs.
- `aes_nangate45`: legal, strict evolve negotiation, HPWL delta `9042.8765`,
  runtime `3.646s`; baseline in the same run was HPWL delta `9104.1865`,
  runtime `3.884s`.
- `jpeg_nangate45`: legal, strict evolve negotiation, HPWL delta `165971.8555`,
  runtime `25.183s`; baseline in the same run was HPWL delta `164045.8655`,
  runtime `33.256s`.
- `bp_quad_nangate45` timeout gate:
  `negotiation_row_bucket_cap_bp_quad_timeout_gate_20260425`
- `bp_quad_nangate45` result: no fallback; command was
  `detailed_placement_evolve -use_negotiation`.  Legalizer completed in `88s`
  with one negotiation iteration and reported `total overflow 0`, average
  displacement `0.7um`, max displacement `1.4um`, and delta HPWL `2%`.
  The outer `240s` evaluator gate timed out later in the full metrics/check
  stage before `metrics.json` was produced.

Net-aware gate:

- Experiment id: `netaware_robustness_smoke_20260425`
- `netaware02_history_sqrt_anchor`: legal on `aes` and `jpeg`; balanced
  runtime and quality.
- `netaware03_row_guard_frontier`: legal on `aes` and `jpeg`, best HPWL among
  tested net-aware variants, but slower on `jpeg` and timed out on `bp_quad`;
  keep it quality-biased in `netaware_base_robust` rather than default
  `robust_base`.
- `netaware06_soft_threshold_ladder`: legal but severe HPWL regression on
  `jpeg`.
- `netaware08_runtime_flat_slack`: legal but quality-neutral or worse.

Priority-escape gate:

- Artifact: `family_robustness/priority_escape/ROBUSTNESS_GATE_20260425.md`
- Current `priority_escape10` fails closed as a base family.  One tested
  variant timed out on `jpeg`; another was legal but severely degraded HPWL on
  both `aes` and `jpeg`.
- New runner candidate: `priority_escape_scale_safe_base` is available through
  `priority_scale_safe_base` and first in `priority_repair`.  It uses row
  buckets, dirty-region bystander scan, bounded frontier expansion, and
  candidate caps, but still needs strict aes/jpeg/bp_quad gates before
  promotion.

Localized-swap gate:

- Artifact: `family_robustness/localized_swap/ROBUSTNESS_DECISION_20260425.md`
- Current compressed `localswap01_bounded_local_polish` has encouraging
  `aes`/`jpeg` smoke results after adding hotsets, buckets, transactional
  rollback, and caps.  It still times out with the current `bp_quad` gate, so
  keep it as explicit postopt polish, not a base family.

LEGALM gate:

- Artifact: `family_robustness/legalm_engine/ROBUSTNESS_GATE_20260425.md`
- `legalm01_hpwl_pinwide` builds and passes `aes`, but fails `jpeg`.
- A Stage1 full-window search passes `jpeg` but has a large displacement
  outlier and is too broad to count as scale-safe.
- `legalm_base_bounded_stage1` is the current base-family candidate.  It uses
  bounded Stage1 recovery windows, conservative displacement scoring, local
  refinement, and the same common evolve entrypoint.  It still needs
  `aes`/`jpeg`/`bp_quad` gate results before being called robust.

## Current Interpretation

`bp_quad` separates legalizer robustness from full-metrics runtime. The
row-bucket/candidate-cap variant now returns from the negotiation legalizer
without routing to another algorithm, while the `240s` bounded evaluator still
times out during the full metrics/check phase.  The older diagnostic
default/diamond path only proves the snapshot and harness can finish; it does
not count as a base-family pass.

For future work, treat `bp_quad` as a two-stage gate:

- Legalizer gate: the private binary must produce a legal placement through the
  same evolve command without entering the negotiation timeout trap.
- Full-metrics gate: the evaluator must produce `metrics.json` within the
  configured timeout.  For `bp_quad`, use at least `900s` unless the metrics
  stage is optimized.

Do not promote a family into `robust_base` unless both gates are understood.

## R3 Worker Update

The 2026-04-25 R3 family workers tightened the current decisions:

- `negotiation_scale_component_dirty`: reject for promotion. It is legal and
  faster on `aes`/`jpeg`, but HPWL and displacement regress versus the same-run
  baseline.
- `netaware11_local_hpwl_anchor_cap`: quality-biased repair candidate only.
  It substantially improves HPWL/timing proxies on `aes`/`jpeg`, but runtime
  and max displacement are not yet base-quality.
- `priority_escape_r3_20260425`: narrow repair only. It uses a diamond-first
  acceptance gate and therefore does not prove priority escape as the evolved
  base algorithm.
- `localized_swap`: reject current implementation for promotion. The current
  hotbucket/rollback polish path is legal but much worse than the same-run
  baseline on HPWL, runtime, displacement, and timing proxies.
- `legalm_base_bounded_stage1`: reject current R3 repair. It still fails
  strict `aes_nangate45` with `DPL-1803`, so no legality or metrics evidence is
  available.

The practical default remains: tune scale-safe negotiation and light net-aware
objective/ranking first; keep LEGALM as an important structural direction only
after its legality failure has telemetry; keep localized swap and priority
escape as follow-up repair/polish, not initial base parents.
