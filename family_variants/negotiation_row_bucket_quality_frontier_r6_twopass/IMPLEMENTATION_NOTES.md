# R6 Implementation Notes

Inspected source-of-truth files:

- `dpl_evolve_agent/scripts/family_mutations.py`: R6 is currently a
  `bringup_alias_not_algorithm_promotion` entry that points to R5.
- `dpl_evolve_agent/scripts/run_variant_experiment_matrix.py`: R5 composes
  row-bucket active-set, disabled diamond stall fallback, and bounded
  net-anchor frontier scoring.
- `dpl_evolve_agent/family_variants/negotiation_row_bucket_quality_frontier_r5`:
  the R5 patch is generator-delta evidence, not a complete clean-base patch.

Exact hunk targets for promoting this patch into the generator:

- `NegotiationLegalizer.h`: add the four mutable frontier counters after
  `prof_candidates_filtered_`.
- `NegotiationLegalizerPass.cpp::negotiationIter`: reset the frontier counters
  with the existing find-best profiling accumulators.
- `NegotiationLegalizerPass.cpp::negotiationIter`: add the
  `findBest frontier: collected/scored/trimmed/drcFiltered` report after the
  existing `findBest by function` report.
- `NegotiationLegalizerPass.cpp::findBestLocation`: replace the single-pass
  `tryLocation` lambda with `FindBestStats`, `FrontierCandidate`,
  `collectCandidate`, `trimFrontier`, and `scoreFrontier`.
- `NegotiationLegalizerPass.cpp::findBestLocation`: call `collectCandidate`
  from both init and current search windows, then call `scoreFrontier` once.

Generator delta sketch for a later shared-script edit:

```python
def mutate_negotiation_row_bucket_quality_frontier_r6_twopass(src: Path) -> list[str]:
    touched: list[str] = []
    touched.extend(mutate_row_bucket_active_set(src))
    touched.extend(mutate_disable_diamond_stall_fallback(src))
    touched.extend(mutate_r6_twopass_findbest_frontier(src))
    return sorted(set(touched))
```

The generated `mutate_r6_twopass_findbest_frontier` should use the patch hunk
anchors above rather than layering on top of `mutate_net_anchor_quality_frontier`;
R6 intentionally replaces R5 inline scoring with true two-pass scoring.
