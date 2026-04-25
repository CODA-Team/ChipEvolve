# Broader Case Sweep (2026-04-22)

## Scope

This note extends the earlier `gcd_nangate45`, `aes_nangate45`, and
`gcd_asap7` observations to larger cases using the current best
HPWL-aware/wide-postopt patch family.

Compared lines:
- `baseline_nblg`
- `evolve_default` with the negotiation-family source stack

Shared setup:
- `track = strict`
- `flow_variant = place_batch_20260421_220319`

## Results

### `ibex_nangate45`

Baseline:
- runtime `4.433 s`
- HPWL delta `16432.4155`
- setup WNS `0.00728351`

Evolve:
- runtime `54.64 s`
- HPWL delta `6556.6705`
- setup WNS `0.015268`

Takeaway:
- HPWL and WNS both improve strongly
- runtime grows by about `12.3x`

### `aes_asap7`

Baseline:
- runtime `5.322 s`
- HPWL delta `5220.818`
- setup WNS `-27.091`
- setup TNS `-245.143`

Evolve:
- runtime `71.623 s`
- HPWL delta `2236.082`
- setup WNS `-20.4597`
- setup TNS `-151.734`

Takeaway:
- HPWL/WNS/TNS all improve strongly
- runtime grows by about `13.5x`

### `jpeg_nangate45`

Baseline:
- runtime `34.667 s`
- HPWL delta `164045.8655`
- setup WNS `-0.130415`
- setup TNS `-49.8277`

Evolve:
- runtime `511.864 s`
- HPWL delta `63849.0555`
- setup WNS `-0.118497`
- setup TNS `-41.3098`

Takeaway:
- HPWL/WNS/TNS all improve
- runtime grows by about `14.8x`
- this confirms the current patch family is not runtime-viable as a default
  policy for large designs

## Main conclusion

The current HPWL-aware wide-postopt family generalizes in quality, but not in
runtime. On larger designs it behaves like a high-quality refinement stage,
not like a drop-in replacement for the baseline negotiation legalizer.

That means the next aggressive family should focus on:
- selective refinement budget
- stronger stuck-cell targeting
- stall-triggered refinement rather than always-on wide refinement

That next family is now tracked in:
- `evolve_agent/knowledge/replay_bank/selective_refinement_budget_observations_20260422.md`

## Supporting artifacts

- `evolve_agent/checkpoints/operations/manual_broader_case_sweep_20260422/ibex_n45_baseline.json`
- `evolve_agent/checkpoints/operations/manual_broader_case_sweep_20260422/ibex_n45_evolve.json`
- `evolve_agent/checkpoints/operations/manual_broader_case_sweep_20260422/aes_asap7_baseline.json`
- `evolve_agent/checkpoints/operations/manual_broader_case_sweep_20260422/aes_asap7_evolve.json`
- `evolve_agent/checkpoints/operations/manual_broader_case_sweep_20260422/jpeg_n45_baseline.json`
- `evolve_agent/checkpoints/operations/manual_broader_case_sweep_20260422/jpeg_n45_evolve_retry.json`
