# negotiation_row_bucket_quality_frontier_r6_twopass

This directory is the Worker A record for the real R6 two-pass top-K frontier
recipe.  It includes the concrete clean-base research patch for
`dpl_evolve/src/NegotiationLegalizer.{h,cpp}`.

The currently registered materializer entry is still a bring-up alias, not the
true R6 algorithm promotion.  That alias now materializes the current R5
row-bucket quality-frontier generator plus safe threaded runtime support:

- command-level OpenROAD `-threads` is passed into `dpl_evolve`;
- row-disjoint history-cost updates can use multiple worker threads;
- negotiation-order sort keys are precomputed in parallel before the serial
  sort;
- grid-mutating `ripUp`, `place`, and DRC-sensitive `findBestLocation` remain
  serial by design.

R6 keeps the R5 family direction but changes `findBestLocation` from inline
cheap-score frontier scoring to a true two-pass flow:

- pass 1 collects a bounded top-K frontier using negotiation cost, DRC penalty,
  and displacement outlier guard only;
- pass 2 applies net-anchor quality scoring only to the retained top-K frontier;
- `FindBestStats` and aggregate counters expose collected/scored/trimmed/DRC
  rejected candidate telemetry under `negotiation_runtime`;
- large designs get an explicit find-best candidate budget and stride gate.

The patch artifact is:

```text
research_patches/negotiation_row_bucket_quality_frontier_r6_twopass.patch
```

Apply it from the OpenROAD repository root that contains
`src/dpl_evolve/src/NegotiationLegalizerPass.cpp`:

```bash
git apply /home/zhiyuzheng/Project/Agenticflow/dpl_evolve_agent/family_variants/negotiation_row_bucket_quality_frontier_r6_twopass/research_patches/negotiation_row_bucket_quality_frontier_r6_twopass.patch
```

To turn the research patch into the executable matrix recipe later, replace the
current `negotiation_row_bucket_quality_frontier_r6_twopass` alias in
`scripts/run_variant_experiment_matrix.py` with a mutator that composes:

- `mutate_row_bucket_active_set(src)`;
- `mutate_disable_diamond_stall_fallback(src)`;
- this R6 two-pass `findBestLocation`/telemetry delta;
- `mutate_negotiation_safe_threading(src)`.

The smoke-tested registered alias is therefore best described as `r5_threaded`
bring-up evidence, while this directory preserves the intended R6 two-pass patch
for the next algorithmic promotion.
