# Negotiation Row-Bucket Hardening Summary - 2026-04-25

## Status

`negotiation_row_bucket_quality_frontier_r5` is the current flow-ready
candidate. It is registered in the matrix runner and documented under
`family_variants/negotiation_row_bucket_quality_frontier_r5/`.

## Mechanism

- Replace illegal-seed by all-cell expansion with row-local spatial buckets.
- Use dirty-region bystander repair instead of repeatedly scanning every
  movable cell on large designs.
- Keep large-design candidate generation bounded through anchor probes,
  horizontal stride, and per-cell candidate budgets.
- Add a bounded net-anchor quality frontier so HPWL-quality scoring is applied
  only to candidates close to the best cheap score.
- Do not count diamond/default fallback as family success.

## Evidence Summary

Same-run strict gates on `aes_nangate45` and `jpeg_nangate45` were legal and
improved both HPWL delta and runtime relative to their same-run baselines.
The next promotion gate is a large/stress design such as `ariane133_nangate45`
or `bp_quad_nangate45`; do not spend the next iteration retuning small cases.

Raw worker logs, runtime patch diffs, and evaluator JSON were intentionally
moved to ignored local backup because they contain machine-local paths. The
commit-ready source of truth is the matrix variant generator plus the family
manifest.

## How To Run

```bash
python3 scripts/run_variant_experiment_matrix.py \
  --family-groups flow_ready_candidates \
  --cases aes_nangate45 jpeg_nangate45 ariane133_nangate45
```
